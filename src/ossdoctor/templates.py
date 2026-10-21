"""File templates used by ``ossdoctor fix``.

Placeholders use :class:`string.Template` syntax (``$project``, ``$year``,
``$author``, ``$contact``). Literal dollar signs must be written as ``$$``.
"""

README = """\
# $project

One or two sentences on what $project does and who it is for.

## Installation

```sh
# Replace with the real install command
```

## Usage

```sh
# Show the most common way to use $project
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## License

See [LICENSE](LICENSE).
"""

LICENSES = {
    "MIT": """\
MIT License

Copyright (c) $year $author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""",
    "ISC": """\
ISC License

Copyright (c) $year $author

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
""",
    "BSD-2-Clause": """\
BSD 2-Clause License

Copyright (c) $year, $author

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""",
    "BSD-3-Clause": """\
BSD 3-Clause License

Copyright (c) $year, $author

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""",
}

CONTRIBUTING = """\
# Contributing to $project

Thanks for taking the time to contribute!

## Reporting bugs and requesting features

Search the existing issues first. If nothing matches, open a new issue using
one of the templates and include as much detail as you can.

Please report security vulnerabilities privately as described in
[SECURITY.md](SECURITY.md), not in public issues.

## Making changes

1. Fork the repository and create a branch from the default branch.
2. Set up the project locally (describe the setup commands here).
3. Make your change and add or update tests.
4. Run the test suite and linters (describe the commands here).
5. Open a pull request that explains what changed and why, and link the
   related issue.

Small, focused pull requests are reviewed faster than large ones.

## Code of conduct

Everyone taking part in this project is expected to follow the
[code of conduct](CODE_OF_CONDUCT.md).
"""

CODE_OF_CONDUCT = """\
# Code of Conduct

This project adopts the [Contributor Covenant, version 2.1][covenant] as its
code of conduct. All contributors and maintainers are expected to follow it in
every project space, including issues, pull requests and chat.

## Reporting

Report unacceptable behaviour to the maintainers at $contact. All reports are
reviewed promptly and handled confidentially.

[covenant]: https://www.contributor-covenant.org/version/2/1/code_of_conduct/
"""

SECURITY = """\
# Security Policy

## Supported versions

Security fixes are released for the latest version of $project. Please upgrade
before reporting an issue.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report vulnerabilities privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
("Report a vulnerability" on the Security tab), or by email to $contact.

Please include a description of the issue, steps to reproduce it, the affected
versions and any known workarounds. You should receive a reply within 7 days.
Once a fix is released we will credit you in the advisory unless you prefer to
stay anonymous.
"""

CHANGELOG = """\
# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release.
"""

ISSUE_BUG = """\
name: Bug report
description: Something does not work as expected.
labels: [bug]
body:
  - type: markdown
    attributes:
      value: Thanks for reporting a bug! Please fill in as much as you can.
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: What did you do, what did you expect, and what happened instead?
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: Steps to reproduce
      placeholder: |
        1. ...
        2. ...
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Version
      description: Which version of $project are you using?
    validations:
      required: true
  - type: input
    id: environment
    attributes:
      label: Environment
      description: Operating system, runtime version and anything else relevant.
  - type: textarea
    id: logs
    attributes:
      label: Logs or error output
      render: text
"""

ISSUE_FEATURE = """\
name: Feature request
description: Suggest an idea or improvement.
labels: [enhancement]
body:
  - type: textarea
    id: problem
    attributes:
      label: What problem would this solve?
      description: Describe the use case rather than the solution.
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives you have considered
"""

ISSUE_CONFIG = """\
blank_issues_enabled: true
contact_links:
  - name: Report a security vulnerability
    url: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
    about: Please report security issues privately, as described in SECURITY.md.
"""

PR_TEMPLATE = """\
## What does this change?

<!-- A short description of the change and why it is needed. -->

Fixes #

## Checklist

- [ ] Tests added or updated
- [ ] Documentation updated
- [ ] CHANGELOG updated
"""

EDITORCONFIG = """\
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{json,yml,yaml,toml,js,jsx,ts,tsx,css,html}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[{Makefile,*.go}]
indent_style = tab
"""

GITIGNORE_COMMON = """\
# Editors and operating systems
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp

# Local environment and secrets
.env
.env.*
!.env.example
"""

GITIGNORE_BY_ECOSYSTEM = {
    "pip": """\
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
build/
dist/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
""",
    "npm": """\
# Node.js
node_modules/
dist/
coverage/
npm-debug.log*
yarn-error.log*
.npm/
""",
    "gomod": """\
# Go
/bin/
*.test
*.out
""",
    "cargo": """\
# Rust
/target/
""",
    "maven": """\
# Java (Maven)
target/
""",
    "gradle": """\
# Java (Gradle)
.gradle/
build/
""",
    "bundler": """\
# Ruby
/.bundle/
/vendor/bundle/
""",
    "composer": """\
# PHP
/vendor/
""",
    "nuget": """\
# .NET
bin/
obj/
""",
}
