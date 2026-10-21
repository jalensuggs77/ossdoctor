# Contributing to ossdoctor

Thanks for taking the time to contribute! Bug reports, new checks, better
templates and documentation fixes are all welcome.

## Reporting bugs and requesting features

Search the [existing issues](https://github.com/jalensuggs77/ossdoctor/issues) first.
If nothing matches, open a new issue using one of the templates. For a false
positive or false negative, include the file layout that triggers it (the
output of `git ls-files` is ideal).

Please report security vulnerabilities privately as described in
[SECURITY.md](SECURITY.md), not in public issues.

## Development setup

ossdoctor needs Python 3.11 or newer and has no runtime dependencies.

```sh
git clone https://github.com/jalensuggs77/ossdoctor
cd ossdoctor
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Before opening a pull request, run:

```sh
pytest
ruff check .
ruff format .
ossdoctor          # the project must keep a score of 100
```

## Adding a check

1. Add a function to `src/ossdoctor/checks.py` decorated with `@check(...)`.
   Give it a short kebab-case id, a category from `CATEGORIES`, a level and a
   one-sentence hint that tells the user *how* to fix the problem.
2. Return `passed(detail)`, `failed(detail)` or `skipped(detail)`. Use
   `skipped` when the check does not apply to the repository (for example a
   lockfile check in a project with no package manager).
3. If the fix is a file that can be generated, add a template to
   `templates.py`, register a fixer in `fixers.py` with `@fixer("<id>")`, and
   pass `fixable=True` to `@check`.
4. Add tests in `tests/` for both the passing and failing cases.
5. Mention the change under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).

Checks must be fast, must work offline and must never modify the repository.

## Pull requests

- Keep each pull request focused on one change.
- Explain what changed and why, and link the related issue.
- New behaviour needs tests.

## Releasing (maintainers)

1. Update `__version__` in `src/ossdoctor/__init__.py` and move the
   `[Unreleased]` notes in `CHANGELOG.md` under the new version.
2. Commit, then tag and push: `git tag v0.2.0 && git push origin v0.2.0`.
3. The release workflow builds the package, publishes it to PyPI through
   trusted publishing and creates the GitHub release.

## Code of conduct

Everyone taking part in this project is expected to follow the
[code of conduct](CODE_OF_CONDUCT.md).
