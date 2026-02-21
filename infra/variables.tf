variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "firestore_location" {
  type    = string
  default = "us-central1"
}

variable "artifact_registry_repository" {
  type    = string
  default = "weather-eval"
}

variable "cloud_run_service_name" {
  type    = string
  default = "weather-eval"
}

variable "cloud_run_min_instances" {
  type    = number
  default = 0
}

variable "cloud_run_max_instances" {
  type    = number
  default = 1
}

variable "cloud_run_memory" {
  type    = string
  default = "256Mi"
}

variable "image" {
  description = "Container image URI deployed to Cloud Run"
  type        = string
}
