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
    :title="date ? `Expiring on ${formatDate(date)}` : 'Expiring Resources'"
    :open="!!date"
    @close="emit('close')"
  >
    <div v-if="resources.length === 0" class="text-zinc-400 text-sm py-4 text-center">
      No resources expire on this date.
    </div>
    <ul v-else class="space-y-2">
      <li
        v-for="resource in resources"
        :key="resource.id"
        class="flex items-center justify-between p-3 bg-tribal-card rounded-lg border border-tribal-border hover:border-blue-500/30 cursor-pointer transition-colors"
        @click="emit('view-resource', resource)"
      >
        <div>
          <p class="text-white font-medium text-sm">{{ resource.name }}</p>
          <p class="text-zinc-500 text-xs mt-0.5">{{ resource.dri }}</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-zinc-500 bg-tribal-muted/30 px-2 py-0.5 rounded">{{ resource.type }}</span>
          <StatusBadge :resource="resource" />
        </div>
      </li>
    </ul>
  </BaseModal>
</template>
