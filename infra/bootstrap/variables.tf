variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "state_bucket_name" {
  type = string
}

variable "state_bucket_location" {
  type    = string
  default = "US-CENTRAL1"
}

variable "deployer_sa_email" {
  description = "GitHub Actions deployer SA email. When set, bootstrap grants it terraform management roles and state bucket access."
  type        = string
  default     = null
}
