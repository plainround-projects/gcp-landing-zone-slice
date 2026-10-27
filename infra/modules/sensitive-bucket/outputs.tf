output "name" {
  description = "Bucket name."
  value       = google_storage_bucket.this.name
}

output "viewer_members" {
  description = "Members granted objectViewer."
  value       = sort(values(var.viewer_members))
}
