# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-10-21

### Added

- `ossdoctor badge` prints a shields.io badge showing the score, as Markdown,
  reStructuredText, HTML or a bare URL, in any shields.io style.
  `--update FILE` rewrites the score of the badges already in a file, and
  `--check` makes it fail instead when they are out of date, for use in CI.
- `ossdoctor fix` generates a GitHub Actions CI workflow when a repository has
  none, with a job for each of Python (pip, uv or Poetry), Node.js (npm, pnpm,
  Yarn or Bun), Go, Rust and Java (Maven or the Gradle wrapper). It only runs
  scripts and tests that exist, picks the Python matrix from
  `requires-python`, runs on the repository's default branch and uses a
  read-only token.
- CI lints ossdoctor's own workflows and the generated ones with actionlint.

## [0.2.1] - 2026-10-21

### Security

- `ossdoctor fix` no longer writes through symlinks. A repository containing a
  link such as `.github -> /elsewhere` could previously make `fix` create files
  outside the repository. Any symlink on the path of a generated file is now
  refused and reported, all paths are checked before anything is written, and
  they are checked again just before each write.

### Fixed

- A dangling symlink is no longer counted as an existing file when the
  repository is not a git checkout, matching the behaviour inside one. It also
  no longer makes `fix` stop halfway with `File exists`.

## [0.2.0] - 2026-10-21

### Added

- `--format sarif` writes a SARIF 2.1.0 report for GitHub code scanning and
  other SARIF viewers. Failures tied to a file (committed secrets, large
  files, README sections, lockfiles) are reported on that file; missing files
  are reported on the path where they belong. Security checks carry a
  `security-severity`.
- `--output FILE` writes the report to a file instead of standard output.
- The GitHub Action takes a `sarif-file` input and exposes it as an output.

### Changed

- The release workflow now runs when a GitHub release is published and
  attaches the built distributions to it.

## [0.1.0] - 2026-10-21

### Added

- `ossdoctor check` with 18 checks across documentation, community, automation,
  security and hygiene, and a weighted 0-100 score.
- Text, Markdown and JSON output, and `--fail-under` for CI gates.
- `ossdoctor fix` to generate missing community files (README, LICENSE,
  CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, issue and PR templates,
  CODEOWNERS, Dependabot, .gitignore, .editorconfig) without overwriting
  anything.
- Configuration via `.ossdoctor.toml` or `[tool.ossdoctor]` in `pyproject.toml`.
- A GitHub Action that writes the report to the job summary.

[Unreleased]: https://github.com/jalensuggs77/ossdoctor/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/jalensuggs77/ossdoctor/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jalensuggs77/ossdoctor/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jalensuggs77/ossdoctor/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jalensuggs77/ossdoctor/releases/tag/v0.1.0
