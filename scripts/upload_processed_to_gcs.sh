#!/usr/bin/env bash
set -euo pipefail

# Upload local processed weather artifacts to GCS for CI/CD Docker builds.
#
# Usage:
#   scripts/upload_processed_to_gcs.sh <bucket-name> [prefix]
#
# Example:
#   scripts/upload_processed_to_gcs.sh my-weather-data-bucket processed/current

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI is required but not found in PATH."
  exit 1
fi

BUCKET_NAME="${1:-}"
PREFIX="${2:-processed/current}"
LOCAL_DIR="backend/data/processed"

if [[ -z "${BUCKET_NAME}" ]]; then
  echo "Usage: $0 <bucket-name> [prefix]"
  exit 1
fi

if [[ ! -d "${LOCAL_DIR}" ]]; then
  echo "Local processed directory not found: ${LOCAL_DIR}"
  exit 1
fi

DESTINATION="gs://${BUCKET_NAME}/${PREFIX}"

echo "Uploading processed artifacts from ${LOCAL_DIR} to ${DESTINATION}"
gcloud storage rsync --recursive --delete-unmatched-destination-objects "${LOCAL_DIR}" "${DESTINATION}"

echo "Upload complete. Listing destination objects:"
gcloud storage ls -l "${DESTINATION}/**"
