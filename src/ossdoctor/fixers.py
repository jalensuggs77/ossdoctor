"""Generating missing files for failed checks (``ossdoctor fix``)."""

from __future__ import annotations

import datetime as _dt
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

from . import templates
from .repo import Repo
from .runner import Report

CONTACT_PLACEHOLDER = "[INSERT CONTACT EMAIL]"
AUTHOR_PLACEHOLDER = "[INSERT COPYRIGHT HOLDER]"
SUPPORTED_LICENSES = tuple(templates.LICENSES)


class FixSkipped(Exception):
    """Raised by a fixer that cannot generate its file with the given options."""


def git_config(root: Path, key: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(root), "config", "--get", key], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout.strip() or None


@dataclass
class FixOptions:
    license: str = "MIT"
    author: str | None = None
    email: str | None = None
    github_user: str | None = None
    year: int = field(default_factory=lambda: _dt.date.today().year)

    def normalized_license(self) -> str:
        for spdx in SUPPORTED_LICENSES:
            if spdx.lower() == self.license.lower():
                return spdx
        raise FixSkipped(
            f"license {self.license!r} has no built-in template (supported: {', '.join(SUPPORTED_LICENSES)}); "
            "copy the text from https://choosealicense.com/licenses/"
        )


@dataclass
class FixPlan:
    files: dict[str, str] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


Fixer = Callable[[Repo, FixOptions, dict[str, str]], dict[str, str]]
FIXERS: dict[str, Fixer] = {}


def fixer(check_id: str):
    def register(func: Fixer) -> Fixer:
        FIXERS[check_id] = func
        return func

    return register


@fixer("readme")
def _readme(repo, opts, ctx):
    from .checks import find_readme

    if find_readme(repo):
        # An existing but empty README is the author's to write; never overwrite it.
        raise FixSkipped("README exists but is nearly empty; fill it in by hand")
    return {"README.md": templates.README}


@fixer("license")
def _license(repo, opts, ctx):
    return {"LICENSE": templates.LICENSES[opts.normalized_license()]}


@fixer("contributing")
def _contributing(repo, opts, ctx):
    return {"CONTRIBUTING.md": templates.CONTRIBUTING}


@fixer("code-of-conduct")
def _code_of_conduct(repo, opts, ctx):
    return {"CODE_OF_CONDUCT.md": templates.CODE_OF_CONDUCT}


@fixer("security-policy")
def _security(repo, opts, ctx):
    return {"SECURITY.md": templates.SECURITY}


@fixer("changelog")
def _changelog(repo, opts, ctx):
    return {"CHANGELOG.md": templates.CHANGELOG}


@fixer("issue-templates")
def _issue_templates(repo, opts, ctx):
    files = {
        ".github/ISSUE_TEMPLATE/bug_report.yml": templates.ISSUE_BUG,
        ".github/ISSUE_TEMPLATE/feature_request.yml": templates.ISSUE_FEATURE,
    }
    if not repo.find(".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/config.yaml"):
        files[".github/ISSUE_TEMPLATE/config.yml"] = templates.ISSUE_CONFIG
    return files


@fixer("pr-template")
def _pr_template(repo, opts, ctx):
    return {".github/pull_request_template.md": templates.PR_TEMPLATE}


@fixer("codeowners")
def _codeowners(repo, opts, ctx):
    if not opts.github_user:
        raise FixSkipped("pass --github-user NAME to generate CODEOWNERS")
    user = opts.github_user.lstrip("@")
    return {".github/CODEOWNERS": f"# Default reviewers for every file.\n* @{user}\n"}


@fixer("dependency-updates")
def _dependabot(repo, opts, ctx):
    ecosystems = sorted(repo.ecosystems | {"github-actions"})
    lines = ["version: 2", "updates:"]
    for eco in ecosystems:
        lines += [
            f'  - package-ecosystem: "{eco}"',
            '    directory: "/"',
            "    schedule:",
            '      interval: "weekly"',
        ]
        if eco == "github-actions":
            lines += ["    groups:", "      actions:", '        patterns: ["*"]']
    return {".github/dependabot.yml": "\n".join(lines) + "\n"}


@fixer("gitignore")
def _gitignore(repo, opts, ctx):
    parts = [templates.GITIGNORE_COMMON]
    parts += [body for eco, body in templates.GITIGNORE_BY_ECOSYSTEM.items() if eco in repo.ecosystems]
    return {".gitignore": "\n".join(parts)}


@fixer("editorconfig")
def _editorconfig(repo, opts, ctx):
    return {".editorconfig": templates.EDITORCONFIG}


def plan_fixes(repo: Repo, report: Report, opts: FixOptions) -> FixPlan:
    author = opts.author or git_config(repo.root, "user.name")
    email = opts.email or git_config(repo.root, "user.email")
    ctx = {
        "project": repo.project_name,
        "year": str(opts.year),
        "author": author or AUTHOR_PLACEHOLDER,
        "contact": email or CONTACT_PLACEHOLDER,
    }

    plan = FixPlan()
    for result in report.fixable:
        make = FIXERS.get(result.check.id)
        if make is None:
            continue
        try:
            generated = make(repo, opts, ctx)
        except FixSkipped as exc:
            plan.skipped[result.check.id] = str(exc)
            continue
        for path, body in generated.items():
            if (repo.root / path).exists():
                plan.skipped.setdefault(result.check.id, f"{path} already exists")
                continue
            plan.files[path] = Template(body).safe_substitute(ctx)

    written = plan.files.values()
    if not author and any(AUTHOR_PLACEHOLDER in body for body in written):
        plan.notes.append(f"replace {AUTHOR_PLACEHOLDER} with your name (or pass --author)")
    if not email and any(CONTACT_PLACEHOLDER in body for body in written):
        plan.notes.append(f"replace {CONTACT_PLACEHOLDER} with a contact address (or pass --email)")
    return plan


def apply_plan(root: Path, plan: FixPlan) -> None:
    for rel, body in plan.files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # "x" mode refuses to overwrite a file that appeared after planning.
        with open(target, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
