mock_provider "google" {}

variables {
  project_id     = "prod-data-ab12cd"
  name           = "prod-data-sensitive-ab12cd"
  location       = "europe-west1"
  viewer_members = { data_reader = "serviceAccount:data-reader@prod-data-ab12cd.iam.gserviceaccount.com" }
}

run "the_bucket_is_private_and_uniform_and_in_the_eu" {
  command = plan

  assert {
    condition     = google_storage_bucket.this.uniform_bucket_level_access && google_storage_bucket.this.public_access_prevention == "enforced" && lower(google_storage_bucket.this.location) == "europe-west1"
    error_message = "Private, uniform, EU."
  }
}

run "only_the_listed_member_may_read" {
  command = plan

  assert {
    condition     = length(google_storage_bucket_iam_member.viewer) == 1 && alltrue([for b in google_storage_bucket_iam_member.viewer : b.role == "roles/storage.objectViewer"])
    error_message = "One objectViewer binding."
  }
}
