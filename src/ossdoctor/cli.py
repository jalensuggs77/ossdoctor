"""Command-line interface."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence

from . import __version__
from .checks import CATEGORIES, REGISTRY
from .config import Config, ConfigError, load_config
from .fixers import SUPPORTED_LICENSES, FixOptions, apply_plan, plan_fixes
from .repo import Repo
from .report import render_json, render_markdown, render_text
from .runner import run_checks
from .sarif import render_sarif

EXIT_OK = 0
EXIT_BELOW_THRESHOLD = 1
EXIT_USAGE = 2


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ossdoctor",
        description="Check an open source repository for the files and automation maintainers rely on.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("path", nargs="?", default=".", help="repository to inspect (default: current directory)")
        p.add_argument("--only", type=_csv, metavar="IDS", help="comma-separated check ids to run")
        p.add_argument("--disable", type=_csv, default=[], metavar="IDS", help="comma-separated check ids to skip")

    check = sub.add_parser("check", help="report on the repository (default command)")
    add_common(check)
    check.add_argument(
        "-f",
        "--format",
        choices=("text", "markdown", "json", "sarif"),
        default="text",
        help="output format; sarif is for GitHub code scanning (default: text)",
    )
    check.add_argument("-o", "--output", metavar="FILE", help="write the report to FILE instead of standard output")
    check.add_argument("-v", "--verbose", action="store_true", help="explain how to fix each failure")
    check.add_argument(
        "--fail-under",
        type=int,
        metavar="SCORE",
        help="exit with status 1 if the score is below SCORE (overrides config)",
    )

    fix = sub.add_parser("fix", help="generate missing files for failing checks")
    add_common(fix)
    fix.add_argument("-n", "--dry-run", action="store_true", help="show what would be created without writing")
    fix.add_argument(
        "--license",
        default="MIT",
        metavar="SPDX",
        help=f"license to generate when none exists: {', '.join(SUPPORTED_LICENSES)} (default: MIT)",
    )
    fix.add_argument("--author", help="copyright holder (default: git user.name)")
    fix.add_argument("--email", help="contact address for SECURITY.md and CODE_OF_CONDUCT.md (default: git user.email)")
    fix.add_argument("--github-user", metavar="NAME", help="GitHub user or team for CODEOWNERS")

    sub.add_parser("list", help="list all available checks")
    return parser


def _prepare(args: argparse.Namespace) -> tuple[Repo, Config]:
    repo = Repo.load(args.path)
    config = load_config(repo.root)
    config.disable = [*config.disable, *args.disable]
    unknown = sorted({*config.disable, *(args.only or [])} - set(REGISTRY))
    if unknown:
        raise ConfigError(f"unknown check id(s): {', '.join(unknown)}. Run `ossdoctor list` to see them.")
    return repo, config


def _cmd_check(args: argparse.Namespace) -> int:
    repo, config = _prepare(args)
    report = run_checks(repo, config, only=args.only)
    target = open(args.output, "w", encoding="utf-8", newline="\n") if args.output else contextlib.nullcontext(sys.stdout)
    with target as out:
        if args.format == "json":
            out.write(render_json(report))
        elif args.format == "markdown":
            out.write(render_markdown(report))
        elif args.format == "sarif":
            out.write(render_sarif(report))
        else:
            out.write(render_text(report, out, verbose=args.verbose))

    threshold = args.fail_under if args.fail_under is not None else config.fail_under
    if threshold is not None and report.score < threshold:
        print(f"ossdoctor: score {report.score} is below the required {threshold}", file=sys.stderr)
        return EXIT_BELOW_THRESHOLD
    return EXIT_OK


def _cmd_fix(args: argparse.Namespace) -> int:
    repo, config = _prepare(args)
    report = run_checks(repo, config, only=args.only)
    opts = FixOptions(license=args.license, author=args.author, email=args.email, github_user=args.github_user)
    plan = plan_fixes(repo, report, opts)

    if not plan.files and not plan.skipped:
        print("Nothing to fix.")
        return EXIT_OK
    verb = "Would create" if args.dry_run else "Created"
    for path in plan.files:
        print(f"{verb} {path}")
    if not args.dry_run:
        apply_plan(repo.root, plan)
    for check_id, reason in plan.skipped.items():
        print(f"Skipped {check_id}: {reason}")
    for note in plan.notes:
        print(f"Note: {note}")
    if plan.files and not args.dry_run:
        print("Review the generated files and fill in the project-specific parts before committing.")
    return EXIT_OK


def _cmd_list(args: argparse.Namespace) -> int:
    width = max(len(c.id) for c in REGISTRY.values())
    for category in CATEGORIES:
        print(category)
        for c in REGISTRY.values():
            if c.category == category:
                fix = " [fixable]" if c.fixable else ""
                print(f"  {c.id.ljust(width)}  {c.level.value:<11}  {c.title}{fix}")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    # `ossdoctor` and `ossdoctor PATH` behave like `ossdoctor check ...`.
    if not argv or argv[0] not in {"check", "fix", "list", "-h", "--help", "--version"}:
        argv.insert(0, "check")
    args = parser.parse_args(argv)
    handlers = {"check": _cmd_check, "fix": _cmd_fix, "list": _cmd_list}
    try:
        return handlers[args.command](args)
    except (ConfigError, OSError) as exc:
        print(f"ossdoctor: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
