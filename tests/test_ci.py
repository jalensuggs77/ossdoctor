from __future__ import annotations

import json
import shutil
import subprocess

import pytest
import yaml

from ossdoctor.ci import NoTemplate, generate_workflow, python_versions
from ossdoctor.cli import main
from ossdoctor.repo import Repo


def workflow(root) -> dict:
    return yaml.safe_load(generate_workflow(Repo.load(root)))


def steps(doc: dict, job: str) -> list[dict]:
    return doc["jobs"][job]["steps"]


def runs(doc: dict, job: str) -> list[str]:
    return [s["run"] for s in steps(doc, job) if "run" in s]


def used(doc: dict, job: str) -> dict[str, dict]:
    return {s["uses"].split("@")[0]: s.get("with", {}) for s in steps(doc, job) if "uses" in s}


def test_workflow_skeleton(make_repo):
    doc = workflow(make_repo({"go.mod": "module x\n"}))
    assert doc["name"] == "CI"
    # PyYAML reads the bare key `on` as the boolean True.
    assert doc[True] == {"push": {"branches": ["main"]}, "pull_request": None}
    assert doc["permissions"] == {"contents": "read"}
    assert steps(doc, "go")[0] == {"uses": "actions/checkout@v7"}


# --------------------------------------------------------------------------- #
# Python
# --------------------------------------------------------------------------- #


def test_python_pip_with_test_extra(make_repo):
    root = make_repo(
        {
            "pyproject.toml": '[project]\nname = "x"\nrequires-python = ">=3.11"\n'
            '[project.optional-dependencies]\ntest = ["pytest"]\n',
            "tests/test_x.py": "",
        }
    )
    doc = workflow(root)
    assert doc["jobs"]["python"]["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13", "3.14"]
    assert used(doc, "python")["actions/setup-python"] == {
        "python-version": "${{ matrix.python-version }}",
        "cache": "pip",
        "cache-dependency-path": "pyproject.toml",
    }
    assert runs(doc, "python") == [
        "python -m pip install --upgrade pip",
        'python -m pip install -e ".[test]"',
        "python -m pytest",
    ]


def test_python_installs_pytest_when_not_declared(make_repo):
    root = make_repo({"pyproject.toml": '[project]\nname = "x"\n', "tests/test_x.py": ""})
    assert runs(workflow(root), "python")[-2:] == ["python -m pip install pytest", "python -m pytest"]


def test_python_requirements_only_without_tests(make_repo):
    doc = workflow(make_repo({"requirements.txt": "requests\n", "app.py": ""}))
    assert runs(doc, "python") == ["python -m pip install --upgrade pip", "python -m pip install -r requirements.txt"]
    assert used(doc, "python")["actions/setup-python"]["cache-dependency-path"] == "requirements.txt"
    assert "No Python tests were found" in generate_workflow(Repo.load(make_repo({})))


def test_python_uv(make_repo):
    root = make_repo({"pyproject.toml": '[project]\nname = "x"\n', "uv.lock": "", "tests/test_x.py": ""})
    doc = workflow(root)
    assert used(doc, "python")["astral-sh/setup-uv"] == {"python-version": "${{ matrix.python-version }}"}
    assert "actions/setup-python" not in used(doc, "python")
    assert runs(doc, "python") == ["uv sync --all-extras", "uv run --with pytest pytest"]


def test_python_poetry(make_repo):
    root = make_repo(
        {
            "pyproject.toml": '[tool.poetry.group.dev.dependencies]\npytest = "^8"\n',
            "poetry.lock": "",
            "tests/test_x.py": "",
        }
    )
    doc = workflow(root)
    assert runs(doc, "python") == ["pipx install poetry", "poetry install --all-extras", "poetry run python -m pytest"]
    assert used(doc, "python")["actions/setup-python"]["cache"] == "poetry"


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (None, ("3.12", "3.13", "3.14")),
        (">=3.10", ("3.10", "3.11", "3.12", "3.13", "3.14")),
        (">=3.13,<4", ("3.13", "3.14")),
        ("~=3.10", ("3.10", "3.11", "3.12", "3.13", "3.14")),
        ("== 3.11.*", ("3.11", "3.12", "3.13", "3.14")),
        (">=3.15", ("3.15",)),
        ("==3.*", ("3.12", "3.13", "3.14")),
    ],
)
def test_python_versions(spec, expected):
    assert python_versions(spec) == expected


def test_pipfile_only_is_not_supported(make_repo):
    with pytest.raises(NoTemplate, match="python"):
        generate_workflow(Repo.load(make_repo({"Pipfile": ""})))


# --------------------------------------------------------------------------- #
# Node.js
# --------------------------------------------------------------------------- #


def _package(**fields) -> str:
    return json.dumps({"name": "x", **fields})


def test_node_npm_runs_existing_scripts_only(make_repo):
    scripts = {"test": "vitest run", "build": "tsc", "start": "node ."}
    doc = workflow(make_repo({"package.json": _package(scripts=scripts), "package-lock.json": "{}"}))
    assert doc["jobs"]["node"]["strategy"]["matrix"]["node-version"] == ["22", "24"]
    assert used(doc, "node")["actions/setup-node"] == {"node-version": "${{ matrix.node-version }}", "cache": "npm"}
    assert runs(doc, "node") == ["npm ci", "npm run build", "npm run test"]


def test_node_default_test_stub_is_ignored(make_repo):
    scripts = {"test": 'echo "Error: no test specified" && exit 1'}
    text = generate_workflow(Repo.load(make_repo({"package.json": _package(scripts=scripts)})))
    doc = yaml.safe_load(text)
    assert runs(doc, "node") == ["npm install"]
    assert "cache" not in used(doc, "node")["actions/setup-node"], "setup-node cache needs a lockfile"
    assert 'no "test" script' in text


def test_node_pnpm_without_pinned_version(make_repo):
    doc = workflow(make_repo({"package.json": _package(scripts={"test": "jest"}), "pnpm-lock.yaml": ""}))
    assert used(doc, "node")["pnpm/action-setup"] == {"version": 12}
    names = [s.get("uses", "").split("@")[0] for s in steps(doc, "node")]
    assert names.index("pnpm/action-setup") < names.index("actions/setup-node"), "pnpm must exist before caching"
    assert runs(doc, "node") == ["pnpm install --frozen-lockfile", "pnpm run test"]


@pytest.mark.parametrize(
    "fields",
    [{"packageManager": "pnpm@12.1.0"}, {"devEngines": {"packageManager": {"name": "pnpm", "version": "^12"}}}],
)
def test_node_pnpm_version_from_package_json_is_not_repeated(make_repo, fields):
    doc = workflow(make_repo({"package.json": _package(**fields), "pnpm-lock.yaml": ""}))
    assert used(doc, "node")["pnpm/action-setup"] == {}


@pytest.mark.parametrize(("yarnrc", "flag"), [(False, "--frozen-lockfile"), (True, "--immutable")])
def test_node_yarn(make_repo, yarnrc, flag):
    files = {"package.json": _package(scripts={"lint": "eslint ."}), "yarn.lock": ""}
    if yarnrc:
        files[".yarnrc.yml"] = "nodeLinker: node-modules\n"
    doc = workflow(make_repo(files))
    assert runs(doc, "node") == [f"yarn install {flag}", "yarn lint"]


def test_node_bun(make_repo):
    doc = workflow(make_repo({"package.json": _package(scripts={"test": "bun test"}), "bun.lock": ""}))
    assert "strategy" not in doc["jobs"]["node"]
    assert "actions/setup-node" not in used(doc, "node")
    assert runs(doc, "node") == ["bun install --frozen-lockfile", "bun run test"]


def test_node_invalid_package_json(make_repo):
    assert runs(workflow(make_repo({"package.json": "{not json"})), "node") == ["npm install"]


# --------------------------------------------------------------------------- #
# Go, Rust, Java
# --------------------------------------------------------------------------- #


def test_go(make_repo):
    doc = workflow(make_repo({"go.mod": "module x\n\ngo 1.24\n"}))
    assert used(doc, "go")["actions/setup-go"] == {"go-version-file": "go.mod"}
    assert runs(doc, "go") == ["go build ./...", "go vet ./...", "go test ./..."]


def test_rust(make_repo):
    assert runs(workflow(make_repo({"Cargo.toml": "[package]\n"})), "rust") == ["cargo build --verbose", "cargo test --verbose"]


@pytest.mark.parametrize(("wrapper", "command"), [(False, "mvn -B verify"), (True, "./mvnw -B verify")])
def test_maven(make_repo, wrapper, command):
    files = {"pom.xml": "<project/>"}
    if wrapper:
        files["mvnw"] = "#!/bin/sh\n"
    doc = workflow(make_repo(files))
    assert used(doc, "java")["actions/setup-java"] == {"distribution": "temurin", "java-version": 21, "cache": "maven"}
    assert runs(doc, "java") == [command]


def test_gradle_with_wrapper(make_repo):
    doc = workflow(make_repo({"build.gradle.kts": "", "gradlew": "#!/bin/sh\n"}))
    assert used(doc, "java")["actions/setup-java"]["cache"] == "gradle"
    assert runs(doc, "java") == ["./gradlew build"]


def test_gradle_without_wrapper_is_not_supported(make_repo):
    with pytest.raises(NoTemplate, match="gradlew"):
        generate_workflow(Repo.load(make_repo({"build.gradle": ""})))


# --------------------------------------------------------------------------- #
# Combinations and fallbacks
# --------------------------------------------------------------------------- #


def test_one_job_per_ecosystem(make_repo):
    doc = workflow(make_repo({"pyproject.toml": '[project]\nname = "x"\n', "package.json": "{}", "Dockerfile": ""}))
    assert list(doc["jobs"]) == ["python", "node"]


def test_unsupported_ecosystem_alongside_supported_one(make_repo):
    text = generate_workflow(Repo.load(make_repo({"go.mod": "module x\n", "Gemfile": ""})))
    assert "# No job was generated for: bundler. Add one by hand." in text
    assert list(yaml.safe_load(text)["jobs"]) == ["go"]


def test_only_unsupported_ecosystems(make_repo):
    with pytest.raises(NoTemplate, match="no CI template for: bundler, composer"):
        generate_workflow(Repo.load(make_repo({"Gemfile": "", "composer.json": "{}"})))


def test_nothing_to_build(make_repo):
    with pytest.raises(NoTemplate, match="no supported ecosystem"):
        generate_workflow(Repo.load(make_repo({"index.html": ""})))


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_push_branch_follows_the_repository(make_repo):
    root = make_repo({"go.mod": "module x\n"})
    subprocess.run(["git", "init", "-q", "-b", "trunk", str(root)], check=True)
    assert workflow(root)[True]["push"] == {"branches": ["trunk"]}


def test_fix_writes_the_workflow_and_ci_then_passes(make_repo, capsys):
    root = make_repo({"package.json": _package(scripts={"test": "node --test"}), "package-lock.json": "{}"})
    assert main(["fix", str(root), "--only", "ci"]) == 0
    assert "Created .github/workflows/ci.yml" in capsys.readouterr().out
    text = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # The expressions must survive the placeholder substitution done on every template.
    assert "${{ matrix.node-version }}" in text
    main(["check", str(root), "--only", "ci", "-f", "json"])
    assert json.loads(capsys.readouterr().out)["results"][0]["status"] == "pass"


def test_fix_explains_when_there_is_no_template(make_repo, capsys):
    main(["fix", str(make_repo({"Gemfile": ""})), "--only", "ci"])
    assert "Skipped ci: no CI template for: bundler" in capsys.readouterr().out


ACTIONLINT = shutil.which("actionlint")
LINT_SAMPLES = {
    "pip": {"pyproject.toml": '[project]\nname = "x"\n', "tests/test_x.py": ""},
    "uv": {"pyproject.toml": '[project]\nname = "x"\n', "uv.lock": "", "tests/test_x.py": ""},
    "poetry": {"pyproject.toml": "[tool.poetry]\n", "poetry.lock": "", "tests/test_x.py": ""},
    "npm": {"package.json": _package(scripts={"test": "jest", "lint": "eslint ."}), "package-lock.json": "{}"},
    "pnpm": {"package.json": _package(), "pnpm-lock.yaml": ""},
    "bun": {"package.json": _package(), "bun.lock": ""},
    "go+rust+java": {"go.mod": "module x\n", "Cargo.toml": "[package]\n", "pom.xml": "<project/>"},
}


@pytest.mark.skipif(ACTIONLINT is None, reason="actionlint not installed")
@pytest.mark.parametrize("name", sorted(LINT_SAMPLES))
def test_generated_workflow_passes_actionlint(make_repo, tmp_path, name):
    workflow_file = tmp_path / "ci.yml"
    workflow_file.write_text(generate_workflow(Repo.load(make_repo(LINT_SAMPLES[name]))), encoding="utf-8")
    result = subprocess.run([ACTIONLINT, "-no-color", str(workflow_file)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
