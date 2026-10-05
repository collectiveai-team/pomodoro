"""Guards for the backend scaffold itself (T1): layering, boundary rules, env schema.

These check the scaffold's own structural guarantees rather than feature behavior,
so they run as meta/tooling tests (no `unit` marker) alongside `test_repo_invariants.py`.
"""

from __future__ import annotations

import ast
import os
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "backend" / "pomodoro" / "core"
FORBIDDEN_FRAMEWORK_MODULES = {"fastapi", "sqlmodel", "pydantic"}


def _top_level_module(name: str) -> str:
    return name.split(".", 1)[0]


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(_top_level_module(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(_top_level_module(node.module))
    return modules


def test_core_package_has_zero_framework_imports() -> None:
    """`core` must stay importable without fastapi/sqlmodel/pydantic installed."""
    offenders: dict[str, set[str]] = {}
    for path in CORE_DIR.rglob("*.py"):
        found = _imported_modules(path.read_text()) & FORBIDDEN_FRAMEWORK_MODULES
        if found:
            offenders[str(path.relative_to(REPO_ROOT))] = found

    assert offenders == {}, f"core modules import framework code: {offenders}"


def test_import_linter_contracts_declare_layering_and_forbidden_rules() -> None:
    """The layers and api-boundary contracts (story 89) must both be configured."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    contracts = config["tool"]["importlinter"]["contracts"]
    types_present = {contract["type"] for contract in contracts}

    assert "layers" in types_present
    assert "forbidden" in types_present

    layers_contract = next(c for c in contracts if c["type"] == "layers")
    assert layers_contract["layers"] == [
        "pomodoro.entrypoints",
        "pomodoro.api",
        "pomodoro.database",
        "pomodoro.core",
    ]

    forbidden_contract = next(c for c in contracts if c["type"] == "forbidden")
    assert set(forbidden_contract["source_modules"]) == {"pomodoro.core", "pomodoro.database"}
    assert "pomodoro.api" in forbidden_contract["forbidden_modules"]


def test_import_linter_gate_is_currently_green() -> None:
    """`uv run lint-imports` must pass on the current tree (the CI gate)."""
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_import_linter_fails_the_gate_on_a_reversed_import(tmp_path: Path) -> None:
    """A `core -> api` import must break the layers contract (negative control)."""
    violating_root = tmp_path / "violation"
    package = violating_root / "pomodoro"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    for layer in ("entrypoints", "api", "database", "core"):
        (package / layer).mkdir()
        (package / layer / "__init__.py").write_text("")
    # core importing api violates the house layering direction.
    (package / "core" / "__init__.py").write_text("import pomodoro.api\n")

    config = """
[tool.importlinter]
root_package = "pomodoro"

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = [
  "pomodoro.entrypoints",
  "pomodoro.api",
  "pomodoro.database",
  "pomodoro.core",
]
"""
    (violating_root / "pyproject.toml").write_text(config)

    lint_imports = REPO_ROOT / ".venv" / "bin" / "lint-imports"
    result = subprocess.run(
        [str(lint_imports)],
        cwd=violating_root,
        env={**os.environ, "PYTHONPATH": str(violating_root)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0, "a reversed-layer import must fail the import-linter gate"


def test_ast_grep_rejects_a_bare_dict_return_at_a_boundary(tmp_path: Path) -> None:
    """The ast-grep rule set must flag `-> dict` and dict-literal returns."""
    offender = tmp_path / "boundary.py"
    offender.write_text("def boundary() -> dict:\n    return {'a': 1}\n")

    result = subprocess.run(
        ["ast-grep", "scan", "--config", str(REPO_ROOT / "sgconfig.yml"), str(offender)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0, "a bare dict return at a boundary must fail ast-grep"
    assert "no-dict-return-annotation" in result.stdout
    assert "no-dict-literal-return" in result.stdout


def test_env_schema_defines_database_url_with_local_sqlite_default() -> None:
    """`.env.schema` must declare `DATABASE_URL` defaulting to SQLite under `.tmp/`."""
    content = (REPO_ROOT / ".env.schema").read_text()

    assert "DATABASE_URL=sqlite:///.tmp/" in content
