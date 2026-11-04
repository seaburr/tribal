<script setup lang="ts">
import { ref, watch } from 'vue'
import { Ban, Check, Copy } from '@lucide/vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import IconButton from '../common/IconButton.vue'
import BaseModal from '../common/BaseModal.vue'
import { useToast } from '../../composables/useToast'
import { listApiKeys, createApiKey, revokeApiKey } from '../../api/keys'
import type { ApiKey, ApiKeyCreated } from '../../types'
import { useDateFormat } from '../../composables/useDateFormat'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const { show } = useToast()
const { formatDateTime } = useDateFormat()

const keys = ref<ApiKey[]>([])
const loading = ref(false)
const newKeyName = ref('')
const createdKey = ref<ApiKeyCreated | null>(null)
const creating = ref(false)
const copied = ref(false)

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) {
      createdKey.value = null
      newKeyName.value = ''
      return
    }
    await loadKeys()
  },
)

async function loadKeys() {
  loading.value = true
  try {
    keys.value = await listApiKeys()
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to load keys', 'error')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newKeyName.value) return
  creating.value = true
  try {
    createdKey.value = await createApiKey(newKeyName.value)
    newKeyName.value = ''
    await loadKeys()
    show('API key created', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to create key', 'error')
  } finally {
    creating.value = false
  }
}

const revoking = ref<ApiKey | null>(null)
const revokeBusy = ref(false)

async function confirmRevoke() {
  if (!revoking.value) return
  revokeBusy.value = true
  try {
    await revokeApiKey(revoking.value.id)
    await loadKeys()
    show('API key revoked', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to revoke key', 'error')
  } finally {
    revokeBusy.value = false
    revoking.value = null
  }
}

async function copyKey() {
  if (!createdKey.value) return
  await navigator.clipboard.writeText(createdKey.value.full_key)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

const activeKeys = () => keys.value.filter(k => !k.revoked_at)
</script>

<template>
  <BaseModal title="API keys" :open="open" @close="emit('close')">
    <div class="space-y-5">
      <!-- Newly created key -->
      <div v-if="createdKey" class="alert-success space-y-2" role="status">
        <p class="font-medium">Key created. Copy it now: it will not be shown again.</p>
        <div class="flex items-center gap-2">
          <code class="mono min-w-0 flex-1 truncate rounded-md border border-tribal-border bg-tribal-bg px-2.5 py-2 text-emerald-200">{{ createdKey.full_key }}</code>
          <button type="button" class="btn-secondary shrink-0" @click="copyKey">
            <Check v-if="copied" :size="16" aria-hidden="true" />
            <Copy v-else :size="16" aria-hidden="true" />
            {{ copied ? 'Copied' : 'Copy' }}
          </button>
        </div>
      </div>

      <!-- Create new key -->
      <form @submit.prevent="handleCreate">
        <label for="new-api-key-name" class="label">Generate new key</label>
        <div class="flex gap-2">
          <input
            id="new-api-key-name"
            v-model="newKeyName"
            type="text"
            placeholder="Key name (e.g., CI/CD Pipeline)"
            class="input flex-1"
          />
          <button type="submit" class="btn-primary shrink-0" :disabled="creating || !newKeyName">
            {{ creating ? 'Creating…' : 'Generate' }}
          </button>
        </div>
      </form>

      <!-- Active keys -->
      <div>
        <h3 class="section-title mb-2">Active keys</h3>
        <div v-if="loading" class="py-4 text-center text-sm text-zinc-400">Loading…</div>
        <div v-else-if="activeKeys().length === 0" class="py-4 text-center text-sm text-zinc-400">
          No active API keys.
        </div>
        <div v-else class="overflow-x-auto rounded-md border border-tribal-border">
          <table class="tbl">
            <thead>
              <tr class="bg-tribal-card">
                <th>Name</th>
                <th>Prefix</th>
                <th>Last used</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in activeKeys()" :key="key.id" class="hover:bg-tribal-card/30">
                <td class="text-white">{{ key.name }}</td>
                <td class="mono text-zinc-400">{{ key.key_prefix }}</td>
                <td class="text-xs text-zinc-400">{{ formatDateTime(key.last_used_at) }}</td>
                <td class="text-right">
                  <IconButton :icon="Ban" label="Revoke API key" danger sm @click="revoking = key" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="revoking !== null"
      title="Revoke API key"
      :message="`Revoke '${revoking?.name ?? ''}'? This cannot be undone, and anything using it stops working immediately.`"
      confirm-label="Revoke key"
      busy-label="Revoking…"
      danger
      :busy="revokeBusy"
      @confirm="confirmRevoke"
      @cancel="revoking = null"
    />
  </BaseModal>
</template>
