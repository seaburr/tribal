<script setup lang="ts">
import { ref, reactive, watch, onMounted, computed } from 'vue'
import type { Team, BannerLevel } from '../../types'
import { useAdminStore } from '../../stores/admin'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'
import { useResourcesStore } from '../../stores/resources'
import { useBannerStore } from '../../stores/banner'
import { BarChart3, Ban, CalendarClock, ClipboardList, RotateCcw, Trash2 } from '@lucide/vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import IconButton from '../common/IconButton.vue'
import Pagination from '../common/Pagination.vue'
import { useDateFormat } from '../../composables/useDateFormat'
import * as adminApi from '../../api/admin'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const resourcesStore = useResourcesStore()
const bannerStore = useBannerStore()
const { show } = useToast()
const { formatDateTime } = useDateFormat()

const loaded = ref(false)

onMounted(async () => {
  try {
    await Promise.all([
      adminStore.loadSettings(),
      adminStore.loadUsers(),
      adminStore.loadAuditLog(50, 0),
      adminStore.loadApiKeys(),
      adminStore.loadDeletedResources(),
      adminApi.listAdminTeams().then((t) => { teams.value = t }).catch(() => {}),
    ])
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to load admin data', 'error')
  } finally {
    loaded.value = true
  }
})

// ── Settings form ──────────────────────────────────────────────────────────────
const settingsForm = reactive({
  org_name: '',
  reminder_days: [] as number[],
  notify_hour: 9,
  slack_webhook: '',
  alert_on_overdue: false,
  alert_on_delete: false,
  alert_on_review_overdue: false,
  review_cadence_months: null as number | null,
  login_banner_enabled: false,
  login_banner_message: '',
  login_banner_level: 'warning' as BannerLevel,
  app_banner_enabled: false,
  app_banner_message: '',
  app_banner_level: 'info' as BannerLevel,
})

watch(
  () => adminStore.settings,
  (s) => {
    if (!s) return
    settingsForm.org_name = s.org_name ?? ''
    settingsForm.reminder_days = [...s.reminder_days]
    settingsForm.notify_hour = s.notify_hour
    settingsForm.slack_webhook = s.slack_webhook ?? ''
    settingsForm.alert_on_overdue = s.alert_on_overdue
    settingsForm.alert_on_delete = s.alert_on_delete
    settingsForm.alert_on_review_overdue = s.alert_on_review_overdue
    settingsForm.review_cadence_months = s.review_cadence_months
    settingsForm.login_banner_enabled = s.login_banner_enabled
    settingsForm.login_banner_message = s.login_banner_message ?? ''
    settingsForm.login_banner_level = s.login_banner_level
    settingsForm.app_banner_enabled = s.app_banner_enabled
    settingsForm.app_banner_message = s.app_banner_message ?? ''
    settingsForm.app_banner_level = s.app_banner_level
  },
  { immediate: true },
)

const reminderOptions = [1, 3, 7, 14, 30, 45, 60]
const bannerLevelOptions: { value: BannerLevel; label: string }[] = [
  { value: 'info', label: 'Info (blue)' },
  { value: 'warning', label: 'Warning (amber)' },
  { value: 'critical', label: 'Critical (red)' },
]

// Show the notify_hour (UTC) in the user's local timezone as a hint.
const notifyHourLocalHint = computed(() => {
  const tz = authStore.user?.timezone
  if (!tz) return null
  try {
    const utcDate = new Date(Date.UTC(2000, 0, 1, settingsForm.notify_hour, 0, 0))
    const localTime = utcDate.toLocaleTimeString(undefined, { timeZone: tz, hour: '2-digit', minute: '2-digit' })
    return `${localTime} in your timezone (${tz})`
  } catch {
    return null
  }
})

function toggleReminderDay(day: number) {
  const idx = settingsForm.reminder_days.indexOf(day)
  if (idx >= 0) settingsForm.reminder_days.splice(idx, 1)
  else settingsForm.reminder_days.push(day)
}

const savingSettings = ref(false)
async function saveSettings() {
  savingSettings.value = true
  try {
    const updated = await adminApi.updateAdminSettings({
      org_name: settingsForm.org_name || null,
      reminder_days: settingsForm.reminder_days,
      notify_hour: settingsForm.notify_hour,
      slack_webhook: settingsForm.slack_webhook || null,
      alert_on_overdue: settingsForm.alert_on_overdue,
      alert_on_delete: settingsForm.alert_on_delete,
      alert_on_review_overdue: settingsForm.alert_on_review_overdue,
      review_cadence_months: settingsForm.review_cadence_months,
      login_banner_enabled: settingsForm.login_banner_enabled,
      login_banner_message: settingsForm.login_banner_message || null,
      login_banner_level: settingsForm.login_banner_level,
      app_banner_enabled: settingsForm.app_banner_enabled,
      app_banner_message: settingsForm.app_banner_message || null,
      app_banner_level: settingsForm.app_banner_level,
    })
    adminStore.settings = updated
    resourcesStore.reviewCadenceMonths = updated.review_cadence_months
    // Refresh the live in-app banner so the change is reflected immediately.
    bannerStore.loadAppBanner()
    show('Settings saved', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Save failed', 'error')
  } finally {
    savingSettings.value = false
  }
}

async function testAdminWebhook() {
  try {
    await adminApi.testAdminWebhook(settingsForm.slack_webhook)
    show('Test webhook sent', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Webhook test failed', 'error')
  }
}

// ── Team settings ──────────────────────────────────────────────────────────────
const teams = ref<Team[]>([])
const teamName = ref('')
const editingTeam = ref<{ id: number; name: string } | null>(null)

async function saveTeam() {
  if (!teamName.value) return
  try {
    if (editingTeam.value) {
      await adminApi.updateTeam(editingTeam.value.id, teamName.value)
      show('Team updated', 'success')
    } else {
      await adminApi.createTeam(teamName.value)
      show('Team created', 'success')
    }
    const t = await adminApi.listAdminTeams()
    teams.value = t
    teamName.value = ''
    editingTeam.value = null
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to save team', 'error')
  }
}

// ── Users table ────────────────────────────────────────────────────────────────
const usersPage = ref(1)

async function handleRoleChange(userId: number, value: string) {
  try {
    if (value === 'readonly') {
      await adminApi.setUserReadonly(userId, true)
    } else if (value === 'admin') {
      await adminApi.setUserReadonly(userId, false)
      await adminApi.setUserRole(userId, true)
    } else {
      // member
      await adminApi.setUserReadonly(userId, false)
      await adminApi.setUserRole(userId, false)
    }
    await adminStore.loadUsers()
    show('Role updated', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to update role', 'error')
  }
}

function getUserRole(user: { is_admin: boolean; is_readonly: boolean }): string {
  if (user.is_readonly) return 'readonly'
  if (user.is_admin) return 'admin'
  return 'member'
}

// One dialog for the destructive actions below. `requireText` makes the user type the name for irreversible ones.
interface PendingConfirm {
  title: string
  message: string
  confirmLabel: string
  busyLabel: string
  requireText?: string
  run: () => Promise<void>
}
const pendingConfirm = ref<PendingConfirm | null>(null)
const lastConfirm = ref<PendingConfirm | null>(null)
const confirmBusy = ref(false)
watch(pendingConfirm, (p) => { if (p) lastConfirm.value = p })

async function runConfirm() {
  if (!pendingConfirm.value) return
  confirmBusy.value = true
  try {
    await pendingConfirm.value.run()
  } finally {
    confirmBusy.value = false
    pendingConfirm.value = null
  }
}

async function deleteUser(id: number) {
  try {
    await adminApi.deleteUser(id)
    await adminStore.loadUsers()
    show('User deleted', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to delete user', 'error')
  }
}

function handleDeleteUser(user: { id: number; email: string }) {
  pendingConfirm.value = {
    title: 'Delete user',
    message: `Delete ${user.email}? They will lose access to Tribal.`,
    confirmLabel: 'Delete user',
    busyLabel: 'Deleting…',
    run: () => deleteUser(user.id),
  }
}

// ── Admin API keys ─────────────────────────────────────────────────────────────
function handleRevokeAdminKey(key: { id: number; name: string }) {
  pendingConfirm.value = {
    title: 'Revoke API key',
    message: `Revoke "${key.name}"? Anything using it stops working immediately.`,
    confirmLabel: 'Revoke key',
    busyLabel: 'Revoking…',
    run: () => revokeAdminKey(key.id),
  }
}

async function revokeAdminKey(id: number) {
  try {
    await adminApi.revokeAdminApiKey(id)
    await adminStore.loadApiKeys()
    show('API key revoked', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to revoke key', 'error')
  }
}

// ── Audit log ──────────────────────────────────────────────────────────────────
const auditOffset = ref(50)

async function loadMoreAudit() {
  await adminStore.loadAuditLog(50, auditOffset.value)
  auditOffset.value += 50
}

// ── Reports ───────────────────────────────────────────────────────────────────
function openReport(url: string) {
  window.open(url)
}

// ── Deleted resources ──────────────────────────────────────────────────────────
async function handleRestore(id: number) {
  try {
    await adminApi.restoreResource(id)
    await adminStore.loadDeletedResources()
    await resourcesStore.load()
    show('Resource restored', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to restore', 'error')
  }
}

function handlePurge(id: number, name: string) {
  pendingConfirm.value = {
    title: 'Permanently delete resource',
    message: `This permanently removes "${name}" and cannot be undone.`,
    confirmLabel: 'Delete permanently',
    busyLabel: 'Deleting…',
    requireText: name,
    run: () => purge(id),
  }
}

async function purge(id: number) {
  try {
    await adminApi.purgeResource(id)
    await adminStore.loadDeletedResources()
    show('Resource permanently deleted', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to purge', 'error')
  }
}
</script>

<template>
  <div v-if="!authStore.user?.is_admin" class="py-12 text-center text-zinc-400">
    Admin access required.
  </div>

  <div v-else-if="!loaded" class="text-center py-12 text-zinc-400">
    Loading admin data…
  </div>

  <div v-else class="space-y-4">

    <!-- ── Team settings ────────────────────────────────────────────────────── -->
    <section class="card card-pad">
      <h2 class="section-title mb-1">Team settings</h2>
      <p class="meta mb-3">The team name is displayed across the application and included in Slack notifications.</p>
      <div class="space-y-3">
        <div v-if="teams.length > 0" class="space-y-2">
          <div
            v-for="team in teams"
            :key="team.id"
            class="flex items-center gap-2"
          >
            <input
              :value="editingTeam?.id === team.id ? teamName : team.name"
              :disabled="editingTeam?.id !== team.id"
              type="text"
              class="input flex-1"
              :aria-label="`Team name: ${team.name}`"
              @input="teamName = ($event.target as HTMLInputElement).value"
            />
            <template v-if="editingTeam?.id === team.id">
              <button type="button"
                class="btn-primary"
                @click="saveTeam"
              >Save</button>
              <button type="button"
                class="btn-secondary btn-sm"
                @click="editingTeam = null; teamName = ''"
              >Cancel</button>
            </template>
            <button type="button"
              v-else
              class="btn-secondary btn-sm"
              @click="editingTeam = { id: team.id, name: team.name }; teamName = team.name"
            >Edit</button>
          </div>
        </div>
        <div v-else class="flex items-center gap-2">
          <input
            v-model="teamName"
            type="text"
            placeholder="Team name"
            class="input flex-1"
          />
          <button type="button"
            class="btn-primary"
            @click="saveTeam"
          >
            Create team
          </button>
        </div>
      </div>
    </section>

    <!-- ── Announcement banners ──────────────────────────────────────────────── -->
    <section class="card card-pad">
      <h2 class="section-title mb-1">Announcement banners</h2>
      <p class="meta mb-3">Show a message across the top of the app. The login banner is visible publicly on the sign-in page; the in-app banner is shown to signed-in users.</p>

      <div class="space-y-6">
        <!-- Login banner -->
        <div class="space-y-3">
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="settingsForm.login_banner_enabled" type="checkbox" class="check" />
            <span class="text-sm font-medium text-zinc-300">Enable login page banner</span>
          </label>
          <div>
            <textarea
              v-model="settingsForm.login_banner_message"
              rows="2"
              maxlength="500"
              placeholder="e.g. This is a personal demo instance — do not store real credentials."
              class="input"
            />
          </div>
          <select
              v-model="settingsForm.login_banner_level"
              class="input w-auto"
            >
              <option v-for="opt in bannerLevelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
        </div>

        <!-- In-app banner -->
        <div class="space-y-3 border-t border-tribal-border pt-5">
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="settingsForm.app_banner_enabled" type="checkbox" class="check" />
            <span class="text-sm font-medium text-zinc-300">Enable in-app banner</span>
          </label>
          <div>
            <textarea
              v-model="settingsForm.app_banner_message"
              rows="2"
              maxlength="500"
              placeholder="e.g. Scheduled maintenance this Saturday 02:00–03:00 UTC."
              class="input"
            />
          </div>
          <select
              v-model="settingsForm.app_banner_level"
              class="input w-auto"
            >
              <option v-for="opt in bannerLevelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
        </div>

        <button type="button"
          :disabled="savingSettings"
          class="btn-primary"
          @click="saveSettings"
        >
          {{ savingSettings ? 'Saving…' : 'Save banners' }}
        </button>
      </div>
    </section>

    <!-- ── Notification settings ─────────────────────────────────────────────── -->
    <section class="card card-pad">
      <h2 class="section-title mb-1">Notification settings</h2>
      <p class="meta mb-3">Configure when and where Tribal sends Slack reminders about expiring resources.</p>

      <div class="space-y-5">
        <!-- Reminder days -->
        <div>
          <p class="label">Reminder days before expiry</p>
          <p class="help mb-2">Tribal will send a Slack notification on each selected day before a resource expires.</p>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="day in reminderOptions"
              :key="day"
              :class="[
                'btn cursor-pointer has-focus-visible:ring-2 has-focus-visible:ring-accent-blue-light',
                settingsForm.reminder_days.includes(day)
                  ? 'border-accent-blue/60 bg-accent-blue/20 text-accent-blue-light'
                  : 'border-tribal-border bg-tribal-card text-zinc-400 hover:border-zinc-500',
              ]"
            >
              <input
                type="checkbox"
                :checked="settingsForm.reminder_days.includes(day)"
                class="sr-only"
                @change="toggleReminderDay(day)"
              />
              {{ day }} days
            </label>
          </div>
        </div>

        <!-- Notify hour -->
        <div>
          <label for="admintab-field-2" class="label">Notify hour (UTC)</label>
          <p class="help mb-1">Notifications are dispatched once daily at this hour.</p>
          <select id="admintab-field-2"
              v-model.number="settingsForm.notify_hour"
              class="input w-auto"
            >
              <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00 UTC</option>
            </select>
          <p v-if="notifyHourLocalHint" class="help">≈ {{ notifyHourLocalHint }}</p>
        </div>

        <!-- Review cadence -->
        <div>
          <label for="admintab-field-3" class="label">Periodic review cadence</label>
          <p class="help mb-1">When enabled, resources not reviewed within this window will be flagged as overdue for review. Members can mark a resource reviewed from its detail view.</p>
          <select id="admintab-field-3"
              v-model="settingsForm.review_cadence_months"
              class="input w-auto"
            >
              <option :value="null">Disabled</option>
              <option :value="6">Every 6 months</option>
              <option :value="12">Every 12 months</option>
              <option :value="24">Every 24 months</option>
            </select>
        </div>

        <!-- Slack webhook -->
        <div>
          <label for="admintab-field-4" class="label">Tribal admins Slack webhook URL</label>
          <p class="help mb-1">Slack webhook used to notify Tribal admins when resources expire, reviews become overdue, or resources are deleted.</p>
          <div class="flex gap-2">
            <input id="admintab-field-4"
              v-model="settingsForm.slack_webhook"
              type="url"
              placeholder="https://hooks.slack.com/..."
              class="input flex-1"
            />
            <button
              :disabled="!settingsForm.slack_webhook"
              class="btn-secondary"
              type="button"
              @click="testAdminWebhook"
            >
              Test
            </button>
          </div>
        </div>

        <!-- Admin alert checkboxes -->
        <div class="space-y-2">
          <p class="help">Notify admins via the webhook above when:</p>
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="settingsForm.alert_on_overdue" type="checkbox" class="check" />
            <span class="text-sm text-zinc-300">Resources become overdue</span>
          </label>
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="settingsForm.alert_on_delete" type="checkbox" class="check" />
            <span class="text-sm text-zinc-300">Resources are deleted</span>
          </label>
          <label class="flex cursor-pointer items-center gap-2">
            <input v-model="settingsForm.alert_on_review_overdue" type="checkbox" class="check" />
            <span class="text-sm text-zinc-300">Reviews are overdue</span>
          </label>
        </div>

        <button type="button"
          :disabled="savingSettings"
          class="btn-primary"
          @click="saveSettings"
        >
          {{ savingSettings ? 'Saving…' : 'Save settings' }}
        </button>
      </div>
    </section>

    <!-- ── Reports ────────────────────────────────────────────────────────────── -->
    <section class="card card-pad">
      <h2 class="section-title mb-1">Reports</h2>
      <p class="meta mb-3">Download CSV snapshots for offline review or sharing with your team.</p>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button type="button"
          class="group flex flex-col items-start gap-1 rounded-md border border-tribal-border px-3 py-2.5 text-left transition-colors hover:border-zinc-500 hover:bg-tribal-card"
          @click="openReport('/admin/reports/upcoming')"
        >
          <span class="flex items-center gap-1.5 text-sm font-medium text-zinc-200 group-hover:text-white"><BarChart3 :size="16" aria-hidden="true" />Upcoming expiry</span>
          <span class="help">Resources expiring within the next 30 days.</span>
        </button>
        <button type="button"
          class="group flex flex-col items-start gap-1 rounded-md border border-tribal-border px-3 py-2.5 text-left transition-colors hover:border-zinc-500 hover:bg-tribal-card"
          @click="openReport('/admin/reports/recent-changes')"
        >
          <span class="flex items-center gap-1.5 text-sm font-medium text-zinc-200 group-hover:text-white"><ClipboardList :size="16" aria-hidden="true" />Recent changes</span>
          <span class="help">All audit log events from the last 30 days.</span>
        </button>
        <button type="button"
          class="group flex flex-col items-start gap-1 rounded-md border border-tribal-border px-3 py-2.5 text-left transition-colors hover:border-zinc-500 hover:bg-tribal-card"
          @click="openReport('/admin/reports/reviews-due')"
        >
          <span class="flex items-center gap-1.5 text-sm font-medium text-zinc-200 group-hover:text-white"><CalendarClock :size="16" aria-hidden="true" />Reviews due</span>
          <span class="help">Resources nearing (within 30 days) or overdue for review.</span>
        </button>
      </div>
    </section>

    <!-- ── Users ──────────────────────────────────────────────────────────────── -->
    <section class="card overflow-hidden">
      <div class="border-b border-tribal-border px-3 py-3 sm:px-4">
        <h2 class="section-title">Users</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="tbl">
          <thead>
            <tr class="bg-tribal-card">
              <th>Name / Email</th>
              <th>Role</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in adminStore.users.slice((usersPage - 1) * 25, usersPage * 25)"
              :key="user.id"
              class="hover:bg-tribal-card/50"
            >
              <td>
                <p class="text-white">{{ user.display_name || user.email }}</p>
                <p v-if="user.display_name" class="help">{{ user.email }}</p>
                <span v-if="user.is_account_creator" class="badge-info mt-1">Account creator</span>
              </td>
              <td>
                <select
                    :aria-label="`Role for ${user.email}`"
                    :value="getUserRole(user)"
                    :disabled="user.id === authStore.user?.id || user.is_account_creator"
                    class="input w-auto"
                    @change="handleRoleChange(user.id, ($event.target as HTMLSelectElement).value)"
                  >
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                    <option value="readonly">Read-only</option>
                  </select>
              </td>
              <td class="text-right">
                <IconButton :icon="Trash2" label="Delete user" danger sm :disabled="user.id === authStore.user?.id || user.is_account_creator" @click="handleDeleteUser(user)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="border-t border-tribal-border">
        <Pagination
          :total="adminStore.users.length"
          :page="usersPage"
          :per-page="25"
          @update:page="usersPage = $event"
        />
      </div>
    </section>

    <!-- ── Admin API Keys ─────────────────────────────────────────────────────── -->
    <section class="card overflow-hidden">
      <div class="border-b border-tribal-border px-3 py-3 sm:px-4">
        <h2 class="section-title">API keys (all users)</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="tbl">
          <thead>
            <tr class="bg-tribal-card">
              <th>Name</th>
              <th>Owner</th>
              <th>Prefix</th>
              <th>Last used</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="key in adminStore.apiKeys"
              :key="key.id"
              :class="[
                'border-b border-tribal-border/50 hover:bg-tribal-card/50 transition-colors',
                key.revoked_at ? 'opacity-50' : '',
              ]"
            >
              <td class="text-white">{{ key.name }}</td>
              <td class="text-zinc-400">{{ key.user_email }}</td>
              <td class="mono text-zinc-400">{{ key.key_prefix }}</td>
              <td class="text-zinc-400">{{ formatDateTime(key.last_used_at) }}</td>
              <td class="text-right">
                <IconButton v-if="!key.revoked_at" :icon="Ban" label="Revoke API key" danger sm @click="handleRevokeAdminKey(key)" />
                <span v-else class="badge-neutral">Revoked</span>
              </td>
            </tr>
            <tr v-if="adminStore.apiKeys.length === 0">
              <td colspan="5" class="py-8 text-center text-zinc-400">No API keys found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ── Audit Log ──────────────────────────────────────────────────────────── -->
    <section class="card overflow-hidden">
      <div class="border-b border-tribal-border px-3 py-3 sm:px-4">
        <h2 class="section-title">Audit log</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="tbl">
          <thead>
            <tr class="bg-tribal-card">
              <th>Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Resource</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in adminStore.auditLog"
              :key="entry.id"
              class="hover:bg-tribal-card/50"
            >
              <td class="text-zinc-400 whitespace-nowrap text-xs">{{ formatDateTime(entry.created_at) }}</td>
              <td class="text-zinc-300">{{ entry.user_email ?? '—' }}</td>
              <td>
                <span class="mono text-zinc-300">{{ entry.action }}</span>
              </td>
              <td class="text-zinc-400">{{ entry.resource_name ?? '—' }}</td>
            </tr>
            <tr v-if="adminStore.auditLog.length === 0">
              <td colspan="4" class="py-8 text-center text-zinc-400">No audit log entries.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="border-t border-tribal-border px-3 py-2">
        <button type="button"
          class="btn-ghost btn-sm"
          @click="loadMoreAudit"
        >
          Load more
        </button>
      </div>
    </section>

    <!-- ── Deleted Resources ──────────────────────────────────────────────────── -->
    <section class="card overflow-hidden">
      <div class="border-b border-tribal-border px-3 py-3 sm:px-4">
        <h2 class="section-title">Deleted resources</h2>
        <p class="meta mt-1">Restore returns a resource to the active list. Purge permanently removes it and cannot be undone.</p>
      </div>
      <div class="overflow-x-auto">
        <table class="tbl">
          <thead>
            <tr class="bg-tribal-card">
              <th>Name</th>
              <th>Type</th>
              <th>DRI</th>
              <th>Deleted at</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="resource in adminStore.deletedResources"
              :key="resource.id"
              class="hover:bg-tribal-card/50"
            >
              <td class="text-white">{{ resource.name }}</td>
              <td class="text-zinc-400">{{ resource.type }}</td>
              <td class="text-zinc-400">{{ resource.dri }}</td>
              <td class="text-zinc-400 text-xs">{{ formatDateTime(resource.deleted_at) }}</td>
              <td class="text-right">
                <div class="flex justify-end gap-1">
                  <IconButton :icon="RotateCcw" label="Restore" sm @click="handleRestore(resource.id)" />
                  <IconButton :icon="Trash2" label="Purge" danger sm @click="handlePurge(resource.id, resource.name)" />
                </div>
              </td>
            </tr>
            <tr v-if="adminStore.deletedResources.length === 0">
              <td colspan="5" class="py-8 text-center text-zinc-400">No deleted resources.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ConfirmDialog
      :open="pendingConfirm !== null"
      :title="lastConfirm?.title ?? ''"
      :message="lastConfirm?.message ?? ''"
      :confirm-label="lastConfirm?.confirmLabel"
      :busy-label="lastConfirm?.busyLabel"
      :require-text="pendingConfirm?.requireText"
      :busy="confirmBusy"
      danger
      @confirm="runConfirm"
      @cancel="pendingConfirm = null"
    />
  </div>
</template>
