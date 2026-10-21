from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from ossdoctor import __version__
from ossdoctor.checks import REGISTRY
from ossdoctor.cli import main
from ossdoctor.config import load_config
from ossdoctor.repo import Repo
from ossdoctor.runner import run_checks
from ossdoctor.sarif import report_to_sarif

from .conftest import HEALTHY


def _sarif(root, only=None) -> dict:
    repo = Repo.load(root)
    return report_to_sarif(run_checks(repo, load_config(repo.root), only=only))


def _results(doc: dict) -> list[dict]:
    return doc["runs"][0]["results"]


def _uri(result: dict) -> str:
    return result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]


def test_document_shape(make_repo):
    doc = _sarif(make_repo({}))
    assert doc["version"] == "2.1.0"
    assert doc["$schema"].endswith("sarif-2.1.0.json")
    (run,) = doc["runs"]
    driver = run["tool"]["driver"]
    assert driver["name"] == "ossdoctor"
    assert driver["semanticVersion"] == __version__
    assert sorted(r["id"] for r in driver["rules"]) == sorted(REGISTRY)
    assert run["originalUriBaseIds"]["%SRCROOT%"]["uri"].startswith("file://")
    assert run["originalUriBaseIds"]["%SRCROOT%"]["uri"].endswith("/")


def test_healthy_repo_has_no_results(make_repo):
    doc = _sarif(make_repo(HEALTHY))
    assert _results(doc) == []
    assert doc["runs"][0]["properties"]["score"] == 100


def test_missing_file_points_at_expected_location(make_repo):
    (result,) = _results(_sarif(make_repo({}), only=["security-policy"]))
    assert result["ruleId"] == "security-policy"
    assert result["level"] == "warning"
    assert _uri(result) == "SECURITY.md"
    assert result["message"]["text"] == "No SECURITY policy found."
    assert result["locations"][0]["physicalLocation"]["region"] == {"startLine": 1}


def test_one_result_per_secret_file(make_repo):
    root = make_repo({".env": "A=1", "deploy/id_rsa": "x", "README.md": "# x\n"})
    results = _results(_sarif(root, only=["no-secret-files"]))
    assert sorted(_uri(r) for r in results) == [".env", "deploy/id_rsa"]
    assert all(r["level"] == "error" for r in results)
    assert results[0]["message"]["text"].endswith("should not be committed.")


def test_file_findings_keep_their_case(make_repo):
    root = make_repo({"readme.md": "# demo\n"})
    (result,) = _results(_sarif(root, only=["readme-sections"]))
    assert _uri(result) == "readme.md"
    assert result["message"]["text"].startswith("readme.md is missing section")


def test_lockfile_points_at_manifest(make_repo):
    (result,) = _results(_sarif(make_repo({"package.json": "{}"}), only=["lockfile"]))
    assert _uri(result) == "package.json"


def test_rule_index_matches_rule(make_repo):
    doc = _sarif(make_repo({".env": "x"}))
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    for result in _results(doc):
        assert rules[result["ruleIndex"]]["id"] == result["ruleId"]


def test_security_rules_carry_severity(make_repo):
    rules = {r["id"]: r for r in _sarif(make_repo({}))["runs"][0]["tool"]["driver"]["rules"]}
    assert rules["no-secret-files"]["properties"]["security-severity"] == "8.0"
    assert "security" in rules["no-secret-files"]["properties"]["tags"]
    assert "security-severity" not in rules["readme"]["properties"]


def test_fingerprints_are_stable_and_distinct(make_repo):
    root = make_repo({".env": "x", ".env.local": "y"})
    first = [r["partialFingerprints"]["primaryLocationLineHash"] for r in _results(_sarif(root))]
    second = [r["partialFingerprints"]["primaryLocationLineHash"] for r in _results(_sarif(root))]
    assert first == second
    assert len(set(first)) == len(first)


def test_disabled_checks_produce_no_results(make_repo):
    root = make_repo({".ossdoctor.toml": 'disable = ["license"]\n'})
    assert "license" not in {r["ruleId"] for r in _results(_sarif(root))}


def test_cli_writes_sarif_to_file(make_repo, tmp_path, capsys):
    root = make_repo({})
    out = tmp_path / "out" / "report.sarif"
    out.parent.mkdir()
    assert main(["check", str(root), "-f", "sarif", "-o", str(out)]) == 0
    assert capsys.readouterr().out == ""
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == "2.1.0"


def test_cli_output_error_is_reported(make_repo, tmp_path, capsys):
    assert main(["check", str(make_repo({})), "-o", str(tmp_path / "missing-dir" / "x.sarif")]) == 2
    assert "ossdoctor: error:" in capsys.readouterr().err


def test_fail_under_still_applies_with_sarif(make_repo, tmp_path):
    root = make_repo({})
    assert main(["check", str(root), "-f", "sarif", "-o", str(tmp_path / "r.sarif"), "--fail-under", "90"]) == 1


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_uris_are_relative_to_git_root(make_repo):
    root = make_repo({"packages/app/package.json": "{}", "packages/app/.env": "x"})
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    doc = _sarif(root / "packages" / "app", only=["no-secret-files", "security-policy"])
    assert sorted(_uri(r) for r in _results(doc)) == ["packages/app/.env", "packages/app/SECURITY.md"]
    assert doc["runs"][0]["originalUriBaseIds"]["%SRCROOT%"]["uri"] == root.resolve().as_uri() + "/"
