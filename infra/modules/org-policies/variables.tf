variable "organization" {
  description = "organizations/ID, the parent of organization-level policies."
  type        = string

  validation {
    condition     = can(regex("^organizations/[0-9]+$", var.organization))
    error_message = "organization must look like organizations/123456789012."
  }
}

variable "folder_parents" {
  description = "Folder name => folders/ID, for policies set at folder level."
  type        = map(string)
  default     = {}
}

variable "mode" {
  description = "dry_run writes only the dry-run spec (violations are logged, nothing is blocked); enforced also writes the real spec."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.mode)
    error_message = "mode must be dry_run or enforced."
  }
}

variable "policies" {
  description = "The policy entries of policies/org-policies.yaml."
  type = list(object({
    constraint     = string
    kind           = string
    enforce        = optional(bool, false)
    allowed_values = optional(list(string), [])
    deny_all       = optional(bool, false)
    folder         = optional(string)
  }))

  validation {
    condition     = alltrue([for p in var.policies : contains(["boolean", "list"], p.kind)])
    error_message = "kind must be boolean or list."
  }

  validation {
    condition     = alltrue([for p in var.policies : p.kind == "boolean" || (length(p.allowed_values) > 0) != p.deny_all])
    error_message = "A list policy needs exactly one of allowed_values and deny_all."
  }
}
