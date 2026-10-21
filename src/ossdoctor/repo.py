"""A read-only snapshot of a repository that every check works against."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

# Directories that are never part of the project's own source, used when the
# target is not a git checkout and we have to walk the tree ourselves.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
    }
)

# Where GitHub looks for community health files, in lookup order.
COMMUNITY_DIRS = ("", ".github/", "docs/")


def _git_files(root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]
    # --cached still lists files that were deleted from the working tree.
    return [p for p in paths if (root / p).is_file()]


def _walk_files(root: Path) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = Path(dirpath).relative_to(root)
        for name in filenames:
            found.append((rel / name).as_posix())
    return found


@dataclass
class Repo:
    root: Path
    files: list[str]
    is_git: bool

    @classmethod
    def load(cls, root: str | os.PathLike[str]) -> Repo:
        path = Path(root).resolve()
        if not path.is_dir():
            raise NotADirectoryError(f"not a directory: {path}")
        files = _git_files(path)
        is_git = files is not None
        if files is None:
            files = _walk_files(path)
        return cls(root=path, files=sorted(files), is_git=is_git)

    @cached_property
    def _by_lower(self) -> dict[str, str]:
        return {f.lower(): f for f in self.files}

    @cached_property
    def _dirs(self) -> set[str]:
        dirs = set()
        for f in self._by_lower:
            parts = f.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                dirs.add("/".join(parts[:i]))
        return dirs

    def find(self, *paths: str) -> str | None:
        """Return the first of ``paths`` that exists, matched case-insensitively."""
        for p in paths:
            hit = self._by_lower.get(p.lower())
            if hit:
                return hit
        return None

    def find_community(self, *names: str) -> str | None:
        """Find a community file in the root, ``.github/`` or ``docs/``."""
        return self.find(*(d + n for d in COMMUNITY_DIRS for n in names))

    def has_dir(self, path: str) -> bool:
        return path.lower().rstrip("/") in self._dirs

    def matching(self, predicate: Callable[[str], bool]) -> list[str]:
        return [f for f in self.files if predicate(f)]

    def read_text(self, rel: str, limit: int = 1_000_000) -> str:
        with open(self.root / rel, "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")

    def size(self, rel: str) -> int:
        return (self.root / rel).stat().st_size

    @cached_property
    def git_toplevel(self) -> Path | None:
        """The root of the enclosing git work tree, which may be above ``root``."""
        if not self.is_git:
            return None
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return Path(proc.stdout.strip()).resolve()

    @property
    def path_in_git(self) -> str:
        """``root`` relative to the git work tree as a ``dir/`` prefix, or ``""``."""
        top = self.git_toplevel
        if top is None or top == self.root:
            return ""
        return self.root.relative_to(top).as_posix() + "/"

    @cached_property
    def ecosystems(self) -> set[str]:
        """Package ecosystems at the repository root, named as Dependabot names them."""
        markers = {
            "npm": ("package.json",),
            "pip": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"),
            "gomod": ("go.mod",),
            "cargo": ("Cargo.toml",),
            "bundler": ("Gemfile",),
            "composer": ("composer.json",),
            "maven": ("pom.xml",),
            "gradle": ("build.gradle", "build.gradle.kts"),
            "nuget": ("packages.config", "Directory.Packages.props"),
            "docker": ("Dockerfile",),
        }
        found = {eco for eco, names in markers.items() if self.find(*names)}
        if any(f.lower().endswith(".csproj") and "/" not in f for f in self.files):
            found.add("nuget")
        if self.has_dir(".github/workflows"):
            found.add("github-actions")
        return found

    @cached_property
    def project_name(self) -> str:
        pyproject = self.find("pyproject.toml")
        if pyproject:
            try:
                name = tomllib.loads(self.read_text(pyproject)).get("project", {}).get("name")
                if isinstance(name, str) and name:
                    return name
            except tomllib.TOMLDecodeError:
                pass
        package_json = self.find("package.json")
        if package_json:
            try:
                name = json.loads(self.read_text(package_json)).get("name")
                if isinstance(name, str) and name:
                    return name
            except (json.JSONDecodeError, AttributeError):
                pass
        return self.root.name
