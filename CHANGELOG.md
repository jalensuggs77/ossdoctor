# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/OWNER/ossdoctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/ossdoctor/releases/tag/v0.1.0
