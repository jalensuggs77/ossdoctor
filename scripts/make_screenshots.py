"""Regenerate the terminal screenshots in docs/images/ used by the README.

Builds a small demo repository in a temporary directory, runs the real
ossdoctor CLI against it and renders the colored output as SVG.

Requires `rich` (not a dependency of ossdoctor itself):

    pip install rich
    python scripts/make_screenshots.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
DISPLAY_PATH = "~/widget"
WIDTH = 96

DEMO_FILES = {
    "pyproject.toml": '[project]\nname = "widget"\nversion = "1.2.0"\n',
    "README.md": (
        "# widget\n\nWidget turns spreadsheets into dashboards. It reads CSV and Excel files\n"
        "and serves an interactive page with charts, filters and exports.\n\n"
        "## Installation\n\n    pip install widget\n\n## Usage\n\n    widget serve sales.csv\n"
    ),
    "LICENSE": "                                 Apache License\n                           Version 2.0, January 2004\n",
    "CONTRIBUTING.md": "# Contributing\n\nRun `pytest` before opening a pull request.\n",
    ".github/workflows/ci.yml": "on: [push, pull_request]\n",
    "src/widget/__init__.py": "",
    "tests/test_widget.py": "def test_import():\n    import widget  # noqa: F401\n",
    ".gitignore": "__pycache__/\n",
    ".env": "DATABASE_URL=postgres://localhost/widget\n",
}


def build_demo(root: Path) -> None:
    for rel, body in DEMO_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Ada Lovelace"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "ada@example.com"], check=True)


def run(root: Path, *args: str) -> str:
    env = {**os.environ, "FORCE_COLOR": "1", "COLUMNS": str(WIDTH)}
    env.pop("NO_COLOR", None)
    proc = subprocess.run(
        [sys.executable, "-m", "ossdoctor", *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout.replace(str(root), DISPLAY_PATH)


def prompt(command: str) -> str:
    return f"\033[1;32m$\033[0m \033[1m{command}\033[0m\n"


def save(name: str, ansi: str) -> None:
    console = Console(record=True, width=WIDTH, force_terminal=True, color_system="truecolor", file=open(os.devnull, "w"))
    console.print(Text.from_ansi(ansi.rstrip("\n")), soft_wrap=True)
    OUT.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(OUT / name), title="ossdoctor")
    print(f"wrote {(OUT / name).relative_to(ROOT)}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve() / "widget"
        root.mkdir()
        build_demo(root)

        save("check.svg", prompt("ossdoctor") + run(root))

        fix = run(root, "fix", "--github-user", "ada")
        # After fixing, show only what is left for the maintainer to do by hand.
        after = run(root).splitlines()
        summary = "\n".join(line for line in after if "✘" in line or "Score:" in line)
        save("fix.svg", prompt("ossdoctor fix --github-user ada") + fix + "\n" + prompt("ossdoctor") + summary)


if __name__ == "__main__":
    main()
