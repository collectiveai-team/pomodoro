output "image_repository" {
  value = local.image_repository
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_sa" {
  value = google_service_account.deployer.email
}

output "service_uris" {
  value = { for name, env in module.environment : name => env.service_uri }
}
