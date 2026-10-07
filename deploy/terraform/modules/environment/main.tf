locals {
  prefix = "pomodoro-${var.name}"
}

resource "google_service_account" "runtime" {
  account_id   = "${local.prefix}-run"
  display_name = "Pomodoro ${var.name} runtime"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${local.prefix}-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_url
}

resource "google_secret_manager_secret_iam_member" "runtime_reads_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.runtime.member
}

resource "google_cloud_run_v2_service" "app" {
  name                = local.prefix
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.name == "prod"

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle = true
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      # entrypoint.sh only starts nginx once uvicorn and Next answer, so this passing means all
      # three are up. 20 x 3s leaves room for a cold start.
      startup_probe {
        http_get {
          path = "/api/health"
        }
        period_seconds    = 3
        timeout_seconds   = 2
        failure_threshold = 20
      }

      liveness_probe {
        http_get {
          path = "/api/health"
        }
        period_seconds  = 30
        timeout_seconds = 5
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_reads_database_url]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "migrate" {
  name                = "${local.prefix}-migrate"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.runtime.email
      max_retries     = 0
      timeout         = "600s"

      containers {
        image   = var.image
        command = ["/app/backend/scripts/migrate.sh"]

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_reads_database_url]
}

# The deployer may change images and run the job; it cannot touch IAM or the rest of the shape.
resource "google_cloud_run_v2_service_iam_member" "deployer" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.developer"
  member   = var.deployer_member
}

resource "google_cloud_run_v2_job_iam_member" "deployer" {
  name     = google_cloud_run_v2_job.migrate.name
  location = var.region
  role     = "roles/run.developer"
  member   = var.deployer_member
}

resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.deployer_member
}
