from __future__ import annotations

import pytest

from ossdoctor.checks import REGISTRY, Status, identify_license
from ossdoctor.config import load_config
from ossdoctor.repo import Repo
from ossdoctor.runner import run_checks

from .conftest import HEALTHY, LONG_README


def test_healthy_repo_scores_100(make_repo):
    root = make_repo(HEALTHY)
    report = run_checks(Repo.load(root), load_config(root))
    failures = {r.check.id: r.outcome.detail for r in report.results if r.status is Status.FAIL}
    assert failures == {}
    assert report.score == 100


def test_empty_repo_only_passes_absence_checks(make_repo):
    root = make_repo({"main.py": "print('hi')\n"})
    report = run_checks(Repo.load(root), load_config(root))
    assert report.score == 15
    assert {r.check.id for r in report.by_status(Status.PASS)} == {"no-secret-files", "no-large-files"}


def test_every_check_has_a_hint():
    for c in REGISTRY.values():
        assert c.hint.endswith((".", ")")), c.id


@pytest.mark.parametrize(
    ("files", "status"),
    [
        ({}, Status.FAIL),
        ({"README.md": "# x\n"}, Status.FAIL),
        ({"README.md": LONG_README}, Status.PASS),
        ({"readme.rst": "x" * 300}, Status.PASS),
        ({".github/README.md": LONG_README}, Status.PASS),
    ],
)
def test_readme(make_repo, outcome, files, status):
    assert outcome(make_repo(files), "readme").status is status


def test_readme_sections_reports_what_is_missing(make_repo, outcome):
    root = make_repo({"README.md": "# demo\n\n## Installation\n\npip install demo\n"})
    result = outcome(root, "readme-sections")
    assert result.status is Status.FAIL
    assert result.detail == "missing section: usage, license"


def test_readme_sections_understands_rst_and_chinese(make_repo, outcome):
    rst = "demo\n====\n\n安装\n----\n\n用法\n----\n\nLicense\n-------\n"
    assert outcome(make_repo({"README.rst": rst}), "readme-sections").status is Status.PASS


def test_readme_sections_ignores_words_outside_headings(make_repo, outcome):
    root = make_repo({"README.md": "# demo\n\nTo install, run pip. Usage is obvious. License: MIT.\n"})
    assert outcome(root, "readme-sections").status is Status.FAIL


def test_readme_sections_ignores_comments_in_code_blocks(make_repo, outcome):
    readme = "# demo\n\n## Installation\n\n```sh\n# usage: demo --help\n# license\n```\n"
    assert outcome(make_repo({"README.md": readme}), "readme-sections").detail == "missing section: usage, license"


def test_readme_sections_reads_html_headings(make_repo, outcome):
    readme = '<h2 align="center">Install</h2>\n<h2><a href="#u">Usage</a></h2>\n\n## License\n'
    assert outcome(make_repo({"README.md": readme}), "readme-sections").status is Status.PASS


def test_readme_sections_skipped_without_readme(make_repo, outcome):
    assert outcome(make_repo({}), "readme-sections").status is Status.SKIP


@pytest.mark.parametrize(
    ("text", "spdx"),
    [
        ("MIT License\n\nPermission is hereby granted, free of charge, to any person", "MIT"),
        ("Apache License\n  Version 2.0, January 2004", "Apache-2.0"),
        ("GNU GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007", "GPL-3.0"),
        ("GNU LESSER GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007", "LGPL-3.0"),
        ("GNU AFFERO GENERAL PUBLIC LICENSE\n Version 3", "AGPL-3.0"),
        ("Redistribution and use in source and binary forms ... Neither the name of", "BSD-3-Clause"),
        ("Redistribution and use in source and binary forms, with or without", "BSD-2-Clause"),
        ("This is free and unencumbered software released into the public domain.", "Unlicense"),
        ("All rights reserved.", None),
    ],
)
def test_identify_license(text, spdx):
    assert identify_license(text) == spdx


def test_license_detail_names_the_license(make_repo, outcome):
    result = outcome(make_repo({"COPYING": "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n"}), "license")
    assert result.status is Status.PASS
    assert result.detail == "COPYING (GPL-2.0)"


def test_issue_templates_ignore_config_only(make_repo, outcome):
    root = make_repo({".github/ISSUE_TEMPLATE/config.yml": "blank_issues_enabled: false\n"})
    assert outcome(root, "issue-templates").status is Status.FAIL


@pytest.mark.parametrize(
    "path",
    [".github/workflows/test.yaml", ".gitlab-ci.yml", ".circleci/config.yml", "Jenkinsfile", ".buildkite/pipeline.yml"],
)
def test_ci_providers(make_repo, outcome, path):
    assert outcome(make_repo({path: "x\n"}), "ci").status is Status.PASS


@pytest.mark.parametrize(
    "path",
    ["tests/test_x.py", "pkg/foo_test.go", "src/app.test.ts", "spec/models/user_spec.rb", "src/Foo.spec.jsx"],
)
def test_tests_detected(make_repo, outcome, path):
    assert outcome(make_repo({path: "x\n"}), "tests").status is Status.PASS


def test_inline_rust_tests(make_repo, outcome):
    root = make_repo({"Cargo.toml": "[package]\n", "src/lib.rs": "#[cfg(test)]\nmod t {\n    #[test]\n    fn a() {}\n}\n"})
    assert outcome(root, "tests").status is Status.PASS


def test_lockfile_skipped_without_ecosystem(make_repo, outcome):
    assert outcome(make_repo({"main.c": ""}), "lockfile").status is Status.SKIP


def test_lockfile_node(make_repo, outcome):
    assert outcome(make_repo({"package.json": "{}"}), "lockfile").status is Status.FAIL
    assert outcome(make_repo({"pnpm-lock.yaml": ""}), "lockfile").status is Status.PASS


def test_lockfile_opt_out_in_npmrc(make_repo, outcome):
    root = make_repo({"package.json": "{}", ".npmrc": "save-exact=true\npackage-lock=false\n"})
    assert outcome(root, "lockfile").detail == "lockfile not used: npm (disabled in .npmrc)"


def test_lockfile_go_without_dependencies_is_skipped(make_repo, outcome):
    assert outcome(make_repo({"go.mod": "module x\n\ngo 1.22\n"}), "lockfile").status is Status.SKIP


def test_lockfile_go_with_dependencies(make_repo, outcome):
    root = make_repo({"go.mod": "module x\n\nrequire example.com/y v1.0.0\n"})
    assert outcome(root, "lockfile").detail == "missing lockfile for Go"


@pytest.mark.parametrize(
    ("files", "status"),
    [
        ({".env": "TOKEN=x"}, Status.FAIL),
        ({"config/.env.production": "TOKEN=x"}, Status.FAIL),
        ({".env.example": "TOKEN="}, Status.PASS),
        ({"deploy/id_rsa": "x"}, Status.FAIL),
        ({"certs/server.pem": "-----BEGIN RSA PRIVATE KEY-----\n"}, Status.FAIL),
        ({"certs/ca.pem": "-----BEGIN CERTIFICATE-----\n"}, Status.PASS),
    ],
)
def test_no_secret_files(make_repo, outcome, files, status):
    assert outcome(make_repo(files), "no-secret-files").status is status


def test_ignore_paths_applies_to_secret_check(make_repo, outcome):
    root = make_repo({".env": "x", ".ossdoctor.toml": 'ignore-paths = [".env"]\n'})
    assert outcome(root, "no-secret-files").status is Status.PASS


def test_large_files_respects_config(make_repo, outcome):
    files = {"data.bin": b"\0" * (2 * 1024 * 1024)}
    assert outcome(make_repo(files), "no-large-files").status is Status.PASS
    root = make_repo({".ossdoctor.toml": "large-file-mb = 1\n"})
    result = outcome(root, "no-large-files")
    assert result.status is Status.FAIL
    assert "data.bin (2.0 MB)" in result.detail


def test_lookup_is_case_insensitive(make_repo, outcome):
    assert outcome(make_repo({"contributing.MD": "x"}), "contributing").status is Status.PASS
