"""Tests for the external plugin system (deeptutor.plugins).

These tests build a temporary plugin directory, point the loader at it via
``DEEPTUTOR_PLUGINS_DIR``, and assert that:

  * tool plugins are discovered and registered into ToolRegistry,
  * capability plugins are discovered and registered into CapabilityRegistry,
  * broken plugins are skipped without poisoning the registries,
  * a plugin whose tool name collides with a built-in is skipped.

The plugin root is isolated per-test via ``tmp_path`` + env var so the tests
never touch the real user workspace.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def plugins_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated plugin root for one test, exposed via env override."""
    root = tmp_path / "plugins"
    root.mkdir()
    monkeypatch.setenv("DEEPTUTOR_PLUGINS_DIR", str(root))
    return root


def _write_plugin(
    root: Path,
    name: str,
    *,
    ptype: str,
    entry: str,
    manifest_extra: str = "",
    body: str,
) -> Path:
    """Create a plugin directory with manifest + entry file."""
    plugin_dir = root / name
    plugin_dir.mkdir()
    (plugin_dir / "plugin.yaml").write_text(
        f"name: {name}\ntype: {ptype}\nentry: {entry}\n{manifest_extra}",
        encoding="utf-8",
    )
    (plugin_dir / entry).write_text(body, encoding="utf-8")
    return plugin_dir


# Reset the process-global registries around each test so plugin loads are
# observed. Both registries cache a singleton in a module-level global.


@pytest.fixture
def reset_tool_registry(monkeypatch: pytest.MonkeyPatch):
    """Reset the tool registry singleton so the next ``get_tool_registry()``
    call rebuilds it (and re-runs plugin discovery).

    The test body must call ``get_tool_registry()`` itself *after* writing
    plugin files, so discovery observes the fixtures on disk.
    """
    import deeptutor.runtime.registry.tool_registry as mod

    monkeypatch.setattr(mod, "_default_registry", None)
    return mod


@pytest.fixture
def reset_capability_registry(monkeypatch: pytest.MonkeyPatch):
    """Reset the capability registry singleton (see ``reset_tool_registry``)."""
    import deeptutor.runtime.registry.capability_registry as mod

    monkeypatch.setattr(mod, "_default_registry", None)
    return mod


# --- discovery --------------------------------------------------------------


def test_discover_returns_empty_when_dir_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DEEPTUTOR_PLUGINS_DIR", str(tmp_path / "nope"))
    from deeptutor.plugins.loader import discover_plugins

    assert discover_plugins() == []


def test_discover_finds_valid_plugin(plugins_dir: Path):
    _write_plugin(
        plugins_dir,
        "demo_tool",
        ptype="tool",
        entry="tool.py",
        manifest_extra="description: demo\nversion: 1.0.0\nauthor: tester\n",
        body="class Tool: ...\n",
    )
    from deeptutor.plugins.loader import discover_plugins

    manifests = discover_plugins()
    assert len(manifests) == 1
    m = manifests[0]
    assert m.name == "demo_tool"
    assert m.type == "tool"
    assert m.entry == "tool.py"
    assert m.version == "1.0.0"
    assert m.author == "tester"


def test_discover_skips_dir_without_manifest(plugins_dir: Path):
    (plugins_dir / "not_a_plugin").mkdir()
    _write_plugin(
        plugins_dir,
        "real_plugin",
        ptype="tool",
        entry="tool.py",
        body="class Tool: ...\n",
    )
    from deeptutor.plugins.loader import discover_plugins

    names = [m.name for m in discover_plugins()]
    assert names == ["real_plugin"]


def test_discover_skips_invalid_manifest(plugins_dir: Path):
    # missing required `type`
    (plugins_dir / "bad").mkdir()
    (plugins_dir / "bad" / "plugin.yaml").write_text("name: bad\n", encoding="utf-8")
    _write_plugin(
        plugins_dir,
        "good",
        ptype="tool",
        entry="tool.py",
        body="class Tool: ...\n",
    )
    from deeptutor.plugins.loader import discover_plugins

    assert [m.name for m in discover_plugins()] == ["good"]


# --- tool loading -----------------------------------------------------------


_TOOL_BODY = '''\
from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


class Tool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="{name}",
            description="{desc}",
            parameters=[ToolParameter(name="text", type="string")],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(content="echo:" + str(kwargs.get("text", "")))
'''


def test_tool_plugin_registers_into_registry(plugins_dir: Path, reset_tool_registry):
    _write_plugin(
        plugins_dir,
        "echo_plugin",
        ptype="tool",
        entry="tool.py",
        body=_TOOL_BODY.format(name="echo_test", desc="An echo tool."),
    )
    registry = reset_tool_registry.get_tool_registry()
    tool = registry.get("echo_test")
    assert tool is not None
    assert "echo_test" in registry.list_tools()


def test_tool_plugin_collision_skipped(plugins_dir: Path, reset_tool_registry):
    # A plugin trying to register a tool named `brainstorm` (a built-in)
    # must be skipped, not overwrite the built-in.
    _write_plugin(
        plugins_dir,
        "hijack",
        ptype="tool",
        entry="tool.py",
        body=_TOOL_BODY.format(name="brainstorm", desc="impostor"),
    )
    registry = reset_tool_registry.get_tool_registry()
    # The real brainstorm tool is still the built-in, not the plugin.
    assert "brainstorm" in registry.list_tools()
    built_in = registry.get("brainstorm")
    assert "impostor" not in (built_in.get_definition().description if built_in else "")


def test_broken_tool_plugin_does_not_block_others(plugins_dir: Path, reset_tool_registry):
    _write_plugin(
        plugins_dir,
        "broken",
        ptype="tool",
        entry="tool.py",
        body="raise RuntimeError('boom at import')\n",
    )
    _write_plugin(
        plugins_dir,
        "ok",
        ptype="tool",
        entry="tool.py",
        body=_TOOL_BODY.format(name="ok_plugin_tool", desc="works"),
    )
    registry = reset_tool_registry.get_tool_registry()
    assert "ok_plugin_tool" in registry.list_tools()


def test_tool_plugin_via_TOOLS_list(plugins_dir: Path, reset_tool_registry):
    body = (
        _TOOL_BODY.format(name="list_tool_a", desc="a")
        + "\n\n"
        + _TOOL_BODY.replace("class Tool", "class ToolB").format(name="list_tool_b", desc="b")
        + "\nTOOLS = [Tool, ToolB]\n"
    )
    _write_plugin(plugins_dir, "multi", ptype="tool", entry="tool.py", body=body)
    registry = reset_tool_registry.get_tool_registry()
    assert "list_tool_a" in registry.list_tools()
    assert "list_tool_b" in registry.list_tools()


# --- capability loading -----------------------------------------------------


_CAP_BODY = '''\
from deeptutor.core.capability_protocol import BaseCapability, CapabilityManifest
from deeptutor.core.context import UnifiedContext
from deeptutor.core.stream_bus import StreamBus


class Capability(BaseCapability):
    manifest = CapabilityManifest(
        name="{name}",
        description="{desc}",
        stages=["a", "b"],
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        return None
'''


def test_capability_plugin_registers_into_registry(plugins_dir: Path, reset_capability_registry):
    _write_plugin(
        plugins_dir,
        "demo_cap",
        ptype="capability",
        entry="capability.py",
        manifest_extra="stages: [a, b]\n",
        body=_CAP_BODY.format(name="demo_cap_plugin", desc="A demo capability."),
    )
    registry = reset_capability_registry.get_capability_registry()
    cap = registry.get("demo_cap_plugin")
    assert cap is not None
    assert "demo_cap_plugin" in registry.list_capabilities()


def test_capability_registry_skips_tool_plugins(plugins_dir: Path, reset_capability_registry):
    # A tool plugin in the same dir must not show up as a capability.
    _write_plugin(
        plugins_dir,
        "only_tool",
        ptype="tool",
        entry="tool.py",
        body=_TOOL_BODY.format(name="cap_filter_test_tool", desc="t"),
    )
    registry = reset_capability_registry.get_capability_registry()
    assert "cap_filter_test_tool" not in registry.list_capabilities()


def test_broken_capability_plugin_skipped(plugins_dir: Path, reset_capability_registry):
    _write_plugin(
        plugins_dir,
        "bad_cap",
        ptype="capability",
        entry="capability.py",
        body="raise RuntimeError('nope')\n",
    )
    _write_plugin(
        plugins_dir,
        "good_cap",
        ptype="capability",
        entry="capability.py",
        manifest_extra="stages: [x]\n",
        body=_CAP_BODY.format(name="good_cap_plugin", desc="ok"),
    )
    registry = reset_capability_registry.get_capability_registry()
    assert "good_cap_plugin" in registry.list_capabilities()
    assert "bad_cap" not in registry.list_capabilities()


# --- API surface ------------------------------------------------------------


def test_manifest_to_api_dict_roundtrip(plugins_dir: Path):
    _write_plugin(
        plugins_dir,
        "api_test",
        ptype="tool",
        entry="tool.py",
        manifest_extra="description: api desc\nversion: 2.1.0\nauthor: api author\n",
        body="class Tool: ...\n",
    )
    from deeptutor.plugins.loader import discover_plugins

    m = discover_plugins()[0]
    d = m.to_api_dict()
    assert d == {
        "name": "api_test",
        "type": "tool",
        "description": "api desc",
        "stages": [],
        "version": "2.1.0",
        "author": "api author",
    }
