"""Generating a GitHub Actions CI workflow for the ecosystems in a repository.

The workflow is a starting point: it installs the project the way its
lockfiles say it is installed, and runs only the scripts and tests that
actually exist, so that it passes on the first push whenever the project
itself builds.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field

from .checks import NODE_LOCKFILES, is_test_file
from .repo import Repo

# Versions are refreshed by hand at each ossdoctor release.
CHECKOUT = "actions/checkout@v7"
SETUP_PYTHON = "actions/setup-python@v7"
SETUP_UV = "astral-sh/setup-uv@v7"
SETUP_NODE = "actions/setup-node@v7"
SETUP_PNPM = "pnpm/action-setup@v6"
SETUP_BUN = "oven-sh/setup-bun@v2"
SETUP_GO = "actions/setup-go@v7"
SETUP_JAVA = "actions/setup-java@v6"

# Supported CPython versions. The newest release is left out of the default
# matrix until its dependencies commonly ship wheels for it.
PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")
DEFAULT_PYTHON_VERSIONS = ("3.12", "3.13", "3.14")
NODE_VERSIONS = ("22", "24")  # the current LTS lines
PNPM_VERSION = "12"
JAVA_VERSION = "21"

NPM_TEST_STUB = 'echo "Error: no test specified" && exit 1'
TEST_EXTRAS = ("test", "tests", "testing", "dev")


class NoTemplate(Exception):
    """The repository has no ecosystem this module can write a job for."""


@dataclass
class Job:
    id: str
    name: str
    steps: list[str]
    matrix: tuple[str, tuple[str, ...]] | None = None
    comments: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"  {self.id}:"]
        lines += [f"    # {c}" for c in self.comments]
        lines.append(f"    name: {self.name}")
        lines.append("    runs-on: ubuntu-latest")
        if self.matrix:
            key, values = self.matrix
            lines += [
                "    strategy:",
                "      fail-fast: false",
                "      matrix:",
                f"        {key}: [{', '.join(json.dumps(v) for v in values)}]",
            ]
        lines.append("    steps:")
        lines += self.steps
        return "\n".join(lines)


def uses(action: str, **with_: str) -> str:
    step = f"      - uses: {action}"
    if with_:
        step += "\n        with:" + "".join(f"\n          {k.replace('_', '-')}: {v}" for k, v in with_.items())
    return step


def run(command: str) -> str:
    return f"      - run: {command}"


def _read_toml(repo: Repo, rel: str) -> dict:
    try:
        return tomllib.loads(repo.read_text(rel))
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _mentions(repo: Repo, needle: str, *files: str) -> bool:
    return any(needle in repo.read_text(f).lower() for f in files if repo.find(f))


def python_versions(requires_python: str | None) -> tuple[str, ...]:
    """The matrix for a ``requires-python`` specifier such as ``>=3.11``."""
    if requires_python:
        m = re.search(r"(?:>=?|~=|==)\s*3\.(\d+)", requires_python)
        if m:
            minor = int(m.group(1))
            chosen = tuple(v for v in PYTHON_VERSIONS if int(v.split(".")[1]) >= minor)
            return chosen or (f"3.{minor}",)
    return DEFAULT_PYTHON_VERSIONS


def python_job(repo: Repo) -> Job:
    pyproject_path = repo.find("pyproject.toml")
    pyproject = _read_toml(repo, pyproject_path) if pyproject_path else {}
    project = pyproject.get("project", {}) if isinstance(pyproject.get("project"), dict) else {}
    requirements = repo.find("requirements.txt")
    setup_py = repo.find("setup.py")
    installable = bool(pyproject_path or setup_py)
    if not (installable or requirements):
        raise NoTemplate("python (only Pipfile or setup.cfg found)")

    has_tests = any(is_test_file(f) and f.endswith(".py") for f in repo.files)
    manifests = [f for f in (pyproject_path, setup_py, requirements) if f]
    pytest_declared = _mentions(repo, "pytest", *manifests)
    matrix = ("python-version", python_versions(project.get("requires-python")))
    version = "${{ matrix.python-version }}"
    steps = [uses(CHECKOUT)]

    if repo.find("uv.lock"):
        steps += [uses(SETUP_UV, python_version=version), run("uv sync --all-extras")]
        if has_tests:
            steps.append(run("uv run pytest" if pytest_declared else "uv run --with pytest pytest"))
    elif repo.find("poetry.lock"):
        steps += [
            run("pipx install poetry"),
            uses(SETUP_PYTHON, python_version=version, cache="poetry"),
            run("poetry install --all-extras"),
        ]
        if has_tests:
            if not pytest_declared:
                steps.append(run("poetry run python -m pip install pytest"))
            steps.append(run("poetry run python -m pytest"))
    else:
        steps += [
            uses(SETUP_PYTHON, python_version=version, cache="pip", cache_dependency_path=manifests[0]),
            run("python -m pip install --upgrade pip"),
        ]
        if requirements:
            steps.append(run(f"python -m pip install -r {requirements}"))
        if installable:
            extras = project.get("optional-dependencies", {})
            extra = next((e for e in TEST_EXTRAS if isinstance(extras, dict) and e in extras), None)
            steps.append(run(f'python -m pip install -e ".[{extra}]"' if extra else "python -m pip install -e ."))
        if has_tests:
            if not pytest_declared:
                steps.append(run("python -m pip install pytest"))
            steps.append(run("python -m pytest"))

    comments = [] if has_tests else ["No Python tests were found, so this job only checks that the project installs."]
    return Job("python", f"Python {version}", steps, matrix, comments)


def node_job(repo: Repo) -> Job:
    manifest_path = repo.find("package.json")
    try:
        manifest = json.loads(repo.read_text(manifest_path))
    except (json.JSONDecodeError, OSError):
        manifest = {}
    if not isinstance(manifest, dict):
        manifest = {}
    scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
    lockfile = repo.find(*NODE_LOCKFILES)
    lock_name = lockfile.rsplit("/", 1)[-1] if lockfile else ""

    if lock_name.startswith("bun.lock"):
        steps = [uses(CHECKOUT), uses(SETUP_BUN), run("bun install --frozen-lockfile")]
        steps += [run(f"bun run {s}") for s in ("lint", "build", "test") if _real_script(scripts, s)]
        return Job("node", "Bun", steps)

    version = "${{ matrix.node-version }}"
    steps = [uses(CHECKOUT)]
    if lock_name == "pnpm-lock.yaml":
        pins_pnpm = str(manifest.get("packageManager", "")).startswith("pnpm@") or (
            isinstance(manifest.get("devEngines"), dict)
            and isinstance(manifest["devEngines"].get("packageManager"), dict)
            and manifest["devEngines"]["packageManager"].get("name") == "pnpm"
        )
        # pnpm/action-setup fails if a version is given here and in package.json.
        steps.append(uses(SETUP_PNPM) if pins_pnpm else uses(SETUP_PNPM, version=PNPM_VERSION))
        steps += [uses(SETUP_NODE, node_version=version, cache="pnpm"), run("pnpm install --frozen-lockfile")]
        runner = "pnpm run"
    elif lock_name == "yarn.lock":
        immutable = "--immutable" if repo.find(".yarnrc.yml") else "--frozen-lockfile"
        steps += [uses(SETUP_NODE, node_version=version, cache="yarn"), run(f"yarn install {immutable}")]
        runner = "yarn"
    elif lockfile:
        steps += [uses(SETUP_NODE, node_version=version, cache="npm"), run("npm ci")]
        runner = "npm run"
    else:
        steps += [uses(SETUP_NODE, node_version=version), run("npm install")]
        runner = "npm run"

    steps += [run(f"{runner} {s}") for s in ("lint", "build", "test") if _real_script(scripts, s)]
    comments = [] if _real_script(scripts, "test") else ['package.json has no "test" script, so no tests are run.']
    return Job("node", f"Node.js {version}", steps, ("node-version", NODE_VERSIONS), comments)


def _real_script(scripts: dict, name: str) -> bool:
    value = scripts.get(name)
    return isinstance(value, str) and bool(value.strip()) and value.strip() != NPM_TEST_STUB


def go_job(repo: Repo) -> Job:
    gomod = repo.find("go.mod")
    steps = [
        uses(CHECKOUT),
        uses(SETUP_GO, go_version_file=gomod),
        run("go build ./..."),
        run("go vet ./..."),
        run("go test ./..."),
    ]
    return Job("go", "Go", steps)


def rust_job(repo: Repo) -> Job:
    # GitHub's runners ship with a stable Rust toolchain.
    return Job("rust", "Rust", [uses(CHECKOUT), run("cargo build --verbose"), run("cargo test --verbose")])


def java_job(repo: Repo) -> Job:
    if repo.find("pom.xml"):
        tool, command = "maven", ("./mvnw -B verify" if repo.find("mvnw") else "mvn -B verify")
    elif repo.find("gradlew"):
        tool, command = "gradle", "./gradlew build"
    else:
        raise NoTemplate("gradle (add the Gradle wrapper, gradlew, so CI uses your Gradle version)")
    steps = [
        uses(CHECKOUT),
        uses(SETUP_JAVA, distribution="temurin", java_version=JAVA_VERSION, cache=tool),
        run(command),
    ]
    return Job("java", f"Java {JAVA_VERSION}", steps, comments=["Change java-version if the project targets another JDK."])


BUILDERS: tuple[tuple[str, Callable[[Repo], Job]], ...] = (
    ("pip", python_job),
    ("npm", node_job),
    ("gomod", go_job),
    ("cargo", rust_job),
    ("java", java_job),
)
# Ecosystems that are detected for Dependabot but need no CI job of their own.
NOT_BUILT = {"github-actions", "docker"}


def default_branch(repo: Repo) -> str:
    for args in (["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], ["branch", "--show-current"]):
        try:
            out = subprocess.run(["git", "-C", str(repo.root), *args], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        name = out.strip().removeprefix("origin/")
        if name:
            return name
    return "main"


def generate_workflow(repo: Repo) -> str:
    """Return the text of ``.github/workflows/ci.yml``, or raise :class:`NoTemplate`."""
    ecosystems = set(repo.ecosystems)
    if ecosystems & {"maven", "gradle"}:
        ecosystems = (ecosystems - {"maven", "gradle"}) | {"java"}

    jobs, unsupported = [], []
    for ecosystem, build in BUILDERS:
        if ecosystem in ecosystems:
            try:
                jobs.append(build(repo))
            except NoTemplate as exc:
                unsupported.append(str(exc))
    handled = {eco for eco, _ in BUILDERS} | NOT_BUILT
    unsupported += sorted(ecosystems - handled)

    if not jobs:
        if unsupported:
            raise NoTemplate("no CI template for: " + ", ".join(unsupported))
        raise NoTemplate("no supported ecosystem found (Python, Node.js, Go, Rust or Java)")

    header = [
        "# Generated by ossdoctor. Review it before committing: check the versions",
        "# and commands against how the project is really built and tested.",
    ]
    if unsupported:
        header.append("# No job was generated for: " + ", ".join(unsupported) + ". Add one by hand.")
    body = [
        "name: CI",
        "",
        "on:",
        "  push:",
        f"    branches: [{default_branch(repo)}]",
        "  pull_request:",
        "",
        "permissions:",
        "  contents: read",
        "",
        "jobs:",
    ]
    return "\n".join(header + body) + "\n" + "\n\n".join(job.render() for job in jobs) + "\n"
