variable "prod_app_project_id" {
  description = "Project id of prod-app."
  type        = string
}

variable "dev_app_project_id" {
  description = "Project id of dev-app."
  type        = string
}

variable "data_project_id" {
  description = "Project id of prod-data."
  type        = string
}

variable "operator_member" {
  description = "Who may impersonate the test identities, for example user:you@example-lab.org."
  type        = string

  validation {
    condition     = can(regex("^(user|group|serviceAccount):", var.operator_member))
    error_message = "operator_member must start with user:, group: or serviceAccount:."
  }
}
