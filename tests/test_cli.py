from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from ossdoctor.cli import main

from .conftest import HEALTHY


def test_default_command_is_check(make_repo, capsys):
    root = make_repo(HEALTHY)
    assert main([str(root)]) == 0
    assert "Score: 100/100" in capsys.readouterr().out


def test_json_output(make_repo, capsys):
    root = make_repo({"README.md": "# x\n"})
    assert main(["check", str(root), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["score"] == 14
    by_id = {r["id"]: r for r in data["results"]}
    assert by_id["readme"]["status"] == "fail"
    assert by_id["readme"]["fixable"] is True
    assert data["summary"]["fail"] + data["summary"]["pass"] + data["summary"]["skip"] == len(data["results"])


def test_markdown_output_lists_fixes(make_repo, capsys):
    root = make_repo({})
    main(["check", str(root), "-f", "markdown"])
    out = capsys.readouterr().out
    assert out.startswith("## ossdoctor report: 15/100")
    assert "### How to fix" in out
    assert "(`license`)" in out


def test_fail_under_flag(make_repo, capsys):
    root = make_repo({})
    assert main(["check", str(root), "--fail-under", "50"]) == 1
    assert "below the required 50" in capsys.readouterr().err


def test_fail_under_from_pyproject(make_repo):
    root = make_repo({"pyproject.toml": "[tool.ossdoctor]\nfail-under = 50\n"})
    assert main(["check", str(root)]) == 1
    assert main(["check", str(root), "--fail-under", "0"]) == 0


def test_disable_from_config_and_flag(make_repo, capsys):
    root = make_repo({".ossdoctor.toml": 'disable = ["readme"]\n'})
    main(["check", str(root), "--disable", "license", "-f", "json"])
    by_id = {r["id"]: r for r in json.loads(capsys.readouterr().out)["results"]}
    assert by_id["readme"]["status"] == "skip"
    assert by_id["license"]["status"] == "skip"


def test_only(make_repo, capsys):
    main(["check", str(make_repo({})), "--only", "readme,license", "-f", "json"])
    assert [r["id"] for r in json.loads(capsys.readouterr().out)["results"]] == ["readme", "license"]


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ('disable = ["nope"]\n', "unknown check id(s): nope"),
        ("fail-under = 120\n", "`fail-under` must be an integer"),
        ("colour = true\n", "unknown key(s): colour"),
        ("disable = \n", "could not parse"),
    ],
)
def test_config_errors(make_repo, capsys, config, message):
    root = make_repo({".ossdoctor.toml": config})
    assert main(["check", str(root)]) == 2
    assert message in capsys.readouterr().err


def test_missing_directory(tmp_path, capsys):
    assert main(["check", str(tmp_path / "nope")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "no-secret-files" in out
    assert "[fixable]" in out


def test_no_color_plain_output(make_repo, capsys, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    main(["check", str(make_repo({}))])
    assert "\033[" in capsys.readouterr().out
    monkeypatch.setenv("NO_COLOR", "1")
    main(["check", str(make_repo({}))])
    assert "\033[" not in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_repo_respects_gitignore(make_repo, capsys):
    root = make_repo({".gitignore": ".env\nbig.bin\n", ".env": "SECRET=1", "big.bin": b"\0" * (6 * 1024 * 1024)})
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    main(["check", str(root), "--only", "no-secret-files,no-large-files", "-f", "json"])
    results = json.loads(capsys.readouterr().out)["results"]
    assert [r["status"] for r in results] == ["pass", "pass"]
