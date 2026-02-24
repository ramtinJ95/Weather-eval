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

  deployer_member = (
    var.deployer_sa_email != null && trimspace(var.deployer_sa_email) != ""
  ) ? "serviceAccount:${trimspace(var.deployer_sa_email)}" : null

  deployer_project_roles = toset([
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/serviceusage.serviceUsageAdmin",
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

resource "google_storage_bucket_iam_member" "deployer_state_access" {
  count = local.deployer_member == null ? 0 : 1

  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectAdmin"
  member = local.deployer_member
}

resource "google_project_iam_member" "deployer_terraform_roles" {
  for_each = local.deployer_member != null ? local.deployer_project_roles : toset([])

  project = var.project_id
  role    = each.value
  member  = local.deployer_member

  depends_on = [google_project_service.foundation]
}

output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}
