import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def find_project_root() -> Path:
    candidates = []

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

    for base in candidates:
        static_dir = base / "frontend" / "public" / "static"

        if (
            (static_dir / "cdyp7-rvs-integrity-dashboard.html").exists()
            or (static_dir / "index.html").exists()
        ):
            return base

    return cwd


PROJECT_ROOT = find_project_root()
STATIC_DIR = PROJECT_ROOT / "frontend" / "public" / "static"

print("PROJECT ROOT:", PROJECT_ROOT)
print("USING STATIC PATH:", STATIC_DIR)

os.environ["CDYP7_STATIC_DIR"] = str(STATIC_DIR)
os.environ["CDYP7_COOKIE_SECURE"] = "false"

os.environ["RVS_HOST"] = "skobde-mks-im.kobde.trw.com"
os.environ["RVS_PORT"] = "7001"
os.environ["RVS_IM_EXE"] = r"C:\app\tools\ptc\RVS\bin\im.exe"

# Import after environment variables are set.
from app.gateway.rvs_http_gateway import app


def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8080/auth/login")


if __name__ == "__main__":
    print("Starting CDYP7 RV&S Gateway...")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8080)
