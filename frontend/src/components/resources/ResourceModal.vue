<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { Resource } from '../../types'
import BaseModal from '../common/BaseModal.vue'
import { useToast } from '../../composables/useToast'
import { getResource, createResource, updateResource, certLookup, identifyKey, testWebhook, listTeams } from '../../api/resources'
import { onMounted } from 'vue'
import type { Team } from '../../types'

const props = defineProps<{
  resourceId: number | null
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const { show } = useToast()

const isNew = computed(() => props.resourceId === null)
const title = computed(() => (isNew.value ? 'Add Resource' : 'Edit Resource'))

// Form state
const form = ref({
  name: '',
  dri: '',
  type: 'API Key' as string,
  expiration_date: '',
  does_not_expire: false,
  purpose: '',
  generation_instructions: '',
  secret_manager_link: '',
  slack_webhook: '',
  team_id: null as number | null,
  certificate_url: '',
  auto_refresh_expiry: false,
  provider: '',
})

const loading = ref(false)
const certEndpoint = ref('')
const certLoading = ref(false)
const apiKeyInput = ref('')
const detectLoading = ref(false)
const teams = ref<Team[]>([])

onMounted(async () => {
  try {
    teams.value = await listTeams()
  } catch {
    // ignore
  }
})

// Reset/load form when modal opens
watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) return
    certEndpoint.value = ''
    apiKeyInput.value = ''

    if (isNew.value) {
      Object.assign(form.value, {
        name: '',
        dri: '',
        type: 'API Key',
        expiration_date: '',
        does_not_expire: false,
        purpose: '',
        generation_instructions: '',
        secret_manager_link: '',
        slack_webhook: '',
        team_id: null,
        certificate_url: '',
        auto_refresh_expiry: false,
        provider: '',
      })
    } else if (props.resourceId !== null) {
      try {
        loading.value = true
        const r = await getResource(props.resourceId)
        Object.assign(form.value, {
          name: r.name,
          dri: r.dri,
          type: r.type,
          expiration_date: r.expiration_date ?? '',
          does_not_expire: r.does_not_expire,
          purpose: r.purpose,
          generation_instructions: r.generation_instructions,
          secret_manager_link: r.secret_manager_link ?? '',
          slack_webhook: r.slack_webhook,
          team_id: r.team_id,
          certificate_url: r.certificate_url ?? '',
          auto_refresh_expiry: r.auto_refresh_expiry,
          provider: r.provider ?? '',
        })
        certEndpoint.value = r.certificate_url ?? ''
      } catch (e: unknown) {
        show(e instanceof Error ? e.message : 'Failed to load resource', 'error')
      } finally {
        loading.value = false
      }
    }
  },
  { immediate: true },
)

async function handleCertLookup() {
  if (!certEndpoint.value) return
  certLoading.value = true
  try {
    const result = await certLookup(certEndpoint.value)
    form.value.expiration_date = result.expiration_date
    form.value.certificate_url = certEndpoint.value
    show('Certificate expiry retrieved', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to look up certificate', 'error')
  } finally {
    certLoading.value = false
  }
}

async function handleDetect() {
  if (!apiKeyInput.value) return
  detectLoading.value = true
  try {
    const result = await identifyKey(apiKeyInput.value, true)
    if (result.matched) {
      form.value.provider = result.provider ?? ''
      if (result.rotation_steps.length > 0) {
        form.value.generation_instructions = result.rotation_steps.map((s) => `• ${s}`).join('\n')
      }
      if (result.expires_at) {
        form.value.expiration_date = result.expires_at.slice(0, 10)
      }
      const expiryNote = result.expires_at ? 'expiry auto-filled.' : 'expiry unavailable — enter manually.'
      show(`Detected: ${result.provider ?? 'unknown provider'} — ${expiryNote}`, 'success')
    } else {
      show('Provider not recognized', 'error')
    }
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Detection failed', 'error')
  } finally {
    detectLoading.value = false
  }
}

async function handleTestWebhook() {
  if (!form.value.slack_webhook) return
  try {
    await testWebhook(form.value.slack_webhook)
    show('Test message sent', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Webhook test failed', 'error')
  }
}

async function handleSave() {
  if (!form.value.name || !form.value.dri) {
    show('Name and DRI are required', 'error')
    return
  }

  loading.value = true
  try {
    const data: Partial<Resource> = {
      name: form.value.name,
      dri: form.value.dri,
      type: form.value.type,
      expiration_date: form.value.does_not_expire ? null : (form.value.expiration_date || null),
      does_not_expire: form.value.does_not_expire,
      purpose: form.value.purpose,
      generation_instructions: form.value.generation_instructions,
      secret_manager_link: form.value.secret_manager_link || null,
      slack_webhook: form.value.slack_webhook,
      team_id: form.value.team_id,
      certificate_url: form.value.type === 'Certificate' ? (form.value.certificate_url || null) : null,
      auto_refresh_expiry: form.value.type === 'Certificate' ? form.value.auto_refresh_expiry : false,
      provider: form.value.provider || null,
    }

    if (isNew.value) {
      await createResource(data)
      show('Resource created', 'success')
    } else {
      await updateResource(props.resourceId!, data)
      show('Resource updated', 'success')
    }
    emit('saved')
    emit('close')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Save failed', 'error')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BaseModal :title="title" :open="open" @close="emit('close')">
    <div v-if="loading && !isNew" class="flex items-center justify-center py-12">
      <span class="text-zinc-400">Loading...</span>
    </div>

    <form v-else class="space-y-4" @submit.prevent="handleSave">
      <!-- Name -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Name <span class="text-red-400">*</span></label>
        <input
          v-model="form.name"
          type="text"
          placeholder="e.g., GitHub Actions Token"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
        />
      </div>

      <!-- DRI -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">DRI (Directly Responsible Individual) <span class="text-red-400">*</span></label>
        <input
          v-model="form.dri"
          type="text"
          placeholder="e.g., platform-team"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
        />
      </div>

      <!-- Type -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Type</label>
        <select
          v-model="form.type"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-amber-500 transition-colors"
        >
          <option value="Certificate">Certificate</option>
          <option value="API Key">API Key</option>
          <option value="SSH Key">SSH Key</option>
          <option value="Other">Other</option>
        </select>
      </div>

      <!-- Certificate-specific: endpoint lookup -->
      <div v-if="form.type === 'Certificate'" class="space-y-3">
        <div>
          <label class="block text-sm font-medium text-zinc-300 mb-1">TLS Endpoint</label>
          <div class="flex gap-2">
            <input
              v-model="certEndpoint"
              type="text"
              placeholder="e.g., example.com or https://example.com"
              class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
            />
            <button
              type="button"
              :disabled="certLoading || !certEndpoint"
              class="px-4 py-2 border border-amber-500/50 text-amber-400 hover:border-amber-500 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              @click="handleCertLookup"
            >
              {{ certLoading ? 'Loading...' : 'Get Expiry' }}
            </button>
          </div>
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
          <input v-model="form.auto_refresh_expiry" type="checkbox" class="rounded border-tribal-border" />
          <span class="text-sm text-zinc-300">Auto-refresh expiry date daily</span>
        </label>
      </div>

      <!-- API Key-specific: detect provider -->
      <div v-if="form.type === 'API Key'" class="space-y-2">
        <label class="block text-sm font-medium text-zinc-300 mb-1">Detect Provider (optional)</label>
        <div class="flex gap-2">
          <input
            v-model="apiKeyInput"
            type="password"
            placeholder="Paste API key to auto-detect provider"
            class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <button
            type="button"
            :disabled="detectLoading || !apiKeyInput"
            class="px-4 py-2 border border-amber-500/50 text-amber-400 hover:border-amber-500 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleDetect"
          >
            {{ detectLoading ? 'Detecting...' : 'Detect' }}
          </button>
        </div>
        <p class="text-xs text-zinc-500">The key is used only for detection and is never stored.</p>
      </div>

      <!-- Provider -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Provider</label>
        <input
          v-model="form.provider"
          type="text"
          placeholder="e.g., GitHub, AWS, Stripe"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
        />
      </div>

      <!-- Does not expire -->
      <label class="flex items-center gap-2 cursor-pointer">
        <input v-model="form.does_not_expire" type="checkbox" class="rounded border-tribal-border" />
        <span class="text-sm text-zinc-300">This resource does not expire</span>
      </label>

      <!-- Expiration date -->
      <div v-if="!form.does_not_expire">
        <label class="block text-sm font-medium text-zinc-300 mb-1">Expiration Date</label>
        <input
          v-model="form.expiration_date"
          type="date"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-amber-500 transition-colors [color-scheme:dark]"
        />
      </div>

      <!-- Team -->
      <div v-if="teams.length > 0">
        <label class="block text-sm font-medium text-zinc-300 mb-1">Team</label>
        <select
          v-model="form.team_id"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-amber-500 transition-colors"
        >
          <option :value="null">No team</option>
          <option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option>
        </select>
      </div>

      <!-- Purpose -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Purpose</label>
        <textarea
          v-model="form.purpose"
          rows="2"
          placeholder="What is this credential used for?"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors resize-none"
        />
      </div>

      <!-- Generation / Rotation Instructions -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Generation / Rotation Instructions</label>
        <textarea
          v-model="form.generation_instructions"
          rows="3"
          placeholder="Steps to generate or rotate this credential"
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors resize-none"
        />
      </div>

      <!-- Secret Manager Link -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Secret Manager Link</label>
        <input
          v-model="form.secret_manager_link"
          type="url"
          placeholder="https://..."
          class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
        />
      </div>

      <!-- Slack Webhook -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-1">Slack Webhook URL</label>
        <div class="flex gap-2">
          <input
            v-model="form.slack_webhook"
            type="url"
            placeholder="https://hooks.slack.com/..."
            class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <button
            type="button"
            :disabled="!form.slack_webhook"
            class="px-4 py-2 border border-tribal-border text-zinc-400 hover:border-amber-500/50 hover:text-amber-400 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleTestWebhook"
          >
            Send Test
          </button>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex justify-end gap-3 pt-2 border-t border-tribal-border">
        <button
          type="button"
          class="px-4 py-2 border border-tribal-border text-zinc-400 hover:text-white rounded-lg text-sm transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          type="submit"
          :disabled="loading"
          class="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-black font-semibold rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          {{ loading ? 'Saving...' : (isNew ? 'Create Resource' : 'Save Changes') }}
        </button>
      </div>
    </form>
  </BaseModal>
</template>
