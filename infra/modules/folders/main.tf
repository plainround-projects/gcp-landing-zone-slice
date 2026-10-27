resource "google_folder" "this" {
  for_each = toset(var.names)

  display_name        = each.value
  parent              = var.parent
  deletion_protection = var.deletion_protection
}
