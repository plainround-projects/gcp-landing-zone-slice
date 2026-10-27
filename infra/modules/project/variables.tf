variable "name" {
  description = "Display name, also the lesson's project name."
  type        = string
}

variable "project_id" {
  description = "Globally unique project id (6-30 characters)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be 6-30 characters: lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "folder_id" {
  description = "Folder the project lives in (the number only)."
  type        = string
}

variable "billing_account" {
  description = "Billing account id."
  type        = string
}

variable "services" {
  description = "APIs to enable."
  type        = list(string)
  default     = []
}

variable "audit_all_services" {
  description = "Turn on admin-read, data-read and data-write audit logs for every service in the project."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels for the project."
  type        = map(string)
  default     = {}
}

variable "deletion_policy" {
  description = "PREVENT, ABANDON or DELETE. DELETE in a lab so terraform destroy schedules the project for deletion."
  type        = string
  default     = "DELETE"

  validation {
    condition     = contains(["PREVENT", "ABANDON", "DELETE"], var.deletion_policy)
    error_message = "deletion_policy must be PREVENT, ABANDON or DELETE."
  }
}
