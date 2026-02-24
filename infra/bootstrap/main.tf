terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.20"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  foundation_apis = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
  ])
}

resource "google_project_service" "foundation" {
  for_each = local.foundation_apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "terraform_state" {
  name                        = var.state_bucket_name
  location                    = var.state_bucket_location
  force_destroy               = false
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }
}

output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}
