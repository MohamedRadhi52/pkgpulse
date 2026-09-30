# Infrastructure du projet. Le reste (projet, facturation, API activées, compte de service de la
# CI) est créé une fois à la main : voir docs/DECISIONS.md, décision 15.

terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.5"
    }
  }

  # Le bucket de l'état est passé à terraform init par le workflow.
  backend "gcs" {
    prefix = "pkgpulse"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Couche bronze (Parquet) et exports du pipeline, lus par BigQuery et par l'API.
resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-pkgpulse"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

resource "google_bigquery_dataset" "layers" {
  for_each = toset(["bronze", "silver", "gold", "snapshots"])

  dataset_id                 = each.key
  location                   = var.region
  delete_contents_on_destroy = true
}

resource "google_artifact_registry_repository" "images" {
  repository_id = "pkgpulse"
  location      = var.region
  format        = "DOCKER"

  # Deux images suffisent (la courante et la précédente) : l'offre gratuite s'arrête à 0,5 Go.
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "garder-les-deux-dernieres"
    action = "KEEP"

    most_recent_versions {
      keep_count = 2
    }
  }

  cleanup_policies {
    id     = "supprimer-les-autres"
    action = "DELETE"

    condition {
      older_than = "86400s"
    }
  }
}

# Identité de l'API sur Cloud Run : lecture seule des exports.
resource "google_service_account" "api" {
  account_id   = "pkgpulse-api"
  display_name = "API PkgPulse sur Cloud Run"
}

resource "google_storage_bucket_iam_member" "api_reads_data" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.api.email}"
}
