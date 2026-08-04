"""Plugin manifest dataclass shared by both registries and the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PluginManifest:
    """Static metadata for a discovered plugin.

    Mirrors the shape that ``/api/v1/plugins/list`` already serialises
    (``name / type / description / stages / version / author``) plus the
    ``entry`` field the capability registry reads to tell tool plugins from
    capability plugins (``capability_registry.py:67``).

    Attributes:
        name: Unique plugin id (also used as the registry key prefix).
        type: ``"tool"`` or ``"capability"``.
        entry: Filename of the Python entry file inside the plugin dir,
            e.g. ``"tool.py"`` or ``"capability.py"``. The registries import
            the plugin module from this file.
        description: Human-readable summary shown in the API/UI.
        stages: For capability plugins, the pipeline stage names.
        version: Semver-ish version string.
        author: Author display name.
        dir: Absolute path to the plugin directory on disk.
    """

    name: str
    type: str  # "tool" | "capability"
    entry: str
    description: str = ""
    stages: list[str] = field(default_factory=list)
    version: str = "0.0.0"
    author: str = ""
    dir: Path = field(default_factory=Path("."))

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to the shape ``/api/v1/plugins/list`` returns."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "stages": self.stages,
            "version": self.version,
            "author": self.author,
        }
