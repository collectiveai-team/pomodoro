module "environment" {
  source   = "./modules/environment"
  for_each = var.environments

  name            = each.key
  region          = var.region
  image           = "${local.image_repository}:bootstrap"
  database_url    = local.database_urls[each.key]
  deployer_member = google_service_account.deployer.member
  cpu             = each.value.cpu
  memory          = each.value.memory

  depends_on = [google_project_service.apis]
}
