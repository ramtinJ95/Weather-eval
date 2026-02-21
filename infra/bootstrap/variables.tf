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
