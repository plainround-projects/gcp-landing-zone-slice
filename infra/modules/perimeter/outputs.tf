output "access_policy_id" {
  description = "Id of the access policy the perimeter belongs to."
  value       = local.access_policy_id
}

output "perimeter_name" {
  description = "Full resource name of the perimeter."
  value       = google_access_context_manager_service_perimeter.this.name
}

output "mode" {
  description = "dry_run or enforced."
  value       = var.mode
}
