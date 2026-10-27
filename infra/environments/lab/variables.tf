variable "org_id" {
  description = "Organization id (gcloud organizations list). A free Cloud Identity domain gives you one."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must contain digits only."
  }
}

variable "billing_account" {
  description = "Billing account id (gcloud billing accounts list)."
  type        = string
}

variable "quota_project_id" {
  description = "An existing project that is charged for the organization-level API calls (scripts/bootstrap.sh creates it)."
  type        = string
}

variable "name_suffix" {
  description = "Appended to project ids and the bucket name, which are global: 3 to 6 lowercase letters or digits."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,6}$", var.name_suffix))
    error_message = "name_suffix must be 3 to 6 lowercase letters or digits."
  }
}

variable "operator_member" {
  description = "Who runs the proofs and may impersonate the test identities, for example user:you@example-lab.org."
  type        = string
}

variable "policy_mode" {
  description = "dry_run writes only the policies' dry-run spec (violations are logged, nothing is blocked); enforced also enforces them."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.policy_mode)
    error_message = "policy_mode must be dry_run or enforced."
  }
}

variable "perimeter_mode" {
  description = "dry_run logs what the perimeter would block; enforced blocks it. Always run dry_run first."
  type        = string
  default     = "dry_run"

  validation {
    condition     = contains(["dry_run", "enforced"], var.perimeter_mode)
    error_message = "perimeter_mode must be dry_run or enforced."
  }
}

variable "access_policy_id" {
  description = "Id (the number) of the organization's existing access policy. Empty creates one; an organization can have only one."
  type        = string
  default     = ""
}

variable "office_ip_subnetworks" {
  description = "Address ranges of the 'office' access level. Null keeps the design file's documentation range, which matches nobody, so a laptop is outside the access level (step 5's second attack)."
  type        = list(string)
  default     = null
}

variable "labels" {
  description = "Labels applied to every project and bucket."
  type        = map(string)
  default = {
    environment = "lab"
    project     = "landing-zone-slice"
    managed-by  = "terraform"
  }
}
