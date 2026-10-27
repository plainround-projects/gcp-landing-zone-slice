variable "organization" {
  description = "organizations/ID, the parent of the access policy."
  type        = string

  validation {
    condition     = can(regex("^organizations/[0-9]+$", var.organization))
    error_message = "organization must look like organizations/123456789012."
  }
}

variable "access_policy_id" {
  description = "Id (the number) of the organization's existing access policy. Empty creates one."
  type        = string
  default     = ""
}

variable "name" {
  description = "Perimeter name: letters, digits and underscores."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,49}$", var.name))
    error_message = "name must start with a letter and contain letters, digits and underscores only."
  }
}

variable "title" {
  description = "Human-readable title."
  type        = string
}

variable "project_numbers" {
  description = "Numbers of the projects inside the perimeter."
  type        = list(string)

  validation {
    condition     = length(var.project_numbers) > 0
    error_message = "A perimeter around no project protects nothing."
  }
}

variable "restricted_services" {
  description = "Services the perimeter restricts, for example storage.googleapis.com."
  type        = list(string)

  validation {
    condition     = length(var.restricted_services) > 0
    error_message = "Restrict at least one service."
  }
}

variable "access_levels" {
  description = "Access level name => IP ranges whose callers count as trusted."
  type        = map(list(string))
  default     = {}
}

variable "access_level_names" {
  description = "Names of the access levels the perimeter accepts (a subset of access_levels)."
  type        = list(string)
  default     = []
}

variable "mode" {
  description = "dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.mode)
    error_message = "mode must be dry_run or enforced."
  }
}
