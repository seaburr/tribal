<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import type { Team } from '../../types'
import { useAdminStore } from '../../stores/admin'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'
import { useResourcesStore } from '../../stores/resources'
import Pagination from '../common/Pagination.vue'
import { formatDateTime } from '../../utils/date'
import * as adminApi from '../../api/admin'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const resourcesStore = useResourcesStore()
const { show } = useToast()

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
  },
  { immediate: true },
)

const reminderOptions = [1, 3, 7, 14, 30, 45, 60]

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
    })
    adminStore.settings = updated
    resourcesStore.reviewCadenceMonths = updated.review_cadence_months
    show('Settings saved', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Save failed', 'error')
  } finally {
    savingSettings.value = false
  }
}

async function testAdminWebhook() {
  try {
    await adminApi.testAdminWebhook()
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

async function handleDeleteUser(id: number) {
  if (!confirm('Delete this user?')) return
  try {
    await adminApi.deleteUser(id)
    await adminStore.loadUsers()
    show('User deleted', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to delete user', 'error')
  }
}

// ── Admin API keys ─────────────────────────────────────────────────────────────
async function handleRevokeAdminKey(id: number) {
  if (!confirm('Revoke this API key?')) return
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

async function handlePurge(id: number, name: string) {
  if (!confirm(`Permanently delete "${name}"? This cannot be undone.`)) return
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
  <div v-if="!authStore.user?.is_admin" class="text-center py-12 text-zinc-500">
    Admin access required.
  </div>

  <div v-else-if="!loaded" class="text-center py-12 text-zinc-400">
    Loading admin data...
  </div>

  <div v-else class="space-y-8">

    <!-- ── Team Settings ────────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-base font-semibold text-white mb-1">Team Settings</h2>
      <p class="text-zinc-500 text-sm mb-4">The team name is displayed across the application and included in Slack notifications.</p>
      <div class="space-y-3">
        <div v-if="teams.length > 0" class="space-y-2">
          <div
            v-for="team in teams"
            :key="team.id"
            class="flex items-center gap-3"
          >
            <input
              v-if="editingTeam?.id === team.id"
              v-model="teamName"
              type="text"
              class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
            />
            <span v-else class="flex-1 text-white text-sm">{{ team.name }}</span>
            <button
              v-if="editingTeam?.id !== team.id"
              class="text-xs px-3 py-1.5 border border-tribal-border text-zinc-400 hover:border-blue-500/50 hover:text-blue-400 rounded-lg transition-colors"
              @click="editingTeam = { id: team.id, name: team.name }; teamName = team.name"
            >Edit</button>
            <button
              v-else
              class="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors"
              @click="saveTeam"
            >Save</button>
          </div>
        </div>
        <div v-else class="flex items-center gap-3">
          <input
            v-model="teamName"
            type="text"
            placeholder="Team name"
            class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          <button
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm transition-colors"
            @click="saveTeam"
          >
            Create Team
          </button>
        </div>
      </div>
    </section>

    <!-- ── Notification Settings ─────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-base font-semibold text-white mb-1">Notification Settings</h2>
      <p class="text-zinc-500 text-sm mb-5">Configure when and where Tribal sends Slack reminders about expiring resources.</p>

      <div class="space-y-5">
        <!-- Reminder days -->
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-1">Reminder days before expiry</label>
          <p class="text-zinc-500 text-xs mb-2">Tribal will send a Slack notification on each selected day before a resource expires.</p>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="day in reminderOptions"
              :key="day"
              :class="[
                'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm cursor-pointer transition-colors',
                settingsForm.reminder_days.includes(day)
                  ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                  : 'bg-tribal-card border-tribal-border text-zinc-400 hover:border-blue-500/30',
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
          <label class="block text-sm font-medium text-zinc-300 mb-1">Notify hour (UTC)</label>
          <p class="text-zinc-500 text-xs mb-1">Notifications are dispatched once daily at this hour.</p>
          <select
            v-model.number="settingsForm.notify_hour"
            class="bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00 UTC</option>
          </select>
        </div>

        <!-- Review cadence -->
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-1">Periodic review cadence</label>
          <p class="text-zinc-500 text-xs mb-1">When enabled, resources not reviewed within this window will be flagged as overdue for review. Members can mark a resource reviewed from its detail view.</p>
          <select
            v-model="settingsForm.review_cadence_months"
            class="bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option :value="null">Disabled</option>
            <option :value="6">Every 6 months</option>
            <option :value="12">Every 12 months</option>
            <option :value="24">Every 24 months</option>
          </select>
        </div>

        <!-- Slack webhook -->
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-1">Global Slack Webhook URL</label>
          <p class="text-zinc-500 text-xs mb-1">Fallback notification channel for admin alerts. Individual resources can specify their own webhook to notify the owning team directly.</p>
          <div class="flex gap-2">
            <input
              v-model="settingsForm.slack_webhook"
              type="url"
              placeholder="https://hooks.slack.com/..."
              class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
            <button
              :disabled="!settingsForm.slack_webhook"
              class="px-4 py-2 border border-tribal-border text-zinc-400 hover:border-blue-500/50 hover:text-blue-400 rounded-lg text-sm transition-colors disabled:opacity-50"
              type="button"
              @click="testAdminWebhook"
            >
              Test
            </button>
          </div>
        </div>

        <!-- Alert checkboxes -->
        <div class="space-y-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="settingsForm.alert_on_overdue" type="checkbox" class="rounded" />
            <span class="text-sm text-zinc-300">Alert when resources become overdue</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="settingsForm.alert_on_delete" type="checkbox" class="rounded" />
            <span class="text-sm text-zinc-300">Alert when resources are deleted</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="settingsForm.alert_on_review_overdue" type="checkbox" class="rounded" />
            <span class="text-sm text-zinc-300">Alert when reviews are overdue</span>
          </label>
        </div>

        <button
          :disabled="savingSettings"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm transition-colors disabled:opacity-50"
          @click="saveSettings"
        >
          {{ savingSettings ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </section>

    <!-- ── Reports ────────────────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-base font-semibold text-white mb-1">Reports</h2>
      <p class="text-zinc-500 text-sm mb-5">Download CSV snapshots for offline review or sharing with your team.</p>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button
          class="flex flex-col items-start gap-1 px-4 py-3 border border-tribal-border text-left rounded-lg hover:border-blue-500/50 transition-colors group"
          @click="openReport('/admin/reports/upcoming')"
        >
          <span class="text-zinc-300 group-hover:text-blue-400 text-sm font-medium transition-colors">📊 Upcoming Expiry</span>
          <span class="text-zinc-500 text-xs">Resources expiring within the next 30 days.</span>
        </button>
        <button
          class="flex flex-col items-start gap-1 px-4 py-3 border border-tribal-border text-left rounded-lg hover:border-blue-500/50 transition-colors group"
          @click="openReport('/admin/reports/recent-changes')"
        >
          <span class="text-zinc-300 group-hover:text-blue-400 text-sm font-medium transition-colors">📋 Recent Changes</span>
          <span class="text-zinc-500 text-xs">All audit log events from the last 30 days.</span>
        </button>
        <button
          class="flex flex-col items-start gap-1 px-4 py-3 border border-tribal-border text-left rounded-lg hover:border-blue-500/50 transition-colors group"
          @click="openReport('/admin/reports/reviews-due')"
        >
          <span class="text-zinc-300 group-hover:text-blue-400 text-sm font-medium transition-colors">📅 Reviews Due</span>
          <span class="text-zinc-500 text-xs">Resources overdue for their periodic review.</span>
        </button>
      </div>
    </section>

    <!-- ── Users ──────────────────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border overflow-hidden">
      <div class="px-6 py-4 border-b border-tribal-border">
        <h2 class="text-base font-semibold text-white">Users</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-tribal-card border-b border-tribal-border">
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Name / Email</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Role</th>
              <th class="text-right text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in adminStore.users.slice((usersPage - 1) * 25, usersPage * 25)"
              :key="user.id"
              class="border-b border-tribal-border/50 hover:bg-tribal-card/50 transition-colors"
            >
              <td class="px-4 py-3">
                <p class="text-white">{{ user.display_name || user.email }}</p>
                <p v-if="user.display_name" class="text-zinc-500 text-xs">{{ user.email }}</p>
                <span v-if="user.is_account_creator" class="text-xs text-blue-400">Account Creator</span>
              </td>
              <td class="px-4 py-3">
                <select
                  :value="getUserRole(user)"
                  :disabled="user.id === authStore.user?.id || user.is_account_creator"
                  class="bg-tribal-card border border-tribal-border rounded px-2 py-1 text-white text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  @change="handleRoleChange(user.id, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="admin">Admin</option>
                  <option value="member">Member</option>
                  <option value="readonly">Read-only</option>
                </select>
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  :disabled="user.id === authStore.user?.id || user.is_account_creator"
                  class="text-red-400 hover:text-red-300 text-sm transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  @click="handleDeleteUser(user.id)"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-3 border-t border-tribal-border/50">
        <Pagination
          :total="adminStore.users.length"
          :page="usersPage"
          :per-page="25"
          @update:page="usersPage = $event"
        />
      </div>
    </section>

    <!-- ── Admin API Keys ─────────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border overflow-hidden">
      <div class="px-6 py-4 border-b border-tribal-border">
        <h2 class="text-base font-semibold text-white">API Keys (All Users)</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-tribal-card border-b border-tribal-border">
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Name</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Owner</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Prefix</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Last Used</th>
              <th class="text-right text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Actions</th>
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
              <td class="px-4 py-3 text-white">{{ key.name }}</td>
              <td class="px-4 py-3 text-zinc-400">{{ key.user_email }}</td>
              <td class="px-4 py-3 font-mono text-zinc-400 text-xs">{{ key.key_prefix }}...</td>
              <td class="px-4 py-3 text-zinc-400">{{ formatDateTime(key.last_used_at) }}</td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="!key.revoked_at"
                  class="text-red-400 hover:text-red-300 text-sm transition-colors"
                  @click="handleRevokeAdminKey(key.id)"
                >
                  Revoke
                </button>
                <span v-else class="text-zinc-600 text-xs">Revoked</span>
              </td>
            </tr>
            <tr v-if="adminStore.apiKeys.length === 0">
              <td colspan="5" class="px-4 py-8 text-center text-zinc-500">No API keys found.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ── Audit Log ──────────────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border overflow-hidden">
      <div class="px-6 py-4 border-b border-tribal-border">
        <h2 class="text-base font-semibold text-white">Audit Log</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-tribal-card border-b border-tribal-border">
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Time</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">User</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Action</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Resource</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in adminStore.auditLog"
              :key="entry.id"
              class="border-b border-tribal-border/50 hover:bg-tribal-card/50 transition-colors"
            >
              <td class="px-4 py-3 text-zinc-400 whitespace-nowrap text-xs">{{ formatDateTime(entry.created_at) }}</td>
              <td class="px-4 py-3 text-zinc-300">{{ entry.user_email ?? '—' }}</td>
              <td class="px-4 py-3">
                <span class="text-zinc-300 font-mono text-xs">{{ entry.action }}</span>
              </td>
              <td class="px-4 py-3 text-zinc-400">{{ entry.resource_name ?? '—' }}</td>
            </tr>
            <tr v-if="adminStore.auditLog.length === 0">
              <td colspan="4" class="px-4 py-8 text-center text-zinc-500">No audit log entries.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-3 border-t border-tribal-border/50">
        <button
          class="text-sm text-zinc-400 hover:text-white transition-colors"
          @click="loadMoreAudit"
        >
          Load More
        </button>
      </div>
    </section>

    <!-- ── Deleted Resources ──────────────────────────────────────────────────── -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border overflow-hidden">
      <div class="px-6 py-4 border-b border-tribal-border">
        <h2 class="text-base font-semibold text-white">Deleted Resources</h2>
        <p class="text-zinc-500 text-sm mt-1">Restore returns a resource to the active list. Purge permanently removes it and cannot be undone.</p>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-tribal-card border-b border-tribal-border">
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Name</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Type</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">DRI</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Deleted At</th>
              <th class="text-right text-zinc-400 text-xs uppercase tracking-wider px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="resource in adminStore.deletedResources"
              :key="resource.id"
              class="border-b border-tribal-border/50 hover:bg-tribal-card/50 transition-colors"
            >
              <td class="px-4 py-3 text-white">{{ resource.name }}</td>
              <td class="px-4 py-3 text-zinc-400">{{ resource.type }}</td>
              <td class="px-4 py-3 text-zinc-400">{{ resource.dri }}</td>
              <td class="px-4 py-3 text-zinc-400 text-xs">{{ formatDateTime(resource.deleted_at) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex justify-end gap-2">
                  <button
                    class="text-emerald-400 hover:text-emerald-300 text-sm transition-colors"
                    @click="handleRestore(resource.id)"
                  >
                    Restore
                  </button>
                  <button
                    class="text-red-400 hover:text-red-300 text-sm transition-colors"
                    @click="handlePurge(resource.id, resource.name)"
                  >
                    Purge
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="adminStore.deletedResources.length === 0">
              <td colspan="5" class="px-4 py-8 text-center text-zinc-500">No deleted resources.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
