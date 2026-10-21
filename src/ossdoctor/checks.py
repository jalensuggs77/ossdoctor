"""The built-in checks.

Each check is a function decorated with :func:`check`. It receives the
:class:`~ossdoctor.repo.Repo` and the active :class:`~ossdoctor.config.Config`
and returns an :class:`Outcome`.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from .config import Config
from .repo import Repo


class Status(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class Level(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"

    @property
    def weight(self) -> int:
        return {"required": 3, "recommended": 2, "optional": 1}[self.value]


CATEGORIES = ("Documentation", "Community", "Automation", "Security", "Hygiene")


@dataclass(frozen=True)
class Finding:
    """One problem tied to one file, for reports that point at files (SARIF)."""

    path: str
    message: str


@dataclass(frozen=True)
class Outcome:
    status: Status
    detail: str = ""
    # Per-file problems behind a failure. Empty when the problem is that a
    # file is missing; reporters then point at the check's ``location``.
    findings: tuple[Finding, ...] = ()


def passed(detail: str = "") -> Outcome:
    return Outcome(Status.PASS, detail)


def failed(detail: str = "", findings: Iterable[Finding] = ()) -> Outcome:
    return Outcome(Status.FAIL, detail, tuple(findings))


def skipped(detail: str = "") -> Outcome:
    return Outcome(Status.SKIP, detail)


CheckFunc = Callable[[Repo, Config], Outcome]


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    category: str
    level: Level
    hint: str
    fixable: bool
    location: str
    run: CheckFunc


REGISTRY: dict[str, Check] = {}


def check(id: str, title: str, category: str, level: Level, hint: str, *, location: str, fixable: bool = False):
    """Register a check. ``location`` is where the file it looks for belongs."""
    assert category in CATEGORIES, category

    def register(func: CheckFunc) -> CheckFunc:
        if id in REGISTRY:
            raise ValueError(f"duplicate check id: {id}")
        REGISTRY[id] = Check(id, title, category, level, hint, fixable, location, func)
        return func

    return register


# --------------------------------------------------------------------------- #
# Documentation
# --------------------------------------------------------------------------- #

README_NAMES = ("README.md", "README.rst", "README.txt", "README.adoc", "README.org", "README")


def find_readme(repo: Repo) -> str | None:
    return repo.find_community(*README_NAMES)


@check(
    "readme",
    "README",
    "Documentation",
    Level.REQUIRED,
    "A README is the front door of the project: say what it does, how to install it and how to use it.",
    fixable=True,
    location="README.md",
)
def check_readme(repo: Repo, config: Config) -> Outcome:
    readme = find_readme(repo)
    if not readme:
        return failed("no README found")
    if len(repo.read_text(readme).strip()) < 200:
        return failed(f"{readme} is nearly empty", [Finding(readme, f"{readme} is nearly empty")])
    return passed(readme)


README_SECTIONS = {
    "installation": ("install", "getting started", "quick start", "quickstart", "setup", "安装", "快速开始"),
    "usage": (
        "usage",
        "example",
        "getting started",
        "quick start",
        "quickstart",
        "how to use",
        "使用",
        "用法",
        "示例",
        "快速开始",
    ),
    "license": ("license", "licence", "许可", "协议"),
}

_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_UNDERLINE = re.compile(r"^\s*([=\-~^*+#`'\"])\1{2,}\s*$")


_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HTML_HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)


def _headings(text: str) -> list[str]:
    """Markdown, setext/reStructuredText and HTML headings, ignoring fenced code."""
    lines = text.splitlines()
    found = []
    fence = None
    for i, line in enumerate(lines):
        m = _FENCE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        m = _MD_HEADING.match(line)
        if m:
            found.append(m.group(1))
        elif i > 0 and lines[i - 1].strip() and _UNDERLINE.match(line):
            found.append(lines[i - 1].strip())
    found += [re.sub(r"<[^>]+>", "", h).strip() for h in _HTML_HEADING.findall(text)]
    return found


@check(
    "readme-sections",
    "README covers install, usage and license",
    "Documentation",
    Level.RECOMMENDED,
    "Add headings for installation, usage and license so newcomers find answers without reading the source.",
    location="README.md",
)
def check_readme_sections(repo: Repo, config: Config) -> Outcome:
    readme = find_readme(repo)
    if not readme:
        return skipped("no README")
    headings = " | ".join(_headings(repo.read_text(readme))).lower()
    missing = [name for name, words in README_SECTIONS.items() if not any(w in headings for w in words)]
    if missing:
        detail = "missing section: " + ", ".join(missing)
        return failed(detail, [Finding(readme, f"{readme} is {detail}")])
    return passed("all sections present")


# Ordered: more specific licenses must be tested before the ones they contain.
LICENSE_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AGPL-3.0", ("gnu affero general public license",)),
    ("LGPL-3.0", ("gnu lesser general public license", "version 3")),
    ("LGPL-2.1", ("gnu lesser general public license", "version 2.1")),
    ("GPL-3.0", ("gnu general public license", "version 3")),
    ("GPL-2.0", ("gnu general public license", "version 2")),
    ("Apache-2.0", ("apache license", "version 2.0")),
    ("MPL-2.0", ("mozilla public license", "2.0")),
    ("BSL-1.0", ("boost software license",)),
    ("Unlicense", ("free and unencumbered software released into the public domain",)),
    ("MIT", ("permission is hereby granted, free of charge",)),
    ("ISC", ("permission to use, copy, modify, and/or distribute this software for any",)),
    ("BSD-3-Clause", ("redistribution and use in source and binary forms", "neither the name")),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",)),
    ("CC0-1.0", ("cc0 1.0 universal",)),
)

LICENSE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "LICENCE.md",
    "LICENCE.txt",
    "COPYING",
    "COPYING.md",
    "UNLICENSE",
)


def identify_license(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    for spdx, phrases in LICENSE_SIGNATURES:
        if all(p in normalized for p in phrases):
            return spdx
    return None


@check(
    "license",
    "License",
    "Documentation",
    Level.REQUIRED,
    "Without a license nobody may legally use, change or share the code. See https://choosealicense.com.",
    fixable=True,
    location="LICENSE",
)
def check_license(repo: Repo, config: Config) -> Outcome:
    found = repo.find(*LICENSE_NAMES)
    if not found:
        return failed("no LICENSE file found")
    spdx = identify_license(repo.read_text(found))
    return passed(f"{found} ({spdx})" if spdx else f"{found} (license not recognised)")


@check(
    "changelog",
    "Changelog",
    "Documentation",
    Level.RECOMMENDED,
    "Keep a CHANGELOG so users can see what changed between releases. See https://keepachangelog.com.",
    fixable=True,
    location="CHANGELOG.md",
)
def check_changelog(repo: Repo, config: Config) -> Outcome:
    names = ("CHANGELOG", "CHANGES", "HISTORY", "NEWS", "RELEASES")
    found = repo.find(*(n + ext for n in names for ext in ("", ".md", ".rst", ".txt")))
    if found:
        return passed(found)
    if repo.has_dir("changelog.d") or repo.has_dir("changes") or repo.has_dir(".changeset"):
        return passed("changelog fragments directory")
    return failed("no CHANGELOG found")


# --------------------------------------------------------------------------- #
# Community
# --------------------------------------------------------------------------- #


@check(
    "contributing",
    "Contributing guide",
    "Community",
    Level.RECOMMENDED,
    "A CONTRIBUTING guide explains how to set up the project, run tests and submit changes.",
    fixable=True,
    location="CONTRIBUTING.md",
)
def check_contributing(repo: Repo, config: Config) -> Outcome:
    found = repo.find_community("CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt", "CONTRIBUTING")
    return passed(found) if found else failed("no CONTRIBUTING file found")


@check(
    "code-of-conduct",
    "Code of conduct",
    "Community",
    Level.RECOMMENDED,
    "A code of conduct sets expectations for behaviour and tells people how to report problems.",
    fixable=True,
    location="CODE_OF_CONDUCT.md",
)
def check_code_of_conduct(repo: Repo, config: Config) -> Outcome:
    found = repo.find_community("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.rst", "CODE_OF_CONDUCT.txt", "CODE_OF_CONDUCT")
    return passed(found) if found else failed("no CODE_OF_CONDUCT file found")


@check(
    "issue-templates",
    "Issue templates",
    "Community",
    Level.RECOMMENDED,
    "Issue templates collect versions, reproduction steps and expected behaviour up front, which shortens triage.",
    fixable=True,
    location=".github/ISSUE_TEMPLATE",
)
def check_issue_templates(repo: Repo, config: Config) -> Outcome:
    templates = repo.matching(
        lambda f: (
            f.lower().startswith((".github/issue_template/", "docs/issue_template/", "issue_template/"))
            and f.lower().endswith((".md", ".yml", ".yaml"))
            and not f.lower().endswith(("/config.yml", "/config.yaml"))
        )
    )
    if templates:
        return passed(f"{len(templates)} template(s)")
    single = repo.find_community("ISSUE_TEMPLATE.md", "issue_template.md")
    return passed(single) if single else failed("no issue templates found")


@check(
    "pr-template",
    "Pull request template",
    "Community",
    Level.OPTIONAL,
    "A pull request template reminds contributors to describe the change, link issues and add tests.",
    fixable=True,
    location=".github/pull_request_template.md",
)
def check_pr_template(repo: Repo, config: Config) -> Outcome:
    found = repo.find_community("pull_request_template.md", "PULL_REQUEST_TEMPLATE.md")
    if found:
        return passed(found)
    if repo.has_dir(".github/pull_request_template"):
        return passed(".github/PULL_REQUEST_TEMPLATE/")
    return failed("no pull request template found")


@check(
    "codeowners",
    "CODEOWNERS",
    "Community",
    Level.OPTIONAL,
    "CODEOWNERS requests reviews from the right maintainers automatically. Generate one with `ossdoctor fix --github-user NAME`.",
    fixable=True,
    location=".github/CODEOWNERS",
)
def check_codeowners(repo: Repo, config: Config) -> Outcome:
    found = repo.find("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS")
    return passed(found) if found else failed("no CODEOWNERS file found")


# --------------------------------------------------------------------------- #
# Automation
# --------------------------------------------------------------------------- #

CI_FILES = (
    ".gitlab-ci.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    ".woodpecker.yml",
    "appveyor.yml",
    ".appveyor.yml",
    ".cirrus.yml",
)


@check(
    "ci",
    "Continuous integration",
    "Automation",
    Level.REQUIRED,
    "Run tests on every push and pull request, e.g. with a GitHub Actions workflow in .github/workflows/.",
    location=".github/workflows",
)
def check_ci(repo: Repo, config: Config) -> Outcome:
    workflows = repo.matching(lambda f: f.lower().startswith(".github/workflows/") and f.lower().endswith((".yml", ".yaml")))
    if workflows:
        return passed(f"GitHub Actions ({len(workflows)} workflow(s))")
    found = repo.find(*CI_FILES)
    if found:
        return passed(found)
    if repo.has_dir(".buildkite") or repo.has_dir(".woodpecker"):
        return passed("CI configuration directory")
    return failed("no CI configuration found")


TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing"}
TEST_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "*_test.go",
    "*.test.[jt]s",
    "*.test.[jt]sx",
    "*.spec.[jt]s",
    "*.spec.[jt]sx",
    "*_spec.rb",
    "*Test.java",
    "*Tests.cs",
    "*_test.exs",
)


def _is_test_file(path: str) -> bool:
    p = PurePosixPath(path)
    if any(part.lower() in TEST_DIRS for part in p.parts[:-1]):
        return True
    return any(fnmatch.fnmatchcase(p.name, pat) for pat in TEST_FILE_PATTERNS)


@check(
    "tests",
    "Automated tests",
    "Automation",
    Level.REQUIRED,
    "Tests let you merge contributions with confidence. Add a tests/ directory and run it in CI.",
    location="tests",
)
def check_tests(repo: Repo, config: Config) -> Outcome:
    tests = repo.matching(_is_test_file)
    if tests:
        return passed(f"{len(tests)} test file(s)")
    if repo.find("Cargo.toml") and any(f.endswith(".rs") for f in repo.files):
        # Rust keeps unit tests inline; look for the test attribute.
        for f in repo.matching(lambda f: f.endswith(".rs")):
            if "#[test]" in repo.read_text(f, limit=200_000):
                return passed("inline Rust tests")
    return failed("no test files found")


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #


@check(
    "security-policy",
    "Security policy",
    "Security",
    Level.RECOMMENDED,
    "SECURITY.md tells researchers how to report vulnerabilities privately instead of opening public issues.",
    fixable=True,
    location="SECURITY.md",
)
def check_security_policy(repo: Repo, config: Config) -> Outcome:
    found = repo.find_community("SECURITY.md", "SECURITY.rst", "SECURITY.txt", "SECURITY")
    return passed(found) if found else failed("no SECURITY policy found")


@check(
    "dependency-updates",
    "Automated dependency updates",
    "Security",
    Level.RECOMMENDED,
    "Dependabot or Renovate keeps dependencies patched without manual work.",
    fixable=True,
    location=".github/dependabot.yml",
)
def check_dependency_updates(repo: Repo, config: Config) -> Outcome:
    found = repo.find(
        ".github/dependabot.yml",
        ".github/dependabot.yaml",
        "renovate.json",
        "renovate.json5",
        ".renovaterc",
        ".renovaterc.json",
        ".github/renovate.json",
        ".github/renovate.json5",
        ".gitlab/renovate.json",
    )
    return passed(found) if found else failed("no Dependabot or Renovate configuration found")


# Projects can opt out of lockfiles deliberately, e.g. libraries that test against fresh installs.
_NO_LOCKFILE = re.compile(r"^\s*package-lock\s*=\s*false\s*$", re.MULTILINE)
NODE_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")


@check(
    "lockfile",
    "Dependency lockfile",
    "Security",
    Level.RECOMMENDED,
    "Commit the lockfile so CI and contributors install exactly the dependency versions you tested.",
    location="package.json",
)
def check_lockfile(repo: Repo, config: Config) -> Outcome:
    results = []  # (ecosystem, manifest, lockfile or None)
    opted_out = []
    package_json = repo.find("package.json")
    if package_json:
        npmrc = repo.find(".npmrc")
        if npmrc and _NO_LOCKFILE.search(repo.read_text(npmrc)):
            opted_out.append(f"npm (disabled in {npmrc})")
        else:
            results.append(("npm", package_json, repo.find(*NODE_LOCKFILES)))
    gomod = repo.find("go.mod")
    if gomod and re.search(r"^\s*require\b", repo.read_text(gomod), re.MULTILINE):
        results.append(("Go", gomod, repo.find("go.sum")))
    if not results:
        return skipped("lockfile not used: " + ", ".join(opted_out) if opted_out else "no ecosystem that needs a lockfile")
    missing = [(eco, manifest) for eco, manifest, lock in results if not lock]
    if missing:
        return failed(
            "missing lockfile for " + ", ".join(eco for eco, _ in missing),
            [Finding(manifest, f"{manifest} has no committed {eco} lockfile") for eco, manifest in missing],
        )
    return passed(", ".join(lock for _, _, lock in results if lock))


SECRET_FILE_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".npmrc.auth", "credentials.json", ".pypirc", ".netrc"}
SECRET_SUFFIXES = (".p12", ".pfx", ".keystore", ".jks")
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")


def _looks_secret(repo: Repo, path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    if name == ".env" or (name.startswith(".env.") and not name.endswith(ENV_TEMPLATE_SUFFIXES)):
        return True
    if name in SECRET_FILE_NAMES or name.endswith(SECRET_SUFFIXES):
        return True
    if name.endswith((".pem", ".key")):
        return "PRIVATE KEY-----" in repo.read_text(path, limit=20_000)
    return False


@check(
    "no-secret-files",
    "No committed secrets",
    "Security",
    Level.REQUIRED,
    "Remove credentials from the repository, rotate them, and add the files to .gitignore. "
    "Deleting a file does not remove it from git history.",
    location=".gitignore",
)
def check_no_secret_files(repo: Repo, config: Config) -> Outcome:
    hits = [f for f in repo.files if not any(fnmatch.fnmatch(f, pat) for pat in config.ignore_paths) and _looks_secret(repo, f)]
    if hits:
        shown = ", ".join(hits[:5]) + (f" and {len(hits) - 5} more" if len(hits) > 5 else "")
        return failed(
            f"possible secrets: {shown}",
            [Finding(f, f"{f} looks like a secret and should not be committed") for f in hits],
        )
    return passed("none found")


# --------------------------------------------------------------------------- #
# Hygiene
# --------------------------------------------------------------------------- #


@check(
    "gitignore",
    ".gitignore",
    "Hygiene",
    Level.RECOMMENDED,
    "A .gitignore keeps build output, caches and local settings out of commits.",
    fixable=True,
    location=".gitignore",
)
def check_gitignore(repo: Repo, config: Config) -> Outcome:
    found = repo.find(".gitignore")
    return passed(found) if found else failed("no .gitignore found")


@check(
    "editorconfig",
    ".editorconfig",
    "Hygiene",
    Level.OPTIONAL,
    "An .editorconfig keeps indentation and line endings consistent across contributors' editors.",
    fixable=True,
    location=".editorconfig",
)
def check_editorconfig(repo: Repo, config: Config) -> Outcome:
    found = repo.find(".editorconfig")
    return passed(found) if found else failed("no .editorconfig found")


@check(
    "no-large-files",
    "No large files",
    "Hygiene",
    Level.RECOMMENDED,
    "Large binaries bloat every clone. Move them to releases or Git LFS. The limit is set with `large-file-mb`.",
    location=".gitattributes",
)
def check_no_large_files(repo: Repo, config: Config) -> Outcome:
    limit = int(config.large_file_mb * 1024 * 1024)
    big = [
        (f, size)
        for f in repo.files
        if not any(fnmatch.fnmatch(f, pat) for pat in config.ignore_paths) and (size := repo.size(f)) > limit
    ]
    if big:
        big.sort(key=lambda item: -item[1])
        shown = ", ".join(f"{f} ({size / 1024 / 1024:.1f} MB)" for f, size in big[:5])
        return failed(
            f"over {config.large_file_mb:g} MB: {shown}",
            [Finding(f, f"{f} is {size / 1024 / 1024:.1f} MB (limit {config.large_file_mb:g} MB)") for f, size in big],
        )
    return passed(f"all files under {config.large_file_mb:g} MB")
