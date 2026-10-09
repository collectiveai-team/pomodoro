# The bucket is the only resource created by hand (docs/deploy.md, "Bootstrap"):
#   terraform init -backend-config="bucket=<project>-tfstate"
# The state holds Neon connection strings: treat it as a secret.
terraform {
  backend "gcs" {
    prefix = "pomodoro"
  }
}
