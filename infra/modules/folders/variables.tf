variable "parent" {
  description = "Parent of every folder: organizations/ID or folders/ID."
  type        = string

  validation {
    condition     = can(regex("^(organizations|folders)/[0-9]+$", var.parent))
    error_message = "parent must look like organizations/123456789012 or folders/123456789012."
  }
}

variable "names" {
  description = "Display names of the folders to create."
  type        = list(string)

  validation {
    condition     = length(var.names) == length(distinct(var.names))
    error_message = "Folder names must be unique."
  }
}

variable "deletion_protection" {
  description = "Refuse to delete the folders. False for a lab so the teardown works."
  type        = bool
  default     = false
}
