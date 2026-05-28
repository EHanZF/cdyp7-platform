#!/usr/bin/env python3
"""
CDYP7 local lint/debug runner.

Runs flake8, pylint8 and mypy are blocking. Pylint is advisory.Runs flake8, pylint, and mypy using the active Python interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPORT_DIR = Path(".lint_debug")
SRC_PATHS = [
    Path("app"),
    Path("run_gateway.py"),
]

TOOLS = {
    "flake8": ["flake8", "--count", "--statistics"],
    "pylint": ["pylint", "--reports=n"],
    "mypy": ["mypy", "--ignore-missing-imports"],
}

BLOCKING_TOOLS = {"flake8", "mypy"}


def tool_available(module_name: str) -> bool:
    """Return True if a Python module can be executed."""
    result = subprocess.run(
        [sys.executable, "-m", module_name, "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run_tool(name: str, args: list[str]) -> int:
    """Run a lint tool and write its output to a report file."""
    report_path = REPORT_DIR / f"{name}.txt"

    cmd = [
        sys.executable,
        "-m",
        *args,
        *[str(path) for path in SRC_PATHS if path.exists()],
    ]

    print(f"▶ Running {name}...")
    print("  " + " ".join(cmd))

    with report_path.open("w", encoding="utf-8") as output_file:
        result = subprocess.run(
            cmd,
            stdout=output_file,
            stderr=subprocess.STDOUT,
            check=False,
        )

    print(f"  exit={result.returncode}, report={report_path}")
    return result.returncode


def count_lines(path: Path) -> int:
    """Count non-empty lines in a report file."""
    if not path.exists():
        return 0

    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def main() -> int:
    """Run local lint diagnostics."""
    REPORT_DIR.mkdir(exist_ok=True)

    print("=== CDYP7 Lint Debugger ===")
    print(f"Python: {sys.executable}")
    print(f"Report dir: {REPORT_DIR}")
    print()

    missing = [
        name
        for name in TOOLS
        if not tool_available(name)
    ]

    if missing:
        print("Missing lint tools:")
        for name in missing:
            print(f"  - {name}")

        print()
        print("Install them with:")
        print(
            "  python -m pip install "
            "flake8 pylint mypy black ruff"
        )
        return 2

    exit_codes: dict[str, int] = {}

    for name, args in TOOLS.items():
        exit_codes[name] = run_tool(name, args)

    print()
    print("=== Summary ===")
    for name in TOOLS:
        report = REPORT_DIR / f"{name}.txt"
        gate_type = "blocking" if name in BLOCKING_TOOLS else "advisory"
        print(
            f"{name}: exit={exit_codes[name]}, "
            f"lines={count_lines(report)}, "
            f"gate={gate_type}"
        )

    print()
    print("Reports written to:")
    for name in TOOLS:
        print(f"  - {REPORT_DIR / (name + '.txt')}")

    blocking_failed = any(
        exit_codes[name] != 0
        for name in BLOCKING_TOOLS
    )

    if blocking_failed:
        print()
        print("Blocking lint/type issues were found.")
        print("Fix flake8 and mypy failures before merge.")
        return 1

    if exit_codes.get("pylint", 0) != 0:
        print()
        print("Pylint advisory findings remain.")
        print("See .lint_debug/pylint.txt for cleanup items.")

    print()
    print("✅ Blocking lint/type checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
