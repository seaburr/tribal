<script setup lang="ts">
import type { Resource } from '../../types'
import BaseModal from '../common/BaseModal.vue'
import StatusBadge from '../common/StatusBadge.vue'
import { formatDate } from '../../utils/date'

defineProps<{
  date: string | null
  resources: Resource[]
}>()

const emit = defineEmits<{
  close: []
  'view-resource': [resource: Resource]
}>()
</script>

<template>
  <BaseModal
    :title="date ? `Expiring on ${formatDate(date)}` : 'Expiring resources'"
    :open="!!date"
    @close="emit('close')"
  >
    <div v-if="resources.length === 0" class="py-4 text-center text-sm text-zinc-400">
      No resources expire on this date.
    </div>
    <ul v-else class="space-y-2">
      <li v-for="resource in resources" :key="resource.id">
        <button
          type="button"
          class="flex w-full flex-wrap items-center justify-between gap-2 rounded-md border border-tribal-border bg-tribal-card p-3 text-left transition-colors hover:border-zinc-500"
          @click="emit('view-resource', resource)"
        >
          <span class="min-w-0">
            <span class="block text-sm font-medium text-white">{{ resource.name }}</span>
            <span class="meta mt-0.5 block">{{ resource.dri }}</span>
          </span>
          <span class="flex items-center gap-2">
            <span class="meta">{{ resource.type }}</span>
            <StatusBadge :resource="resource" />
          </span>
        </button>
      </li>
    </ul>
  </BaseModal>
</template>
