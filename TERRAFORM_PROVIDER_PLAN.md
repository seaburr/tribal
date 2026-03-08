# Tribal Terraform Provider — Design Plan

A custom Terraform provider would allow teams to manage Tribal resources as infrastructure-as-code, enabling expiration tracking to live alongside the systems they describe.

---

## Provider Overview

```hcl
terraform {
  required_providers {
    tribal = {
      source  = "seaburr/tribal"
      version = "~> 1.0"
    }
  }
}

provider "tribal" {
  endpoint = "https://dev.tribal-app.xyz"
  api_key  = var.tribal_api_key  # or TRIBAL_API_KEY env var
}
```

---

## Resources

### `tribal_resource`

Manages a tracked resource (certificate, API key, SSH key, etc.).

```hcl
resource "tribal_resource" "prod_tls" {
  name                     = "Production TLS Certificate"
  dri                      = "platform-team"
  type                     = "Certificate"
  expiration_date          = "2026-06-01"
  purpose                  = "Secures api.example.com"
  generation_instructions  = "Run: certbot renew --cert-name api.example.com"
  slack_webhook            = var.platform_slack_webhook

  # Optional
  secret_manager_link      = "https://vault.example.com/certs/prod-tls"
}
```

**Computed attributes (read from API after create/import):**
- `id` — Tribal resource ID
- `created_at`, `updated_at`

**Lifecycle behaviour:**
- `create` → `POST /api/resources/`
- `read` → `GET /api/resources/{id}`
- `update` → `PUT /api/resources/{id}`
- `delete` → `DELETE /api/resources/{id}` (triggers Slack deletion notification)
- `import` → `terraform import tribal_resource.prod_tls <id>`

---

## Data Sources

### `tribal_resource` (singular)

Look up an existing resource by ID without managing it.

```hcl
data "tribal_resource" "existing" {
  id = 42
}

output "expiration" {
  value = data.tribal_resource.existing.expiration_date
}
```

### `tribal_resources` (plural)

Return all resources, optionally filtered.

```hcl
data "tribal_resources" "certificates" {
  type = "Certificate"  # optional filter
}
```

---

## Authentication

The provider authenticates via a Tribal API key (Bearer token). The key can be:

1. Set directly in the provider block via `api_key` (use a sensitive variable or `TF_VAR_tribal_api_key`)
2. Set via the `TRIBAL_API_KEY` environment variable (preferred for CI/CD)

API keys are managed through the Tribal UI (Account → API Keys) or the Admin panel.

---

## Application Changes Required

### 1. `via` field in audit log *(already implemented in Iteration 11)*

All mutating API calls now record `"via": "api"` in the audit log detail. Tribal UI actions record `"via": "ui"`. This means Terraform-driven changes will appear in the audit log as:

```
Updated via API  (DRI: platform-team, updated_fields: [expiration_date])
```

### 2. No additional API changes needed

The existing REST API (`/api/resources/`) already provides full CRUD and is suitable as a provider backend. The `expiration_date` field accepts both `YYYY-MM-DD` and `MM/DD/YYYY` formats; the provider should normalise to `YYYY-MM-DD` before sending.

---

## Implementation Plan

### Tech stack

- **Language:** Go (required for Terraform providers)
- **Framework:** [Terraform Plugin Framework](https://developer.hashicorp.com/terraform/plugin/framework) (v1+)
- **HTTP client:** Standard `net/http` or `go-resty`
- **Registry:** [Terraform Registry](https://registry.terraform.io/) under `seaburr/tribal`

### Repository structure

```
terraform-provider-tribal/
  internal/
    client/
      client.go          # HTTP client wrapping the Tribal REST API
      resources.go       # Resource CRUD helpers
    provider/
      provider.go        # Provider schema and configuration
      resource_resource.go   # tribal_resource resource
      datasource_resource.go # tribal_resource data source
      datasource_resources.go # tribal_resources data source
  examples/
    basic/               # Example Terraform config
  GNUmakefile
  .goreleaser.yml        # Release pipeline for Registry publishing
```

### Implementation steps

1. **Go client** — thin HTTP wrapper around the Tribal API; handles auth header, JSON marshal/unmarshal, and error mapping to Terraform diagnostics.
2. **Provider** — configure `endpoint` + `api_key`; validate connectivity in `Configure`.
3. **`tribal_resource` resource** — implement `Create`, `Read`, `Update`, `Delete`, `ImportState`. Map all Tribal resource fields to Terraform schema.
4. **Data sources** — `tribal_resource` (by ID) and `tribal_resources` (list with optional type filter).
5. **Acceptance tests** — set `TF_ACC=1` + `TRIBAL_API_KEY` pointing at a test instance; cover create/read/update/delete/import lifecycle.
6. **Release** — GoReleaser + GitHub Actions publishes signed binaries to the Terraform Registry.

### Estimated effort

| Step | Complexity |
|---|---|
| Go HTTP client | Low — wraps 4 REST endpoints |
| Provider + resource | Medium — straightforward schema mapping |
| Data sources | Low |
| Acceptance tests | Medium — requires a running Tribal instance |
| Registry publishing | Low — template-driven |

---

## Future Extensions

- `tribal_admin_settings` resource — manage notification settings via Terraform
- Import support for existing resources by name (currently by ID only)
- Drift detection on `expiration_date` (alert if the cert in the secret manager differs from Tribal)
