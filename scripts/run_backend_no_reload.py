#!/usr/bin/env python
"""
Backend launcher WITHOUT uvicorn --reload.

The stock `deeptutor.api.run_server` enables uvicorn reload over the whole
project root, which on Windows walks `web/node_modules` (hundreds of
thousands of files) via glob and crashes with MemoryError. This launcher
reuses the exact same runtime/mode/log/port configuration but runs uvicorn
with reload=False, which is sufficient for a frontend-only dev cycle.

Usage (from project root):
    py scripts/run_backend_no_reload.py
"""
import asyncio
import os
import sys

# Ensure the project root is importable (the launcher may be invoked from a
# different cwd, and there is no installed .venv in this environment).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from deeptutor.runtime.home import get_runtime_home

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn  # noqa: E402

os.environ["PYTHONUNBUFFERED"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")


def main() -> None:
    from deeptutor.logging import configure_logging
    from deeptutor.runtime.mode import RunMode, set_mode
    from deeptutor.services.config import get_ws_max_size
    from deeptutor.services.setup import get_backend_port

    project_root = get_runtime_home()
    os.chdir(str(project_root))

    set_mode(RunMode.SERVER)
    configure_logging()
    backend_port = get_backend_port(project_root)

    uvicorn.run(
        "deeptutor.api.main:app",
        host="0.0.0.0",
        port=backend_port,
        reload=False,
        log_level="info",
        access_log=False,
        ws_max_size=get_ws_max_size(),
    )


if __name__ == "__main__":
    main()
