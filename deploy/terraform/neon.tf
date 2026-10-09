# Neon project with branches prod (default) and qa (child of prod). Each has its own compute
# endpoint that suspends when idle. QA gets its own role and database: a child branch inherits
# prod's roles *with prod's password*, and the provider cannot rotate an inherited role.

resource "neon_project" "pomodoro" {
  name                      = "pomodoro"
  region_id                 = "aws-sa-east-1"
  pg_version                = 17
  history_retention_seconds = 86400

  branch {
    name          = "prod"
    database_name = "pomodoro"
    role_name     = "pomodoro"
  }
}

resource "neon_branch" "qa" {
  project_id = neon_project.pomodoro.id
  parent_id  = neon_project.pomodoro.default_branch_id
  name       = "qa"
}

resource "neon_endpoint" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  type       = "read_write"
}

resource "neon_role" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  name       = "pomodoro_qa"
}

resource "neon_database" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  name       = "pomodoro_qa"
  owner_name = neon_role.qa.name
}

locals {
  database_urls = sensitive({
    prod = "postgresql+psycopg://${neon_project.pomodoro.database_user}:${urlencode(neon_project.pomodoro.database_password)}@${neon_project.pomodoro.database_host}/${neon_project.pomodoro.database_name}?sslmode=require"
    qa   = "postgresql+psycopg://${neon_role.qa.name}:${urlencode(neon_role.qa.password)}@${neon_endpoint.qa.host}/${neon_database.qa.name}?sslmode=require"
  })
}
