<script setup lang="ts">
import { ref, watch } from 'vue'
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

async function handleRevoke(id: number) {
  if (!confirm('Revoke this API key? This cannot be undone.')) return
  try {
    await revokeApiKey(id)
    await loadKeys()
    show('API key revoked', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to revoke key', 'error')
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
  <BaseModal title="API Keys" :open="open" @close="emit('close')">
    <div class="space-y-5">
      <!-- Newly created key banner -->
      <div
        v-if="createdKey"
        class="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-4 space-y-2"
      >
        <p class="text-emerald-400 font-medium text-sm">
          ✓ Key created — copy it now. It will not be shown again.
        </p>
        <div class="flex items-center gap-2">
          <code class="flex-1 bg-[#0d0d14] rounded px-3 py-2 text-sm text-emerald-300 font-mono truncate border border-emerald-800/50">
            {{ createdKey.full_key }}
          </code>
          <button
            class="px-3 py-2 border border-emerald-500/50 text-emerald-400 hover:border-emerald-500 rounded-lg text-sm transition-colors whitespace-nowrap"
            @click="copyKey"
          >
            {{ copied ? 'Copied!' : 'Copy' }}
          </button>
        </div>
      </div>

      <!-- Create new key -->
      <div>
        <label class="block text-sm font-medium text-zinc-300 mb-2">Generate New Key</label>
        <div class="flex gap-2">
          <input
            v-model="newKeyName"
            type="text"
            placeholder="Key name (e.g., CI/CD Pipeline)"
            class="flex-1 bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            @keyup.enter="handleCreate"
          />
          <button
            :disabled="creating || !newKeyName"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg text-sm transition-colors disabled:opacity-50"
            @click="handleCreate"
          >
            {{ creating ? 'Creating...' : 'Generate' }}
          </button>
        </div>
      </div>

      <!-- Active keys table -->
      <div>
        <h3 class="text-sm font-medium text-zinc-400 mb-2">Active Keys</h3>
        <div v-if="loading" class="text-center py-4 text-zinc-500 text-sm">Loading...</div>
        <div v-else-if="activeKeys().length === 0" class="text-center py-4 text-zinc-500 text-sm">
          No active API keys.
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="bg-tribal-card border-b border-tribal-border">
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-3 py-2">Name</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-3 py-2">Prefix</th>
              <th class="text-left text-zinc-400 text-xs uppercase tracking-wider px-3 py-2">Last Used</th>
              <th class="text-right text-zinc-400 text-xs uppercase tracking-wider px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="key in activeKeys()"
              :key="key.id"
              class="border-b border-tribal-border/50 hover:bg-tribal-card/30 transition-colors"
            >
              <td class="px-3 py-2.5 text-white">{{ key.name }}</td>
              <td class="px-3 py-2.5 font-mono text-zinc-400 text-xs">{{ key.key_prefix }}...</td>
              <td class="px-3 py-2.5 text-zinc-400 text-xs">{{ formatDateTime(key.last_used_at) }}</td>
              <td class="px-3 py-2.5 text-right">
                <button
                  class="text-red-400 hover:text-red-300 text-xs transition-colors"
                  @click="handleRevoke(key.id)"
                >
                  Revoke
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </BaseModal>
</template>
