"""
Plugin Loader
=============

Discovers plugins from the plugin directory and loads them into the tool and
capability registries.

Discovery is a directory scan: every immediate subdirectory of the plugin
root that contains a ``plugin.yaml`` is a candidate. The YAML must declare
``name``, ``type`` (``tool`` | ``capability``), and ``entry`` (the Python
file to import). Optional fields: ``description``, ``stages`` (capability),
``version``, ``author``.

Loading uses :func:`importlib.util.spec_from_file_location` so plugins do
not need to be on ``sys.path`` — each plugin dir is its own import root.
A plugin module exports either:

* **tool** — a ``BaseTool`` subclass named ``Tool`` (the convention) or a
  module-level ``TOOLS`` list of ``BaseTool`` subclasses/instances.
* **capability** — a ``BaseCapability`` subclass named ``Capability`` or a
  module-level ``CAPABILITY`` string giving the class name to read back.

All failures are logged and skipped: one broken plugin never blocks the
others or the built-in registries.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING
import uuid

import yaml

from .manifest import PluginManifest

if TYPE_CHECKING:
    from deeptutor.core.capability_protocol import BaseCapability
    from deeptutor.core.tool_protocol import BaseTool

logger = logging.getLogger(__name__)

# Env override for the plugin root. Falls back to the user workspace's
# ``plugins/`` subdir so per-user plugins work in multi-user mode without
# any extra wiring.
_PLUGINS_DIR_ENV = "DEEPTUTOR_PLUGINS_DIR"
_MANIFEST_FILENAME = "plugin.yaml"


def get_plugins_dir() -> Path:
    """Resolve the plugin root directory.

    Priority:
      1. ``$DEEPTUTOR_PLUGINS_DIR`` (absolute path).
      2. ``<workspace>/plugins`` under the active path service.

    The directory is *not* created here — absence is a normal "no plugins"
    state and discovery returns an empty list.
    """
    env = os.environ.get(_PLUGINS_DIR_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    try:
        from deeptutor.services.path_service import get_path_service

        return get_path_service().get_workspace_dir() / "plugins"
    except Exception:
        logger.debug("path_service unavailable; plugin dir defaults to ./plugins", exc_info=True)
        return Path("./plugins")


def _read_manifest(plugin_dir: Path) -> PluginManifest | None:
    """Parse ``plugin.yaml`` from a plugin directory.

    Returns ``None`` (with a warning log) on any structural problem so the
    caller can skip the directory without raising.
    """
    manifest_path = plugin_dir / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.warning("plugin manifest unreadable: %s", manifest_path, exc_info=True)
        return None
    if not isinstance(raw, dict):
        logger.warning("plugin manifest not a mapping: %s", manifest_path)
        return None

    name = str(raw.get("name", "")).strip()
    ptype = str(raw.get("type", "")).strip().lower()
    entry = str(raw.get("entry", "")).strip()
    if not name or not ptype or not entry:
        logger.warning(
            "plugin manifest missing required field(s) in %s "
            "(need name/type/entry; got name=%r type=%r entry=%r)",
            manifest_path,
            name,
            ptype,
            entry,
        )
        return None
    if ptype not in {"tool", "capability"}:
        logger.warning("plugin %r has unsupported type %r (expected tool|capability)", name, ptype)
        return None

    return PluginManifest(
        name=name,
        type=ptype,
        entry=entry,
        description=str(raw.get("description", "")).strip(),
        stages=list(raw.get("stages", []) or []),
        version=str(raw.get("version", "0.0.0")).strip() or "0.0.0",
        author=str(raw.get("author", "")).strip(),
        dir=plugin_dir,
    )


def _import_plugin_module(manifest: PluginManifest):
    """Import the plugin's entry file as an isolated module.

    Each plugin gets a unique module name (``deeptutor_plugins.<uuid>.<stem>``)
    so two plugins with the same ``tool.py`` filename don't collide in
    ``sys.modules``, and the plugin dir is prepended to the import search
    path only for the duration of this import so plugins can use relative
    sibling imports.
    """
    entry_path = manifest.dir / manifest.entry
    if not entry_path.is_file():
        logger.warning("plugin %r entry file missing: %s", manifest.name, entry_path)
        return None

    stem = entry_path.stem
    module_name = f"deeptutor_plugins.{uuid.uuid4().hex}.{stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry_path)
        if spec is None or spec.loader is None:
            logger.warning("plugin %r: cannot build import spec for %s", manifest.name, entry_path)
            return None
        module = importlib.util.module_from_spec(spec)
        # Make the plugin dir importable so `from .helper import x` style
        # sibling imports work. Insert at the front and remove afterwards.
        added = False
        if str(manifest.dir) not in sys.path:
            sys.path.insert(0, str(manifest.dir))
            added = True
        try:
            spec.loader.exec_module(module)
        finally:
            if added:
                try:
                    sys.path.remove(str(manifest.dir))
                except ValueError:
                    pass
        sys.modules[module_name] = module
        return module
    except Exception:
        logger.warning("plugin %r failed to import: %s", manifest.name, entry_path, exc_info=True)
        return None


def discover_plugins() -> list[PluginManifest]:
    """Scan the plugin directory and return all valid manifests.

    Order is sorted by plugin name for deterministic registration. A missing
    or empty plugin directory returns ``[]`` (the normal no-plugins state).
    """
    root = get_plugins_dir()
    if not root.is_dir():
        return []
    manifests: list[PluginManifest] = []
    try:
        candidates = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        logger.warning("plugin directory not readable: %s", root, exc_info=True)
        return []
    for plugin_dir in candidates:
        manifest = _read_manifest(plugin_dir)
        if manifest is not None:
            manifests.append(manifest)
    return manifests


def _instantiate_tool(cls) -> "BaseTool | None":
    """Best-effort instantiate a BaseTool subclass."""
    try:
        return cls()
    except Exception:
        logger.warning("tool plugin class failed to instantiate: %s", cls, exc_info=True)
        return None


def load_plugin_tools(manifest: PluginManifest) -> list["BaseTool"]:
    """Load tool instances from a tool-type plugin.

    The entry module may export:
      * ``Tool`` — a ``BaseTool`` subclass (instantiated).
      * ``TOOLS`` — a list of ``BaseTool`` subclasses or instances.

    Returns an empty list on any failure (logged, not raised).
    """
    if manifest.type != "tool":
        return []
    module = _import_plugin_module(manifest)
    if module is None:
        return []

    from deeptutor.core.tool_protocol import BaseTool

    tools: list[BaseTool] = []

    # ``Tool`` convention.
    tool_attr = getattr(module, "Tool", None)
    if isinstance(tool_attr, type) and issubclass(tool_attr, BaseTool):
        instance = _instantiate_tool(tool_attr)
        if instance is not None:
            tools.append(instance)

    # ``TOOLS`` list (subclasses or instances).
    raw_tools = getattr(module, "TOOLS", None)
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, BaseTool):
                tools.append(item)
            elif isinstance(item, type) and issubclass(item, BaseTool):
                instance = _instantiate_tool(item)
                if instance is not None:
                    tools.append(instance)

    if not tools:
        logger.warning(
            "tool plugin %r exported no BaseTool subclass via `Tool` or `TOOLS`",
            manifest.name,
        )
    return tools


def load_plugin_capability(manifest: PluginManifest) -> "BaseCapability | None":
    """Load a capability instance from a capability-type plugin.

    The entry module may export:
      * ``Capability`` — a ``BaseCapability`` subclass (instantiated).
      * ``CAPABILITY`` — a string naming the class to read back from the module.

    Returns ``None`` on any failure (logged, not raised). The capability
    registry's ``load_plugins`` already filters out tool plugins by checking
    ``manifest.entry.endswith("tool.py")``, but we also short-circuit on
    ``type != "capability"`` for safety.
    """
    if manifest.type != "capability":
        return None
    module = _import_plugin_module(manifest)
    if module is None:
        return None

    from deeptutor.core.capability_protocol import BaseCapability

    cls = getattr(module, "Capability", None)
    if isinstance(cls, type) and issubclass(cls, BaseCapability):
        try:
            return cls()
        except Exception:
            logger.warning("capability plugin %r failed to instantiate", manifest.name, exc_info=True)
            return None

    cap_name = getattr(module, "CAPABILITY", None)
    if isinstance(cap_name, str) and cap_name:
        cls = getattr(module, cap_name, None)
        if isinstance(cls, type) and issubclass(cls, BaseCapability):
            try:
                return cls()
            except Exception:
                logger.warning(
                    "capability plugin %r failed to instantiate %s", manifest.name, cap_name, exc_info=True
                )
                return None

    logger.warning(
        "capability plugin %r exported no BaseCapability subclass via `Capability` or `CAPABILITY`",
        manifest.name,
    )
    return None
