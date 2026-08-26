"""Deterministic guards for the repository's own invariants.

These run in any clone: they read git history and tracked files only. Checks that
depend on local, gitignored orq-lite runtime state skip when it is absent.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\([a-z0-9._-]+\))?!?: .+"
)
EXEMPT_SUBJECT_PREFIXES = ("Merge ", "Revert ", "fixup! ")

AI_ATTRIBUTION_TOOLS = (
    "claude|anthropic|copilot|github copilot|chatgpt|openai|codex|cursor|windsurf"
    "|aider|gemini|devin|opencode"
)
AI_ATTRIBUTION = re.compile(
    rf"(?im)^\s*(co-authored-by:.*({AI_ATTRIBUTION_TOOLS})"
    rf"|generated[\s-]+(with|by):?.*({AI_ATTRIBUTION_TOOLS})"
    rf"|ai-generated-by:?.*({AI_ATTRIBUTION_TOOLS})"
    rf"|assisted-by:?.*({AI_ATTRIBUTION_TOOLS}))"
)


def roles_referenced_by(node: object) -> set[str]:
    """Collect every `role` value appearing anywhere in a compiled flow's IR."""
    found: set[str] = set()
    if isinstance(node, dict):
        role = node.get("role")
        if isinstance(role, str):
            found.add(role)
        for value in node.values():
            found |= roles_referenced_by(value)
    elif isinstance(node, list):
        for item in node:
            found |= roles_referenced_by(item)
    return found


def orq_lite(*args: str) -> str:
    """Run an orq-lite command in the repository root and return its stdout."""
    return subprocess.run(
        ["orq-lite", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def git(*args: str) -> str:
    """Run a git command in the repository root and return its stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_no_ai_coauthorship_trailers_in_history() -> None:
    """Commit metadata stays human-accountable (CES-91, enforced by CI)."""
    offenders = [
        line.split("\x00", 1)[0]
        for line in git("log", "--format=%H%x00%B%x1e").split("\x1e")
        if line.strip() and AI_ATTRIBUTION.search(line)
    ]
    assert offenders == [], f"commits carry AI attribution trailers: {offenders}"


def test_commit_subjects_follow_conventional_commits() -> None:
    """Every commit subject parses as Conventional Commits (CES-75)."""
    bad = [
        subject
        for subject in git("log", "--format=%s").splitlines()
        if subject.strip()
        and not subject.startswith(EXEMPT_SUBJECT_PREFIXES)
        and not CONVENTIONAL_SUBJECT.match(subject)
    ]
    assert bad == [], f"non-conventional commit subjects: {bad}"


def test_env_schema_tracked_and_env_is_ignored() -> None:
    """The varlock contract: schema committed, real env files never."""
    tracked = git("ls-files").splitlines()
    assert ".env.schema" in tracked, ".env.schema must be tracked"
    leaked = [
        path
        for path in tracked
        if path == ".env" or (path.startswith(".env.") and path != ".env.schema")
    ]
    assert leaked == [], f"no real .env file may be tracked: {leaked}"

    ignored = subprocess.run(
        ["git", "check-ignore", ".env"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0, ".env must be gitignored"


def test_skills_manifest_declares_a_source_for_every_skill() -> None:
    """A skill on disk without provenance breaks `scaffolding check` (CES-107)."""
    manifest = json.loads((REPO_ROOT / "skills-lock.json").read_text())
    entries = manifest["skills"] if isinstance(manifest, dict) else manifest
    assert entries, "skills-lock.json declares no skills"

    if isinstance(entries, dict):
        undeclared = [name for name, spec in entries.items() if not spec.get("source")]
        assert undeclared == [], f"skills declared without a source: {undeclared}"


def test_orq_lite_flow_roles_resolve_against_team_json() -> None:
    """Every role a compiled flow invokes must exist in team.json.

    Guards the failure mode where a flow references a role the config never
    declares: the role's fail-closed fallback fires and governance rejects the
    run for a reason unrelated to the code under review.
    """
    team_path = REPO_ROOT / "team.json"
    if not team_path.exists() or shutil.which("orq-lite") is None:
        pytest.skip("orq-lite runtime config not present in this checkout")

    declared = set(json.loads(team_path.read_text())["roles"])
    flows = orq_lite("flow", "list").split()
    assert flows, "orq-lite reports no installed flows"

    missing = {
        flow: sorted(roles_referenced_by(json.loads(orq_lite("flow", "inspect", flow))) - declared)
        for flow in flows
    }
    unresolved = {flow: roles for flow, roles in missing.items() if roles}
    assert unresolved == {}, f"flows reference roles absent from team.json: {unresolved}"


def test_the_package_is_importable_under_its_distribution_name() -> None:
    """`import pomodoro` must work, not `import src.pomodoro`."""
    assert importlib.util.find_spec("pomodoro") is not None, (
        "the pomodoro package is not importable"
    )


def test_wheel_packages_name_real_packages() -> None:
    """Every declared wheel package must be an importable package directory.

    Guards the defect the house template shipped: `packages = ["src"]` named the
    layout directory, so the wheel's top-level module was the `src` namespace
    package and `import pomodoro` raised ModuleNotFoundError. A layout directory
    is never a valid entry.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    packages = config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert packages, "no wheel packages declared"
    for entry in packages:
        path = REPO_ROOT / entry
        assert path.name not in {"src", "lib"}, (
            f"{entry!r} names a layout directory; name the package itself"
        )
        assert (path / "__init__.py").is_file(), f"{entry!r} is not a package"
