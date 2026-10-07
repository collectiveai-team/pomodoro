locals {
  github_repository_name = split("/", var.github_repository)[1]
}

data "github_user" "prod_reviewers" {
  for_each = toset(var.prod_reviewer_users)
  username = each.value
}

resource "github_repository_environment" "qa" {
  repository  = local.github_repository_name
  environment = "qa"
  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "qa_main" {
  repository     = local.github_repository_name
  environment    = github_repository_environment.qa.environment
  branch_pattern = "main"
}

resource "github_repository_environment" "prod" {
  repository  = local.github_repository_name
  environment = "prod"
  reviewers {
    users = [for user in data.github_user.prod_reviewers : tonumber(user.id)]
  }
  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "prod_releases" {
  repository  = local.github_repository_name
  environment = github_repository_environment.prod.environment
  tag_pattern = "v*"
}

# Not secrets: WIF means there are no keys to hide.
resource "github_actions_variable" "shared" {
  for_each = {
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    WIF_PROVIDER   = google_iam_workload_identity_pool_provider.github.name
    DEPLOYER_SA    = google_service_account.deployer.email
  }
  repository    = local.github_repository_name
  variable_name = each.key
  value         = each.value
}

locals {
  github_environments = {
    qa   = github_repository_environment.qa.environment
    prod = github_repository_environment.prod.environment
  }
  environment_variables = merge([
    for name, env in module.environment : {
      "${name}/SERVICE_NAME"     = { environment = local.github_environments[name], name = "SERVICE_NAME", value = env.service_name }
      "${name}/MIGRATE_JOB_NAME" = { environment = local.github_environments[name], name = "MIGRATE_JOB_NAME", value = env.migrate_job_name }
    }
  ]...)
}

resource "github_actions_environment_variable" "per_environment" {
  for_each      = local.environment_variables
  repository    = local.github_repository_name
  environment   = each.value.environment
  variable_name = each.value.name
  value         = each.value.value
}
