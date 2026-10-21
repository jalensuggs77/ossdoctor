"""Rendering a :class:`~ossdoctor.runner.Report` as SARIF 2.1.0.

SARIF is the format GitHub code scanning (and most other code analysis
dashboards) ingest. Every failed check becomes one result per affected file.
A check that fails because a file is missing points at the path where that
file belongs, since code scanning requires every result to have a location.
"""

from __future__ import annotations

import hashlib
import json

from . import __version__
from .checks import Check, Finding, Level, Status
from .runner import Report

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
INFORMATION_URI = "https://github.com/jalensuggs77/ossdoctor"
SRCROOT = "%SRCROOT%"

_LEVELS = {Level.REQUIRED: "error", Level.RECOMMENDED: "warning", Level.OPTIONAL: "note"}
# GitHub buckets security-severity into critical (9+), high (7+), medium (4+) and low.
_SECURITY_SEVERITY = {Level.REQUIRED: "8.0", Level.RECOMMENDED: "5.0", Level.OPTIONAL: "2.0"}


def _rule_name(check_id: str) -> str:
    return "".join(part.capitalize() for part in check_id.split("-"))


def _rule(check: Check) -> dict:
    # The "security" tag (from the category) is what GitHub uses to list a rule as a security alert.
    properties: dict = {"tags": [check.category.lower(), "open-source"], "precision": "very-high"}
    if check.category == "Security":
        properties["security-severity"] = _SECURITY_SEVERITY[check.level]
    markdown = f"{check.hint}\n\nLevel: **{check.level.value}**."
    if check.fixable:
        markdown += "\n\nRun `ossdoctor fix` to generate the missing file."
    return {
        "id": check.id,
        "name": _rule_name(check.id),
        "shortDescription": {"text": check.title},
        "fullDescription": {"text": check.hint},
        "help": {"text": check.hint, "markdown": markdown},
        "helpUri": f"{INFORMATION_URI}#checks",
        "defaultConfiguration": {"level": _LEVELS[check.level]},
        "properties": properties,
    }


def _fingerprint(rule_id: str, uri: str) -> str:
    # Supplied up front so uploaders don't try to hash lines of files that
    # don't exist (the location of a missing file).
    digest = hashlib.sha256(f"{rule_id}\0{uri}".encode()).hexdigest()[:16]
    return f"{digest}:1"


def _sentence(text: str) -> str:
    return text if text.endswith(".") else text + "."


def report_to_sarif(report: Report) -> dict:
    checks = [r.check for r in report.results]
    rule_index = {c.id: i for i, c in enumerate(checks)}
    prefix = report.repo.path_in_git
    base = report.repo.git_toplevel or report.repo.root

    results = []
    for r in report.by_status(Status.FAIL):
        findings = r.outcome.findings or (Finding(r.check.location, r.outcome.detail[:1].upper() + r.outcome.detail[1:]),)
        for finding in findings:
            uri = prefix + finding.path
            results.append(
                {
                    "ruleId": r.check.id,
                    "ruleIndex": rule_index[r.check.id],
                    "level": _LEVELS[r.check.level],
                    "message": {"text": _sentence(finding.message)},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri, "uriBaseId": SRCROOT},
                                "region": {"startLine": 1},
                            }
                        }
                    ],
                    "partialFingerprints": {"primaryLocationLineHash": _fingerprint(r.check.id, uri)},
                }
            )

    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ossdoctor",
                        "version": __version__,
                        "semanticVersion": __version__,
                        "informationUri": INFORMATION_URI,
                        "rules": [_rule(c) for c in checks],
                    }
                },
                "originalUriBaseIds": {SRCROOT: {"uri": base.as_uri() + "/"}},
                "results": results,
                "properties": {"score": report.score},
            }
        ],
    }


def render_sarif(report: Report) -> str:
    return json.dumps(report_to_sarif(report), indent=2, ensure_ascii=False) + "\n"
