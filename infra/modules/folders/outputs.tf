output "ids" {
  description = "Folder name => folder id (the number only)."
  value       = { for name, folder in google_folder.this : name => folder.folder_id }
}

output "names" {
  description = "Folder name => resource name (folders/ID), the form parents take."
  value       = { for name, folder in google_folder.this : name => folder.name }
}
