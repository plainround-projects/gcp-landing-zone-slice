resource "google_storage_bucket" "this" {
  #checkov:skip=CKV_GCP_62:A lab needs no separate access-log bucket; the data-access audit logs and the perimeter's violation logs record the calls that matter here
  #checkov:skip=CKV_GCP_114:Public access prevention is enforced below; checkov looks for it under another attribute name
  project  = var.project_id
  name     = var.name
  location = var.location
  labels   = var.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = true
  }
}

# The data reader holds objectViewer on this bucket only. It is the principal the attack runs as: IAM allows the read.
resource "google_storage_bucket_iam_member" "viewer" {
  for_each = var.viewer_members

  bucket = google_storage_bucket.this.name
  role   = "roles/storage.objectViewer"
  member = each.value
}
