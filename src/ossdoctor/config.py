"""Loading ``[tool.ossdoctor]`` from pyproject.toml or a standalone ``.ossdoctor.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = ".ossdoctor.toml"


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    disable: list[str] = field(default_factory=list)
    fail_under: int | None = None
    large_file_mb: float = 5.0
    ignore_paths: list[str] = field(default_factory=list)
    source: str | None = None


def _str_list(table: dict, key: str, source: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{source}: `{key}` must be a list of strings")
    return value


def load_config(root: Path) -> Config:
    standalone = root / CONFIG_FILE
    pyproject = root / "pyproject.toml"
    table: dict | None = None
    source = None
    try:
        if standalone.is_file():
            table = tomllib.loads(standalone.read_text(encoding="utf-8"))
            source = CONFIG_FILE
        elif pyproject.is_file():
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            table = data.get("tool", {}).get("ossdoctor")
            source = "pyproject.toml [tool.ossdoctor]"
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"could not parse {source or 'config'}: {exc}") from exc

    if table is None:
        return Config()

    known = {"disable", "fail-under", "large-file-mb", "ignore-paths"}
    unknown = sorted(set(table) - known)
    if unknown:
        raise ConfigError(f"{source}: unknown key(s): {', '.join(unknown)}")

    fail_under = table.get("fail-under")
    if fail_under is not None and (not isinstance(fail_under, int) or not 0 <= fail_under <= 100):
        raise ConfigError(f"{source}: `fail-under` must be an integer from 0 to 100")

    large = table.get("large-file-mb", 5.0)
    if not isinstance(large, (int, float)) or large <= 0:
        raise ConfigError(f"{source}: `large-file-mb` must be a positive number")

    return Config(
        disable=_str_list(table, "disable", source),
        fail_under=fail_under,
        large_file_mb=float(large),
        ignore_paths=_str_list(table, "ignore-paths", source),
        source=source,
    )
