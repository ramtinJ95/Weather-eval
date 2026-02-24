terraform {
  required_version = ">= 1.8.0"

  backend "gcs" {}

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
  required_services = toset([
    "artifactregistry.googleapis.com",

    "run.googleapis.com",
    "storage.googleapis.com",
  ])

  github_actions_deployer_member = (
    var.github_actions_deployer_sa_email != null && trimspace(var.github_actions_deployer_sa_email) != ""
  ) ? "serviceAccount:${trimspace(var.github_actions_deployer_sa_email)}" : null
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "docker" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_registry_repository
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket" "processed_data" {
  name                        = var.processed_data_bucket_name
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = false
  uniform_bucket_level_access = true

  depends_on = [google_project_service.required]
}

resource "google_service_account" "cloud_run" {
  project      = var.project_id
  account_id   = "weather-eval-cloudrun"
  display_name = "Cloud Run runtime SA"
}

resource "google_project_iam_member" "github_actions_run_admin" {
  count = local.github_actions_deployer_member == null ? 0 : 1

  project = var.project_id
  role    = "roles/run.admin"
  member  = local.github_actions_deployer_member
}

resource "google_project_iam_member" "github_actions_artifact_registry_writer" {
  count = local.github_actions_deployer_member == null ? 0 : 1

  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = local.github_actions_deployer_member
}

resource "google_storage_bucket_iam_member" "github_actions_processed_data_reader" {
  count = local.github_actions_deployer_member == null ? 0 : 1

  bucket = google_storage_bucket.processed_data.name
  role   = "roles/storage.objectViewer"
  member = local.github_actions_deployer_member
}

resource "google_service_account_iam_member" "github_actions_act_as_cloud_run_runtime" {
  count = local.github_actions_deployer_member == null ? 0 : 1

  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.github_actions_deployer_member
}

resource "google_cloud_run_v2_service" "app" {
  name     = var.cloud_run_service_name
  location = var.region

  template {
    service_account                  = google_service_account.cloud_run.email
    max_instance_request_concurrency = var.cloud_run_concurrency

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = var.image
      ports {
        container_port = 8080
      }

      resources {
        cpu_idle = true
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

    }
  }

  ingress = "INGRESS_TRAFFIC_ALL"

  depends_on = [
    google_project_service.required,
  ]
}

resource "google_cloud_run_service_iam_member" "public" {
  location = google_cloud_run_v2_service.app.location
  service  = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.app.uri
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.docker.id
}

output "processed_data_bucket" {
  value = google_storage_bucket.processed_data.name
}
