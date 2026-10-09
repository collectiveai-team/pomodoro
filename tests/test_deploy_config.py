"""Static guards for the Cloud Run deploy configuration (deploy/, deploy.yml, Terraform).

They read tracked files only, so they run in the default unit suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"


@pytest.mark.unit
def test_entrypoint_binds_internal_processes_to_loopback_only() -> None:
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "--host 127.0.0.1 --port 8000" in entrypoint
    assert "HOSTNAME=127.0.0.1" in entrypoint


@pytest.mark.unit
def test_entrypoint_keeps_uvicorn_default_proxy_trust() -> None:
    """Trust stays at 127.0.0.1 (nginx); a blanket trust would reopen the rate-limit bypass."""
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "--forwarded-allow-ips" not in entrypoint
    assert "FORWARDED_ALLOW_IPS" not in entrypoint
    # Pre-written fix, applied only if QA shows the key collapsed to Google's front end.
    runbook = (REPO_ROOT / "docs" / "deploy.md").read_text()
    assert "FORWARDED_ALLOW_IPS=169.254.0.0/16" in runbook


@pytest.mark.unit
def test_nginx_maps_api_health_to_backend_health_route() -> None:
    nginx = (DEPLOY_DIR / "nginx.conf.template").read_text()
    assert re.search(
        r"location = /api/health \{\s*proxy_pass http://127\.0\.0\.1:8000/health;", nginx
    )
    assert "location /api/ {" in nginx
    assert "listen __PORT__;" in nginx


@pytest.mark.unit
def test_app_image_never_migrates_on_start() -> None:
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "alembic" not in entrypoint
    assert "migrate.sh" not in entrypoint


@pytest.mark.unit
def test_app_image_runs_as_non_root() -> None:
    dockerfile = (DEPLOY_DIR / "Dockerfile").read_text()
    user_lines = [line for line in dockerfile.splitlines() if line.startswith("USER ")]
    assert user_lines, "deploy/Dockerfile must drop root"
    assert user_lines[-1].split()[1].split(":")[0] not in {"0", "root"}


TERRAFORM_DIR = DEPLOY_DIR / "terraform"


@pytest.mark.unit
def test_workload_identity_only_accepts_this_repository() -> None:
    shared = (TERRAFORM_DIR / "shared.tf").read_text()
    # CEL evaluated by Google, so the repository is interpolated into a quoted string literal.
    assert 'assertion.repository == \\"${var.github_repository}\\"' in shared
    assert '"attribute.ref"         = "assertion.ref"' in shared
    assert '"attribute.environment" = "assertion.environment"' in shared
    # Only main (build + QA) or the reviewer-gated prod environment may impersonate the deployer.
    assert 'assertion.ref == \\"refs/heads/main\\"' in shared
    assert 'has(assertion.environment) && assertion.environment == \\"prod\\"' in shared
    member = re.search(r'member\s+=\s+"(principalSet://[^"]+)"', shared)
    assert member
    assert member.group(1).endswith("/attribute.repository/${var.github_repository}")


@pytest.mark.unit
def test_qa_database_has_its_own_role_and_password() -> None:
    """QA must not reuse prod's inherited role: a leaked QA secret must not open prod."""
    neon = (TERRAFORM_DIR / "neon.tf").read_text()
    assert re.search(r'name\s+=\s+"pomodoro_qa"', neon)
    assert "neon_role.qa.password" in neon
    assert "sslmode=require" in neon


@pytest.mark.unit
def test_terraform_never_reverts_the_deployed_image() -> None:
    """Terraform owns the shape, the pipeline owns the image (spec, "Principios")."""
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert main.count("ignore_changes") == 2
    assert "template[0].containers[0].image" in main
    assert "template[0].template[0].containers[0].image" in main


@pytest.mark.unit
def test_cloud_run_scales_between_zero_and_one() -> None:
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert "min_instance_count = 0" in main
    assert "max_instance_count = 1" in main


@pytest.mark.unit
def test_runtime_identity_reads_only_its_own_secret() -> None:
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert "google_secret_manager_secret_iam_member" in main
    assert "google_project_iam_member" not in main


@pytest.mark.unit
def test_cloud_run_resources_wait_for_the_secret_version() -> None:
    """Revisions resolve secret version "latest" on create, so it must already exist."""
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    depends = re.findall(r"depends_on\s*=\s*\[([^\]]*)\]", main)
    with_version = [d for d in depends if "google_secret_manager_secret_version.database_url" in d]
    assert len(with_version) == 2


@pytest.mark.unit
def test_prod_environment_requires_reviewers_and_release_tags() -> None:
    github = (TERRAFORM_DIR / "github.tf").read_text()
    assert "reviewers {" in github
    assert re.search(r'tag_pattern\s+=\s+"v\*"', github)
    for name in (
        "GCP_PROJECT_ID",
        "GCP_REGION",
        "WIF_PROVIDER",
        "DEPLOYER_SA",
        "SERVICE_NAME",
        "MIGRATE_JOB_NAME",
    ):
        assert name in github


WORKFLOWS = REPO_ROOT / ".github" / "workflows"


@pytest.mark.unit
def test_prod_deploy_never_builds_an_image() -> None:
    deploy = (WORKFLOWS / "deploy.yml").read_text()
    prod_job = deploy.split("  deploy-prod:", 1)[1]
    assert "docker build" not in prod_job
    assert "verify-release.sh" in prod_job


@pytest.mark.unit
def test_deploy_workflow_has_no_default_permissions_and_never_cancels_a_deploy() -> None:
    deploy = (WORKFLOWS / "deploy.yml").read_text()
    assert "\npermissions: {}\n" in deploy
    assert deploy.count("cancel-in-progress: false") == 3
    assert "cancel-in-progress: true" not in deploy
    assert re.search(r"\nconcurrency:\n  group: deploy-\$\{\{ github.event_name \}\}\n", deploy)
    assert deploy.count("timeout-minutes:") == 3
    assert "!github.event.release.prerelease" in deploy


@pytest.mark.unit
def test_deploy_ci_runs_guards_on_deploy_only_changes() -> None:
    ci = (WORKFLOWS / "deploy-ci.yml").read_text()
    assert "deploy-guards:" in ci
    assert "tests/test_deploy_config.py tests/test_deploy_scripts.py" in ci
    for path in (
        ".github/workflows/deploy.yml",
        ".github/actions/deploy-env/**",
        ".github/actions/setup-backend/**",
        "docs/deploy.md",
        "tests/test_deploy_config.py",
        "tests/test_deploy_scripts.py",
    ):
        assert f'"{path}"' in ci
    assert ci.count("timeout-minutes:") == 3


@pytest.mark.unit
def test_prod_reviewers_cannot_be_empty() -> None:
    variables = (TERRAFORM_DIR / "variables.tf").read_text()
    block = variables.split('variable "prod_reviewer_users"', 1)[1].split("\nvariable ", 1)[0]
    assert "length(var.prod_reviewer_users) > 0" in block


@pytest.mark.unit
def test_image_context_excludes_untracked_secrets_and_data() -> None:
    ignore = (DEPLOY_DIR / "Dockerfile.dockerignore").read_text().splitlines()
    for pattern in ("**/.env*", "**/*.db", "**/.tmp/", "**/.venv/", "**/node_modules/"):
        assert pattern in ignore


@pytest.mark.unit
def test_runbook_covers_every_operation_the_spec_lists() -> None:
    runbook = (REPO_ROOT / "docs" / "deploy.md").read_text()
    for heading in (
        "## Bootstrap",
        "## Primer apply",
        "## Primer deploy",
        "## Verificación del rate limit en QA",
        "## Promoción a prod",
        "## Rollback manual",
        "## Reset de QA desde prod",
        "## Rotación de secretos y tokens",
        "## Subir max-instances",
    ):
        assert heading in runbook
