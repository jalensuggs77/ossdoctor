"""Score badges for READMEs, and keeping them current.

Badges are shields.io static badges. A static badge cannot update itself, so
:func:`update_badges` rewrites the score in a file that already contains one;
run it (or ``ossdoctor badge --update README.md --check`` in CI) to keep the
number honest.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from . import PROJECT_URL

ALT = "ossdoctor score"
STYLES = ("flat", "flat-square", "plastic", "for-the-badge")
FORMATS = ("markdown", "rst", "html", "url")

# A shields.io badge made by this module, with any query string (such as
# ?style=...) the author added.
BADGE_URL = re.compile(r"https://img\.shields\.io/badge/ossdoctor-(\d{1,3})%2F100-([a-z]+)((?:\?[^\s)\"'<>]*)?)")


def color(score: int) -> str:
    if score >= 90:
        return "brightgreen"
    if score >= 75:
        return "green"
    if score >= 60:
        return "yellow"
    if score >= 40:
        return "orange"
    return "red"


def badge_url(score: int, style: str = "flat") -> str:
    query = "" if style == "flat" else "?style=" + quote(style)
    return f"https://img.shields.io/badge/ossdoctor-{score}%2F100-{color(score)}{query}"


def render_badge(score: int, fmt: str = "markdown", style: str = "flat") -> str:
    url = badge_url(score, style)
    if fmt == "url":
        return url
    if fmt == "rst":
        return f".. image:: {url}\n   :target: {PROJECT_URL}\n   :alt: {ALT}"
    if fmt == "html":
        return f'<a href="{PROJECT_URL}"><img src="{url}" alt="{ALT}"></a>'
    return f"[![{ALT}]({url})]({PROJECT_URL})"


def update_badges(text: str, score: int) -> tuple[str, int, list[int]]:
    """Return ``text`` with every ossdoctor badge set to ``score``.

    Also returns how many badges were found and the scores they showed.
    """
    previous: list[int] = []

    def replace(match: re.Match[str]) -> str:
        previous.append(int(match.group(1)))
        return f"https://img.shields.io/badge/ossdoctor-{score}%2F100-{color(score)}{match.group(3)}"

    new_text, count = BADGE_URL.subn(replace, text)
    return new_text, count, previous
