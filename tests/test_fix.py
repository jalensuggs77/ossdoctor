from __future__ import annotations

from ossdoctor.checks import Status
from ossdoctor.cli import main
from ossdoctor.config import load_config
from ossdoctor.repo import Repo
from ossdoctor.runner import run_checks


def _score(root) -> int:
    return run_checks(Repo.load(root), load_config(root)).score


def test_fix_creates_files_and_raises_score(make_repo, capsys):
    root = make_repo({"pyproject.toml": '[project]\nname = "widget"\n', "src/widget.py": ""})
    before = _score(root)
    assert main(["fix", str(root), "--author", "Ada", "--email", "ada@example.com", "--github-user", "@ada"]) == 0
    out = capsys.readouterr().out
    assert "Created LICENSE" in out
    assert "Created .github/CODEOWNERS" in out

    assert "Copyright (c) " in (root / "LICENSE").read_text()
    assert "Ada" in (root / "LICENSE").read_text()
    assert "ada@example.com" in (root / "SECURITY.md").read_text()
    assert "# widget" in (root / "README.md").read_text()
    assert (root / ".github/CODEOWNERS").read_text().endswith("* @ada\n")
    assert 'package-ecosystem: "pip"' in (root / ".github/dependabot.yml").read_text()
    assert "__pycache__/" in (root / ".gitignore").read_text()

    report = run_checks(Repo.load(root), load_config(root))
    still_failing = {r.check.id for r in report.by_status(Status.FAIL)}
    # Only checks that need real work from the maintainer remain.
    assert still_failing == {"ci", "tests"}
    assert report.score > before


def test_dry_run_writes_nothing(make_repo, capsys):
    root = make_repo({})
    main(["fix", str(root), "--dry-run"])
    assert "Would create LICENSE" in capsys.readouterr().out
    assert not (root / "LICENSE").exists()


def test_fix_never_overwrites(make_repo, capsys):
    root = make_repo({"README.md": "# mine\n"})
    main(["fix", str(root), "--only", "readme"])
    assert "README exists but is nearly empty" in capsys.readouterr().out
    assert (root / "README.md").read_text() == "# mine\n"


def test_unknown_license_is_skipped(make_repo, capsys):
    root = make_repo({})
    main(["fix", str(root), "--only", "license", "--license", "GPL-3.0"])
    assert "no built-in template" in capsys.readouterr().out
    assert not (root / "LICENSE").exists()


def test_license_choice_is_case_insensitive(make_repo, capsys):
    root = make_repo({})
    main(["fix", str(root), "--only", "license", "--license", "bsd-3-clause", "--author", "Ada"])
    assert "Neither the name of the copyright holder" in (root / "LICENSE").read_text()


def test_placeholders_reported_when_identity_unknown(make_repo, capsys, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = make_repo({})
    main(["fix", str(root), "--only", "security-policy,license"])
    out = capsys.readouterr().out
    assert "[INSERT CONTACT EMAIL]" in out
    assert "[INSERT COPYRIGHT HOLDER]" in out


def test_nothing_to_fix(make_repo, capsys):
    root = make_repo({".gitignore": "x\n"})
    main(["fix", str(root), "--only", "gitignore"])
    assert capsys.readouterr().out == "Nothing to fix.\n"
