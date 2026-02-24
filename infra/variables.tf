variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "artifact_registry_repository" {
  type    = string
  default = "weather-eval"
}

variable "processed_data_bucket_name" {
  description = "GCS bucket for processed weather artifacts used in Docker builds"
  type        = string
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
  default = "2Gi"
}

variable "cloud_run_cpu" {
  description = "CPU limit for Cloud Run container"
  type        = string
  default     = "1000m"
}

variable "cloud_run_concurrency" {
  description = "Max concurrent requests per Cloud Run instance"
  type        = number
  default     = 1
}

variable "image" {
  description = "Container image URI deployed to Cloud Run"
  type        = string
}

variable "github_actions_deployer_sa_email" {
  description = "GitHub Actions deployer SA email. When set, Terraform grants deploy/runtime and processed-data read IAM."
  type        = string
  default     = null
}
