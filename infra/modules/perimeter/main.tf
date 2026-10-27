locals {
  access_policy_id = var.access_policy_id != "" ? var.access_policy_id : google_access_context_manager_access_policy.this[0].name
  parent           = "accessPolicies/${local.access_policy_id}"
  level_names      = [for name in var.access_level_names : "${local.parent}/accessLevels/${name}"]
  resources        = [for number in var.project_numbers : "projects/${number}"]
}

# One access policy per organization. Give access_policy_id to reuse the organization's existing one.
resource "google_access_context_manager_access_policy" "this" {
  count = var.access_policy_id == "" ? 1 : 0

  parent = var.organization
  title  = "${var.name} access policy"
}

# Callers from these ranges count as inside the trusted network (your office or home address).
resource "google_access_context_manager_access_level" "this" {
  for_each = var.access_levels

  parent = local.parent
  name   = "${local.parent}/accessLevels/${each.key}"
  title  = each.key

  basic {
    conditions {
      ip_subnetworks = each.value
    }
  }
}

# `spec` is the dry-run configuration: violations are logged and nothing is blocked.
# `status` is the enforced configuration and is written only when mode = "enforced".
resource "google_access_context_manager_service_perimeter" "this" {
  parent         = local.parent
  name           = "${local.parent}/servicePerimeters/${var.name}"
  title          = var.title
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  use_explicit_dry_run_spec = true

  spec {
    resources           = local.resources
    restricted_services = var.restricted_services
    access_levels       = local.level_names
  }

  dynamic "status" {
    for_each = var.mode == "enforced" ? [1] : []
    content {
      resources           = local.resources
      restricted_services = var.restricted_services
      access_levels       = local.level_names
    }
  }

  depends_on = [google_access_context_manager_access_level.this]
}
