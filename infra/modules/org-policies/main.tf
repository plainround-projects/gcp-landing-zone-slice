locals {
  # One policy per constraint per level: the key is the constraint plus where it is set.
  policies = { for p in var.policies : "${p.constraint}@${coalesce(p.folder, "organization")}" => p }

  parents = {
    for key, p in local.policies : key => p.folder == null ? var.organization : var.folder_parents[p.folder]
  }

  # The rule each policy carries, as the three optional fields of the provider's rules block.
  rules = {
    for key, p in local.policies : key => {
      enforce        = p.kind == "boolean" ? (p.enforce ? "TRUE" : "FALSE") : null
      deny_all       = p.kind == "list" && p.deny_all ? "TRUE" : null
      allowed_values = p.kind == "list" ? p.allowed_values : []
    }
  }
}

# The dry-run spec is always written, so every change is visible in the audit logs before it is enforced.
# The enforced spec is written only when mode = "enforced".
resource "google_org_policy_policy" "this" {
  for_each = local.policies

  name   = "${local.parents[each.key]}/policies/${each.value.constraint}"
  parent = local.parents[each.key]

  dry_run_spec {
    rules {
      enforce  = local.rules[each.key].enforce
      deny_all = local.rules[each.key].deny_all

      dynamic "values" {
        for_each = length(local.rules[each.key].allowed_values) > 0 ? [1] : []
        content {
          allowed_values = local.rules[each.key].allowed_values
        }
      }
    }
  }

  dynamic "spec" {
    for_each = var.mode == "enforced" ? [1] : []
    content {
      rules {
        enforce  = local.rules[each.key].enforce
        deny_all = local.rules[each.key].deny_all

        dynamic "values" {
          for_each = length(local.rules[each.key].allowed_values) > 0 ? [1] : []
          content {
            allowed_values = local.rules[each.key].allowed_values
          }
        }
      }
    }
  }
}
