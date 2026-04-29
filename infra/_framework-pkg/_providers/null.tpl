# Null provider — for TG units that only use null_resource (local-exec).
# No cloud credentials required.
terraform {
  required_version = ">= 1.3.0"
  required_providers {
    null = { source = "hashicorp/null", version = "~> 3.0" }
  }
}
