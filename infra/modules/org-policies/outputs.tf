output "constraints" {
  description = "Constraint@level of every policy managed here."
  value       = sort(keys(local.policies))
}

output "mode" {
  description = "dry_run or enforced."
  value       = var.mode
}
