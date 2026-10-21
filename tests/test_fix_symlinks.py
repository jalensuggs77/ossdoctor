from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from ossdoctor.cli import main
from ossdoctor.config import load_config
from ossdoctor.fixers import FixOptions, FixPlan, UnsafePathError, apply_plan, plan_fixes, unsafe_reason
from ossdoctor.repo import Repo
from ossdoctor.runner import run_checks


def symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available on this system")


@pytest.fixture
def repo_and_outside(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    return repo, outside


def _files(directory: Path) -> list[str]:
    return sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file())


def test_symlinked_directory_is_not_followed(repo_and_outside, capsys):
    repo, outside = repo_and_outside
    symlink(repo / ".github", outside)
    assert main(["fix", str(repo), "--github-user", "ada"]) == 0
    out = capsys.readouterr().out
    assert _files(outside) == ["keep.txt"]
    assert "not creating .github/CODEOWNERS: .github is a symlink" in out
    assert "Skipped issue-templates" in out


def test_other_files_are_still_created(repo_and_outside):
    repo, outside = repo_and_outside
    symlink(repo / ".github", outside)
    main(["fix", str(repo)])
    assert (repo / "LICENSE").is_file()
    assert (repo / "CONTRIBUTING.md").is_file()
    assert _files(outside) == ["keep.txt"]


def test_dry_run_reports_the_refusal(repo_and_outside, capsys):
    repo, outside = repo_and_outside
    symlink(repo / ".github", outside)
    main(["fix", str(repo), "--dry-run", "--only", "security-policy,codeowners", "--github-user", "ada"])
    out = capsys.readouterr().out
    assert "Would create SECURITY.md" in out
    assert "not creating .github/CODEOWNERS" in out
    assert _files(outside) == ["keep.txt"]


def test_dangling_symlink_is_left_alone(repo_and_outside, capsys):
    repo, outside = repo_and_outside
    symlink(repo / "SECURITY.md", outside / "stolen.md")
    assert not (outside / "stolen.md").exists()
    assert main(["fix", str(repo), "--only", "security-policy,gitignore"]) == 0
    out = capsys.readouterr().out
    assert "SECURITY.md is a symlink" in out
    assert not (outside / "stolen.md").exists()
    assert (repo / ".gitignore").is_file(), "an unrelated fix must not be lost to the refusal"


def test_dangling_symlink_does_not_count_as_a_file(repo_and_outside):
    repo, outside = repo_and_outside
    symlink(repo / "SECURITY.md", outside / "missing.md")
    assert "SECURITY.md" not in Repo.load(repo).files


def test_dangling_symlink_in_a_git_checkout(repo_and_outside, capsys):
    if shutil.which("git") is None:
        pytest.skip("git not installed")
    import subprocess

    repo, outside = repo_and_outside
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    symlink(repo / "SECURITY.md", outside / "stolen.md")
    main(["fix", str(repo), "--only", "security-policy"])
    assert "SECURITY.md is a symlink" in capsys.readouterr().out
    assert not (outside / "stolen.md").exists()


def test_symlink_to_directory_inside_the_repo_is_also_refused(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    symlink(repo / ".github", repo / "docs")
    assert unsafe_reason(repo, ".github/CODEOWNERS") == ".github is a symlink"
    main(["fix", str(repo), "--only", "codeowners", "--github-user", "ada"])
    assert not (repo / "docs" / "CODEOWNERS").exists()


def test_symlink_deeper_in_the_path(repo_and_outside):
    repo, outside = repo_and_outside
    (repo / ".github").mkdir()
    symlink(repo / ".github" / "ISSUE_TEMPLATE", outside)
    main(["fix", str(repo), "--only", "issue-templates"])
    assert _files(outside) == ["keep.txt"]


def test_apply_is_all_or_nothing(repo_and_outside):
    repo, outside = repo_and_outside
    symlink(repo / ".github", outside)
    plan = FixPlan(files={"SAFE.md": "safe\n", ".github/CODEOWNERS": "* @ada\n"})
    with pytest.raises(UnsafePathError, match=r"\.github/CODEOWNERS: \.github is a symlink"):
        apply_plan(repo, plan)
    assert not (repo / "SAFE.md").exists(), "nothing may be written when any path is refused"
    assert _files(outside) == ["keep.txt"]


def test_symlink_swapped_in_after_planning(repo_and_outside):
    repo, outside = repo_and_outside
    (repo / ".github").mkdir()
    loaded = Repo.load(repo)
    report = run_checks(loaded, load_config(repo), only=["codeowners"])
    plan = plan_fixes(loaded, report, FixOptions(github_user="ada"))
    assert list(plan.files) == [".github/CODEOWNERS"]

    # Between planning and applying, the directory is replaced by a link.
    shutil.rmtree(repo / ".github")
    symlink(repo / ".github", outside)
    with pytest.raises(UnsafePathError):
        apply_plan(repo, plan)
    assert _files(outside) == ["keep.txt"]


def test_cli_reports_unsafe_path_as_an_error(repo_and_outside, monkeypatch, capsys):
    repo, _ = repo_and_outside

    def refuse(root, plan):
        raise UnsafePathError("refusing to create X: X is a symlink")

    monkeypatch.setattr("ossdoctor.cli.apply_plan", refuse)
    assert main(["fix", str(repo), "--only", "gitignore"]) == 2
    assert "ossdoctor: error: refusing to create X" in capsys.readouterr().err


@pytest.mark.parametrize("rel", ["../escape.md", "a/../../escape.md", "/etc/escape.md", ""])
def test_paths_that_leave_the_repository_are_refused(tmp_path, rel):
    assert unsafe_reason(tmp_path, rel) == "path is not relative to the repository"


def test_plain_nested_paths_are_fine(tmp_path):
    assert unsafe_reason(tmp_path, ".github/ISSUE_TEMPLATE/bug_report.yml") is None
    (tmp_path / ".github").mkdir()
    assert unsafe_reason(tmp_path, ".github/CODEOWNERS") is None


def test_repository_reached_through_a_symlink_still_works(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    symlink(alias, real)
    assert main(["fix", str(alias), "--only", "gitignore"]) == 0
    assert (real / ".gitignore").is_file()


@pytest.mark.skipif(os.name != "nt", reason="junctions only exist on Windows")
def test_windows_junction_is_refused(repo_and_outside):  # pragma: no cover
    import subprocess

    repo, outside = repo_and_outside
    subprocess.run(["cmd", "/c", "mklink", "/J", str(repo / ".github"), str(outside)], check=True, capture_output=True)
    assert unsafe_reason(repo, ".github/CODEOWNERS") is not None
