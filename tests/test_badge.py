from __future__ import annotations

import json

import pytest

from ossdoctor import PROJECT_URL
from ossdoctor.badge import badge_url, color, render_badge, update_badges
from ossdoctor.cli import main

from .conftest import HEALTHY

URL_100 = "https://img.shields.io/badge/ossdoctor-100%2F100-brightgreen"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "brightgreen"),
        (90, "brightgreen"),
        (89, "green"),
        (75, "green"),
        (74, "yellow"),
        (60, "yellow"),
        (59, "orange"),
        (40, "orange"),
        (39, "red"),
        (0, "red"),
    ],
)
def test_color_thresholds(score, expected):
    assert color(score) == expected


def test_badge_url_escapes_the_slash_and_adds_style():
    assert badge_url(86) == "https://img.shields.io/badge/ossdoctor-86%2F100-green"
    assert badge_url(86, "for-the-badge").endswith("-green?style=for-the-badge")


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        ("markdown", f"[![ossdoctor score]({URL_100})]({PROJECT_URL})"),
        ("html", f'<a href="{PROJECT_URL}"><img src="{URL_100}" alt="ossdoctor score"></a>'),
        ("rst", f".. image:: {URL_100}\n   :target: {PROJECT_URL}\n   :alt: ossdoctor score"),
        ("url", URL_100),
    ],
)
def test_render_formats(fmt, expected):
    assert render_badge(100, fmt) == expected


def test_update_keeps_style_and_surrounding_text():
    url = "https://img.shields.io/badge/ossdoctor-42%2F100-orange?style=flat-square"
    text = f"# x\n\n[![ossdoctor score]({url})]({PROJECT_URL}) other\n"
    new, count, previous = update_badges(text, 95)
    assert count == 1
    assert previous == [42]
    assert new == text.replace("42%2F100-orange?style=flat-square", "95%2F100-brightgreen?style=flat-square")


def test_update_handles_several_badges_and_formats():
    text = render_badge(10, "markdown") + "\n\n" + render_badge(20, "rst") + "\n" + render_badge(30, "html")
    new, count, previous = update_badges(text, 77)
    assert (count, previous) == (3, [10, 20, 30])
    assert new.count("77%2F100-green") == 3


def test_update_ignores_other_badges():
    text = "![PyPI](https://img.shields.io/pypi/v/ossdoctor) ![x](https://img.shields.io/badge/license-MIT-blue)"
    assert update_badges(text, 50) == (text, 0, [])


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_prints_badge_for_the_score(make_repo, capsys):
    assert main(["badge", str(make_repo(HEALTHY))]) == 0
    assert capsys.readouterr().out == render_badge(100) + "\n"


def test_cli_respects_config(make_repo, capsys):
    root = make_repo({".ossdoctor.toml": 'disable = ["readme", "license"]\n'})
    main(["badge", str(root), "-f", "url"])
    disabled = capsys.readouterr().out.strip()
    main(["check", str(root), "-f", "json"])
    assert disabled == badge_url(json.loads(capsys.readouterr().out)["score"])


def test_cli_update_rewrites_file(make_repo, capsys):
    root = make_repo({**HEALTHY, "README.md": HEALTHY["README.md"] + "\n" + render_badge(12) + "\n"})
    readme = root / "README.md"
    assert main(["badge", str(root), "--update", str(readme)]) == 0
    assert "badge updated from 12/100 to 100/100" in capsys.readouterr().out
    assert render_badge(100) in readme.read_text(encoding="utf-8")
    assert main(["badge", str(root), "--update", str(readme)]) == 0
    assert "badge is up to date (100/100)" in capsys.readouterr().out


def test_cli_update_preserves_line_endings(make_repo):
    root = make_repo(HEALTHY)
    readme = root / "README.md"
    readme.write_bytes(HEALTHY["README.md"].replace("\n", "\r\n").encode() + render_badge(1).encode() + b"\r\n")
    main(["badge", str(root), "--update", str(readme)])
    data = readme.read_bytes()
    assert b"100%2F100" in data
    assert data.count(b"\r\n") == data.count(b"\n")


def test_cli_check_reports_stale_badge_without_writing(make_repo, capsys):
    root = make_repo({**HEALTHY, "README.md": HEALTHY["README.md"] + render_badge(50) + "\n"})
    readme = root / "README.md"
    before = readme.read_text(encoding="utf-8")
    assert main(["badge", str(root), "--update", str(readme), "--check"]) == 1
    err = capsys.readouterr().err
    assert "badge shows 50/100 but the score is 100/100" in err
    assert readme.read_text(encoding="utf-8") == before


def test_cli_check_passes_when_current(make_repo):
    root = make_repo({**HEALTHY, "README.md": HEALTHY["README.md"] + render_badge(100) + "\n"})
    assert main(["badge", str(root), "--update", str(root / "README.md"), "--check"]) == 0


def test_cli_update_without_badge_is_an_error(make_repo, capsys):
    root = make_repo(HEALTHY)
    assert main(["badge", str(root), "--update", str(root / "README.md")]) == 2
    assert "no ossdoctor badge found" in capsys.readouterr().err


def test_cli_check_requires_update(make_repo, capsys):
    assert main(["badge", str(make_repo({})), "--check"]) == 2
    assert "--check needs --update" in capsys.readouterr().err


def test_cli_update_missing_file(make_repo, capsys):
    root = make_repo({})
    assert main(["badge", str(root), "--update", str(root / "NOPE.md")]) == 2
    assert "ossdoctor: error:" in capsys.readouterr().err
