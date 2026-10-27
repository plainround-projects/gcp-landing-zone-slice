output "team_prod_member" {
  description = "IAM member of the team-prod test identity."
  value       = "serviceAccount:${google_service_account.team_prod.email}"
}

output "team_dev_member" {
  description = "IAM member of the team-dev test identity."
  value       = "serviceAccount:${google_service_account.team_dev.email}"
}

output "data_reader_member" {
  description = "IAM member of the data reader."
  value       = "serviceAccount:${google_service_account.data_reader.email}"
}

output "emails" {
  description = "Emails of the three test identities."
  value = {
    team_prod   = google_service_account.team_prod.email
    team_dev    = google_service_account.team_dev.email
    data_reader = google_service_account.data_reader.email
  }
}
