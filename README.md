# ossdoctor

[![CI](https://github.com/jalensuggs77/ossdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/jalensuggs77/ossdoctor/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/ossdoctor)](https://pypi.org/project/ossdoctor/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[简体中文](README.zh-CN.md)

**A health check for open source repositories.** ossdoctor looks for the docs,
community files and automation that maintainers rely on, scores the repository
from 0 to 100, and generates whatever is missing.

- **Fast and offline.** It reads only the working tree, never calls an API and
  needs no token, so it runs the same locally, in CI and on forks.
- **Fixes, not just findings.** `ossdoctor fix` writes a sensible LICENSE,
  CONTRIBUTING guide, security policy, issue forms, Dependabot config, a CI
  workflow and more, tailored to the ecosystems it detects. It never
  overwrites an existing file.
- **Built for CI.** Markdown output for job summaries and PR comments, SARIF
  for GitHub code scanning, JSON for scripts, and `--fail-under` to keep a
  score from slipping.
- **Zero dependencies.** Pure Python standard library.

<p align="center">
  <img src="docs/images/check.svg" alt="ossdoctor reporting a score of 50/100 for a demo repository, with failing checks such as a missing changelog, security policy and a committed .env file" width="820">
</p>

## Installation

```sh
pipx install ossdoctor      # or: pip install ossdoctor
```

Python 3.11 or newer is required.

## Usage

```sh
ossdoctor                       # check the current directory
ossdoctor path/to/repo -v       # explain how to fix each failure
ossdoctor --format markdown     # report as a Markdown table
ossdoctor --format json         # machine-readable output
ossdoctor -f sarif -o ossdoctor.sarif   # SARIF 2.1.0 for code scanning
ossdoctor --fail-under 80       # exit 1 when the score is below 80

ossdoctor fix --dry-run         # show which files would be generated
ossdoctor fix --license Apache-2.0 --email security@example.com --github-user ada

ossdoctor list                  # list every check
```

`fix` fills in the project name, year, author and contact address (taken from
`git config` unless you pass `--author` and `--email`). Placeholders it cannot
fill are reported so you can finish them by hand. Review the generated files
before committing: they are starting points, not finished documents.

<p align="center">
  <img src="docs/images/fix.svg" alt="ossdoctor fix creating ten missing files, after which only the README license section and the committed .env file remain" width="820">
</p>

Anything that needs a human decision, such as a leaked secret or a missing
README section, is left for you.

Built-in license templates: MIT, ISC, BSD-2-Clause and BSD-3-Clause. For other
licenses, copy the text from [choosealicense.com](https://choosealicense.com/licenses/).

### Generated CI workflows

When a repository has no CI at all, `fix` writes `.github/workflows/ci.yml`
with one job per ecosystem it finds:

| Ecosystem | How it is installed | What runs |
|---|---|---|
| Python | uv (`uv.lock`), Poetry (`poetry.lock`) or pip, with a `test`/`dev` extra if declared | pytest, if there are tests, across the versions allowed by `requires-python` |
| Node.js | npm, pnpm, Yarn or Bun, chosen by lockfile | the `lint`, `build` and `test` scripts that exist, on the Node.js LTS lines |
| Go | `setup-go` with the version from `go.mod` | `go build`, `go vet`, `go test` |
| Rust | the runner's stable toolchain | `cargo build`, `cargo test` |
| Java | Maven or the Gradle wrapper, Temurin 21 | `mvn verify` or `./gradlew build` |

The workflow runs on pushes to the default branch and on pull requests, with a
read-only token. It only calls scripts and tests that exist, so it should pass
on the first push if the project builds. It is still a starting point: check
the versions and commands before committing. Ecosystems without a template are
listed in a comment at the top of the file.

### GitHub Action

```yaml
# .github/workflows/ossdoctor.yml
name: ossdoctor
on: [push, pull_request]
permissions:
  contents: read
jobs:
  health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: jalensuggs77/ossdoctor@v0.2.1
        with:
          fail-under: "80"
```

The report is added to the job summary and the score is available as
`steps.<id>.outputs.score`.

### GitHub code scanning

With `sarif-file`, the Action also writes a SARIF report. Upload it and every
failing check shows up under **Security → Code scanning**, with the fix
explained on the alert and new problems flagged on pull requests:

```yaml
jobs:
  health:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v7
      - uses: jalensuggs77/ossdoctor@v0.2.1
        with:
          sarif-file: ossdoctor.sarif
      - uses: github/codeql-action/upload-sarif@v4
        if: always()
        with:
          sarif_file: ossdoctor.sarif
          category: ossdoctor
```

Required checks are reported as errors, recommended ones as warnings and
optional ones as notes. Security checks also carry a `security-severity`, so
GitHub ranks them as high, medium or low. Problems with a specific file (a
committed `.env`, a large binary, an incomplete README) are reported on that
file. A missing file is reported on the path where it belongs, such as
`SECURITY.md`. Paths are relative to the git repository root, so running
ossdoctor on a subdirectory of a monorepo works too.

## Checks

| Id | Level | What it looks for |
|---|---|---|
| `readme` | required | A README with real content |
| `readme-sections` | recommended | Installation, usage and license headings |
| `license` | required | A LICENSE file, identified by SPDX id |
| `changelog` | recommended | CHANGELOG / HISTORY / NEWS, or a fragments directory |
| `contributing` | recommended | CONTRIBUTING guide |
| `code-of-conduct` | recommended | CODE_OF_CONDUCT |
| `issue-templates` | recommended | Issue templates or forms |
| `pr-template` | optional | Pull request template |
| `codeowners` | optional | CODEOWNERS |
| `ci` | required | GitHub Actions, GitLab CI, CircleCI, Jenkins, Buildkite and others |
| `tests` | required | Test files or directories in common layouts |
| `security-policy` | recommended | SECURITY policy for private vulnerability reports |
| `dependency-updates` | recommended | Dependabot or Renovate configuration |
| `lockfile` | recommended | Committed lockfiles for npm and Go |
| `no-secret-files` | required | No `.env`, private keys or keystores in the repository |
| `gitignore` | recommended | `.gitignore` |
| `editorconfig` | optional | `.editorconfig` |
| `no-large-files` | recommended | No files over the size limit (5 MB by default) |

Community files are found in the root, `.github/` or `docs/`, the same places
GitHub looks. In a git checkout, files ignored by `.gitignore` are not checked.
Because ossdoctor works offline, it cannot see default community files that an
organization keeps in its own `.github` repository. If you rely on those,
`disable` the corresponding checks. A `package-lock=false` line in `.npmrc` is
treated as a deliberate choice not to commit an npm lockfile.

**Scoring.** Required checks weigh 3, recommended 2 and optional 1. The score is
the weighted share of applicable checks that pass. Skipped checks don't count.

## Configuration

Add a `[tool.ossdoctor]` table to `pyproject.toml`, or create `.ossdoctor.toml`
with the same keys at the top level:

```toml
[tool.ossdoctor]
disable = ["codeowners", "editorconfig"]   # check ids to skip
fail-under = 80                            # default for --fail-under
large-file-mb = 10                         # limit for no-large-files
ignore-paths = ["tests/fixtures/*"]        # globs excluded from file scans
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Score below `fail-under` |
| 2 | Usage or configuration error |

## Roadmap

- Checks for release hygiene (tags, signed releases) and branch protection, using an optional token
- More license templates and templates in other languages
- Package manager metadata checks (repository URL, license field, keywords)

Ideas and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
