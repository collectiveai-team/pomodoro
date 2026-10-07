variable "project_id" {
  type        = string
  description = "GCP project that hosts both environments."
}

variable "region" {
  type        = string
  default     = "southamerica-east1"
  description = "Region for Cloud Run, Artifact Registry and Secret Manager replicas."
}

variable "github_repository" {
  type        = string
  default     = "collectiveai-team/pomodoro"
  description = "owner/name of the only repository allowed to deploy through WIF."
}

variable "prod_reviewer_users" {
  type        = list(string)
  description = "GitHub logins that must approve every prod deploy."
}

variable "environments" {
  type = map(object({
    cpu    = string
    memory = string
  }))
  default = {
    qa   = { cpu = "1", memory = "1Gi" }
    prod = { cpu = "1", memory = "1Gi" }
  }
  description = "Per-environment Cloud Run resources."

  validation {
    condition     = toset(keys(var.environments)) == toset(["qa", "prod"])
    error_message = "environments must define exactly qa and prod."
  }
}
