terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.9"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

# Credentials come only from the environment at apply time (docs/deploy.md):
# Google via `gcloud auth application-default login`, NEON_API_KEY, GITHUB_TOKEN.
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "neon" {}

provider "github" {
  owner = split("/", var.github_repository)[0]
}
