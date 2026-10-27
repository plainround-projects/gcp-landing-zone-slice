variable "project_id" {
  description = "Project that owns the bucket."
  type        = string
}

variable "name" {
  description = "Globally unique bucket name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$", var.name))
    error_message = "name must be 3-63 characters: lowercase letters, digits, dot, underscore and hyphen."
  }
}

variable "location" {
  description = "Bucket location; the organization policy only allows EU locations."
  type        = string
}

variable "viewer_members" {
  description = "Members that may read objects in this bucket, keyed by a fixed label."
  type        = map(string)
  default     = {}
}

variable "force_destroy" {
  description = "Delete the bucket even when it holds objects. True only for a lab."
  type        = bool
  default     = false
}

variable "labels" {
  description = "Labels for the bucket."
  type        = map(string)
  default     = {}
}
