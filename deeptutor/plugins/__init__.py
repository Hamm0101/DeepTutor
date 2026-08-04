"""
Plugin System
=============

External plugin discovery and loading for tools and capabilities.

This package is intentionally optional: the runtime imports it via
``importlib.import_module("deeptutor.plugins.loader")`` inside a
``try/except`` in both :mod:`deeptutor.runtime.registry.capability_registry`
and :mod:`deeptutor.runtime.registry.tool_registry`. If the package is absent
or the plugin directory is empty, both registries silently fall back to
built-ins only — so a fresh install with no plugins behaves identically to
today.

Layout of a plugin directory (default ``data/workspace/plugins``, overridable
via ``DEEPTUTOR_PLUGINS_DIR``)::

    plugins/
      my_plugin/
        plugin.yaml        # manifest (required)
        tool.py            # a BaseTool subclass (optional, for tool plugins)
        capability.py      # a BaseCapability subclass (optional)
        ...support files...

The ``plugin.yaml`` manifest declares the plugin's identity and which entry
file to load. Two kinds are supported, mirroring the runtime's two layers:

* ``type: tool``        — ``entry`` points at a ``tool.py`` exporting a
  ``BaseTool`` subclass (or a ``TOOLS`` list of them).
* ``type: capability``  — ``entry`` points at a ``capability.py`` exporting a
  ``BaseCapability`` subclass (or a ``CAPABILITY`` name).

The capability registry's existing ``load_plugins()`` already skips manifests
whose ``entry`` ends with ``tool.py`` (see
``capability_registry.py:67``), so a single ``discover_plugins()`` can serve
both sides without either registry needing to know the other's filter rules.

Why a directory scan instead of entry_points? Plugins live in the user's
data tree (per-user in multi-user mode), not in the installed package, so
they cannot advertise setuptools entry_points. The scan is cheap (one
``os.listdir`` + one YAML read per plugin) and runs once per process at
first registry access.
"""

from __future__ import annotations

from .loader import (
    PluginManifest,
    discover_plugins,
    get_plugins_dir,
    load_plugin_capability,
    load_plugin_tools,
)

__all__ = [
    "PluginManifest",
    "discover_plugins",
    "load_plugin_capability",
    "load_plugin_tools",
    "get_plugins_dir",
]
