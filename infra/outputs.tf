output "bucket" {
  value = google_storage_bucket.data.name
}

output "repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "api_service_account" {
  value = google_service_account.api.email
}
