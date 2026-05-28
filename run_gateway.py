"""Local launcher for the CDYP7 RV&S HTTP gateway.

This script configures local RV&S / dashboard environment variables,
loads the FastAPI application after configuration, opens the browser,
and starts Uvicorn on localhost.
"""

from __future__ import annotations

import importlib
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn


def find_project_root() -> Path:
    """Find the project root by locating the dashboard static directory."""
    candidates: list[Path] = []

    cwd = Path.cwd()
    candidates.append(cwd)

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir)
        candidates.append(exe_dir.parent)
        candidates.append(exe_dir.parent.parent)

    script_dir = Path(__file__).resolve().parent
    candidates.append(script_dir)
    candidates.append(script_dir.parent)

    for base_path in candidates:
        static_dir = base_path / "frontend" / "public" / "static"

        dashboard_file = static_dir / "cdyp7-rvs-integrity-dashboard.html"
        index_file = static_dir / "index.html"

        if dashboard_file.exists() or index_file.exists():
            return base_path

    return cwd


def configure_environment() -> Path:
    """Configure environment variables required by the local gateway."""
    project_root = find_project_root()
    static_dir = project_root / "frontend" / "public" / "static"

    print("PROJECT ROOT:", project_root)
    print("USING STATIC PATH:", static_dir)

    os.environ["CDYP7_STATIC_DIR"] = str(static_dir)
    os.environ["CDYP7_COOKIE_SECURE"] = "false"

    os.environ["RVS_HOST"] = "skobde-mks-im.kobde.trw.com"
    os.environ["RVS_PORT"] = "7001"
    os.environ["RVS_IM_EXE"] = r"C:\app\tools\ptc\RVS\bin\im.exe"

    return static_dir


def load_gateway_app() -> Any:
    """Load the FastAPI gateway app after environment configuration."""
    module = importlib.import_module("app.gateway.rvs_http_gateway")
    return module.app


def open_browser() -> None:
    """Open the local login page after the server starts."""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8080/auth/login")


def main() -> None:
    """Start the local CDYP7 RV&S gateway."""
    configure_environment()
    gateway_app = load_gateway_app()

    print("Starting CDYP7 RV&S Gateway...")
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        gateway_app,
        host="127.0.0.1",
        port=8080,
    )


if __name__ == "__main__":
    main()
