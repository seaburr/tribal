export interface User {
  id: number
  email: string
  display_name: string | null
  is_admin: boolean
  is_readonly: boolean
  is_account_creator: boolean
}

export interface Resource {
  id: number
  name: string
  dri: string
  type: string // 'Certificate' | 'API Key' | 'SSH Key' | 'Other'
  expiration_date: string | null // ISO date string YYYY-MM-DD
  does_not_expire: boolean
  purpose: string
  generation_instructions: string
  secret_manager_link: string | null
  slack_webhook: string
  team_id: number | null
  certificate_url: string | null
  auto_refresh_expiry: boolean
  provider: string | null
  last_reviewed_at: string | null // ISO datetime
  created_at: string
  updated_at: string
}

export interface DeletedResource extends Resource {
  deleted_at: string
}

export interface Team {
  id: number
  name: string
  created_at: string
}

export interface AdminSettings {
  org_name: string | null
  reminder_days: number[]
  notify_hour: number
  slack_webhook: string | null
  alert_on_overdue: boolean
  alert_on_delete: boolean
  alert_on_review_overdue: boolean
  review_cadence_months: number | null
}

export interface AuditEntry {
  id: number
  user_email: string | null
  resource_id: number | null
  resource_name: string | null
  action: string
  detail: Record<string, unknown> | null
  created_at: string
}

export interface ApiKey {
  id: number
  name: string
  key_prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export interface ApiKeyCreated extends ApiKey {
  full_key: string
}

export interface AdminApiKey extends ApiKey {
  user_email: string
}

export interface KeyIdentifyResponse {
  provider: string | null
  expires_at: string | null
  metadata: Record<string, unknown>
  rotation_url: string | null
  rotation_steps: string[]
  matched: boolean
}

export interface Provider {
  name: string
  display_name: string
}

export type ResourceType = 'Certificate' | 'API Key' | 'SSH Key' | 'Other'
