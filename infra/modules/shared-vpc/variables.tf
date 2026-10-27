variable "host_project_id" {
  description = "Id of the host project that owns the network."
  type        = string
}

variable "service_projects" {
  description = "Service projects attached to the host, keyed by a fixed label (the project name)."
  type        = map(string)
}

variable "network_name" {
  description = "Name of the shared VPC network."
  type        = string
}

variable "region" {
  description = "Region of every subnet."
  type        = string
}

variable "subnets" {
  description = "Subnets by name: the CIDR range and the IAM members that may use the subnet (roles/compute.networkUser)."
  type = map(object({
    cidr  = string
    users = list(string)
  }))

  validation {
    condition     = alltrue([for s in values(var.subnets) : can(cidrhost(s.cidr, 0))])
    error_message = "Every subnet needs a valid CIDR range."
  }

  validation {
    condition     = alltrue([for s in values(var.subnets) : length(s.users) > 0])
    error_message = "A subnet nobody may use is a mistake: give it at least one user."
  }
}
