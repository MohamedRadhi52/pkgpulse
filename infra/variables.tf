variable "project_id" {
  description = "Identifiant du projet GCP"
  type        = string
}

variable "region" {
  description = "Région de toutes les ressources : l'offre gratuite de Cloud Storage est aux États-Unis"
  type        = string
  default     = "us-central1"
}
