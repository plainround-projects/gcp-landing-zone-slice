terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.8"
    }
  }

  # Local state is enough for a lab. A real landing zone keeps its state in a locked bucket (see backend.tf.example).
}

provider "google" {
  # Organization policies and Access Context Manager are charged to a quota project, which must already exist
  # and have those APIs enabled: scripts/bootstrap.sh creates it.
  user_project_override = true
  billing_project       = var.quota_project_id
}
