variable "name" {
  type        = string
  description = "Environment name: qa or prod."
}

variable "region" {
  type = string
}

variable "image" {
  type        = string
  description = "Initial image only; deploys change it outside Terraform (ignore_changes)."
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "deployer_member" {
  type        = string
  description = "IAM member of the CI deployer service account."
}

variable "cpu" {
  type = string
}

variable "memory" {
  type = string
}
