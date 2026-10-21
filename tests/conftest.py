from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from ossdoctor.config import load_config
from ossdoctor.repo import Repo
from ossdoctor.runner import run_checks

LONG_README = """\
# demo

A demo project that exists to exercise ossdoctor. It does nothing useful at all,
but this paragraph is long enough to count as a real README for the check.

## Installation

    pip install demo

## Usage

    demo --help

## License

MIT
"""

MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\n"


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., Path]:
    def make(files: dict[str, str | bytes]) -> Path:
        for rel, body in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                target.write_bytes(body)
            else:
                target.write_text(body, encoding="utf-8")
        return tmp_path

    return make


@pytest.fixture
def outcome() -> Callable[[Path, str], object]:
    """Run a single check against a directory and return its outcome."""

    def run(root: Path, check_id: str):
        repo = Repo.load(root)
        report = run_checks(repo, load_config(repo.root), only=[check_id])
        (result,) = report.results
        return result.outcome

    return run


HEALTHY = {
    "README.md": LONG_README,
    "LICENSE": MIT,
    "CHANGELOG.md": "# Changelog\n",
    "CONTRIBUTING.md": "# Contributing\n",
    ".github/CODE_OF_CONDUCT.md": "# Code of Conduct\n",
    ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug\n",
    ".github/pull_request_template.md": "## What\n",
    ".github/CODEOWNERS": "* @demo\n",
    ".github/workflows/ci.yml": "on: push\n",
    "tests/test_demo.py": "def test_ok():\n    pass\n",
    "SECURITY.md": "# Security\n",
    ".github/dependabot.yml": "version: 2\n",
    ".gitignore": "*.pyc\n",
    ".editorconfig": "root = true\n",
    "pyproject.toml": '[project]\nname = "demo"\n',
}
