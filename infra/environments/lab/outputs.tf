output "project_ids" {
  description = "Design name => project id."
  value       = local.project_ids
}

output "project_numbers" {
  description = "Design name => project number."
  value       = { for name, project in module.projects : name => project.number }
}

output "folders" {
  description = "Folder name => folders/ID."
  value       = module.folders.names
}

output "policy_constraints" {
  description = "Constraint@level of every organization policy."
  value       = module.org_policies.constraints
}

output "policy_mode" {
  description = "dry_run or enforced."
  value       = module.org_policies.mode
}

output "subnet_cidrs" {
  description = "Shared VPC subnet => CIDR range."
  value       = module.shared_vpc.subnet_cidrs
}

output "perimeter" {
  description = "Perimeter resource name and mode."
  value = {
    name = module.perimeter.perimeter_name
    mode = module.perimeter.mode
  }
}

output "access_policy_id" {
  description = "Access policy the perimeter belongs to."
  value       = module.perimeter.access_policy_id
}

output "sensitive_bucket" {
  description = "The bucket that holds customers.csv."
  value       = module.sensitive_bucket.name
}

output "test_identities" {
  description = "Emails of the identities the proofs impersonate."
  value       = module.lab_identities.emails
}
