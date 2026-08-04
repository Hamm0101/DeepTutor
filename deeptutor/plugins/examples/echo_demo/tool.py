"""Example tool plugin: echoes its input.

Copy this directory into your plugins root to see the `echo_demo` tool
appear in the registry. Remove the directory (or set `type: disabled` in
plugin.yaml) to uninstall.
"""

from __future__ import annotations

from typing import Any

from deeptutor.core.tool_protocol import BaseTool, ToolDefinition, ToolParameter, ToolResult


class Tool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="echo_demo",
            description="Echo the input text back with a prefix. Demo plugin.",
            parameters=[
                ToolParameter(
                    name="text",
                    type="string",
                    description="Text to echo.",
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = str(kwargs.get("text", ""))
        return ToolResult(content=f"[echo_demo] {text}", metadata={"echoed": text})
