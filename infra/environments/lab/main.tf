locals {
  # The design and the policies are data. The same files are checked and simulated by the landing-zone tool.
  design      = yamldecode(file("${path.module}/../../../design/landing-zone.yaml"))
  policy_file = yamldecode(file("${path.module}/../../../policies/org-policies.yaml"))

  organization = "organizations/${var.org_id}"
  region       = local.design.shared_vpc.region
  host_name    = local.design.shared_vpc.host_project

  projects    = { for p in local.design.projects : p.name => p }
  project_ids = { for name, _ in local.projects : name => "${name}-${var.name_suffix}" }
  subnets     = { for s in local.design.shared_vpc.subnets : s.name => s }
  bucket_name = "${local.design.sensitive_data.bucket}-${var.name_suffix}"

  # APIs per project role. The perimeter restricts Cloud Storage in the data project, so that one needs it.
  services = {
    data    = ["iam.googleapis.com", "logging.googleapis.com", "storage.googleapis.com"]
    service = ["compute.googleapis.com", "iam.googleapis.com", "logging.googleapis.com"]
    host    = ["compute.googleapis.com", "logging.googleapis.com"]
  }

  policies = [
    for p in local.policy_file.policies : {
      constraint     = p.constraint
      kind           = p.kind
      enforce        = try(p.enforce, false)
      allowed_values = try(p.allowed_values, [])
      deny_all       = try(p.deny_all, false)
      folder         = startswith(try(p.level, "organization"), "folder:") ? trimprefix(p.level, "folder:") : null
    }
  ]

  access_levels = {
    for level in local.design.access_levels : level.name => coalesce(var.office_ip_subnetworks, level.ip_subnetworks)
  }

  # The test identity that stands in for each team, by service project.
  testers = {
    "prod-app" = module.lab_identities.team_prod_member
    "dev-app"  = module.lab_identities.team_dev_member
  }
}

module "folders" {
  source = "../../modules/folders"

  parent = local.organization
  names  = [for f in local.design.folders : f.name]
}

module "projects" {
  source   = "../../modules/project"
  for_each = local.projects

  name            = each.key
  project_id      = local.project_ids[each.key]
  folder_id       = module.folders.ids[each.value.folder]
  billing_account = var.billing_account
  services        = local.services[each.value.role]
  labels          = var.labels
}

# Step 2. Set once, at the top. Written in dry-run mode first: violations are logged and nothing is blocked.
module "org_policies" {
  source = "../../modules/org-policies"

  organization   = local.organization
  folder_parents = module.folders.names
  mode           = var.policy_mode
  policies       = local.policies
}

module "lab_identities" {
  source = "../../modules/lab-identities"

  prod_app_project_id = module.projects["prod-app"].project_id
  dev_app_project_id  = module.projects["dev-app"].project_id
  data_project_id     = module.projects["prod-data"].project_id
  operator_member     = var.operator_member
}

# Step 3. A host project with a shared VPC; each team may use only its own subnet.
module "shared_vpc" {
  source = "../../modules/shared-vpc"

  host_project_id = module.projects[local.host_name].project_id
  service_projects = {
    for s in local.design.shared_vpc.subnets : s.service_project => module.projects[s.service_project].project_id
  }
  network_name = local.design.shared_vpc.network
  region       = local.region
  subnets = {
    for name, s in local.subnets : name => {
      cidr  = s.cidr
      users = concat(s.user_groups, [local.testers[s.service_project]])
    }
  }
}

module "sensitive_bucket" {
  source = "../../modules/sensitive-bucket"

  project_id     = module.projects[local.design.sensitive_data.project].project_id
  name           = local.bucket_name
  location       = local.region
  labels         = var.labels
  force_destroy  = true
  viewer_members = { data_reader = module.lab_identities.data_reader_member }
}

# Steps 4 and 5. The perimeter surrounds the data project only. Dry run first; enforce when the logs are clean.
module "perimeter" {
  source = "../../modules/perimeter"

  organization        = local.organization
  access_policy_id    = var.access_policy_id
  name                = local.design.perimeter.name
  title               = local.design.perimeter.title
  project_numbers     = [for name in local.design.perimeter.projects : module.projects[name].number]
  restricted_services = local.design.perimeter.restricted_services
  access_levels       = local.access_levels
  access_level_names  = local.design.perimeter.access_levels
  mode                = var.perimeter_mode
}
