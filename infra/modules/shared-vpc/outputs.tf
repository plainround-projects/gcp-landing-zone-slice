output "network" {
  description = "Self link of the shared network."
  value       = google_compute_network.this.self_link
}

output "subnets" {
  description = "Subnet name => self link."
  value       = { for name, subnet in google_compute_subnetwork.this : name => subnet.self_link }
}

output "subnet_cidrs" {
  description = "Subnet name => CIDR range."
  value       = { for name, subnet in var.subnets : name => subnet.cidr }
}
