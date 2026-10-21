"""Running the registered checks and scoring the result."""

from __future__ import annotations

from dataclasses import dataclass

from .checks import CATEGORIES, REGISTRY, Check, Outcome, Status
from .config import Config
from .repo import Repo


@dataclass(frozen=True)
class Result:
    check: Check
    outcome: Outcome

    @property
    def status(self) -> Status:
        return self.outcome.status


@dataclass
class Report:
    repo: Repo
    results: list[Result]

    def by_status(self, status: Status) -> list[Result]:
        return [r for r in self.results if r.status is status]

    @property
    def score(self) -> int:
        """Weighted share of applicable checks that pass, from 0 to 100."""
        applicable = [r for r in self.results if r.status is not Status.SKIP]
        total = sum(r.check.level.weight for r in applicable)
        if not total:
            return 100
        got = sum(r.check.level.weight for r in applicable if r.status is Status.PASS)
        return round(100 * got / total)

    @property
    def fixable(self) -> list[Result]:
        return [r for r in self.by_status(Status.FAIL) if r.check.fixable]


def run_checks(repo: Repo, config: Config, only: list[str] | None = None) -> Report:
    order = {c: i for i, c in enumerate(CATEGORIES)}
    checks = sorted(REGISTRY.values(), key=lambda c: order[c.category])
    results = []
    for c in checks:
        if only is not None and c.id not in only:
            continue
        if c.id in config.disable:
            results.append(Result(c, Outcome(Status.SKIP, "disabled in config")))
            continue
        try:
            outcome = c.run(repo, config)
        except OSError as exc:
            outcome = Outcome(Status.FAIL, f"could not read files: {exc}")
        results.append(Result(c, outcome))
    return Report(repo, results)
