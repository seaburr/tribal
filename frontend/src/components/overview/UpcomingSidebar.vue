<script setup lang="ts">
import { computed, inject } from 'vue'
import { useResourcesStore } from '../../stores/resources'
import StatusBadge from '../common/StatusBadge.vue'
import { daysUntil } from '../../utils/date'
import type { Resource } from '../../types'

const resourcesStore = useResourcesStore()
const openResourceDetail = inject<(resource: Resource) => void>('openResourceDetail')!

const upcoming = computed(() => {
  return resourcesStore.resources
    .filter((r) => {
      if (r.does_not_expire) return false
      const days = daysUntil(r.expiration_date)
      if (days === null) return false
      return days <= 90
    })
    .sort((a, b) => {
      const da = daysUntil(a.expiration_date) ?? 9999
      const db = daysUntil(b.expiration_date) ?? 9999
      return da - db
    })
})
</script>

<template>
  <div class="bg-tribal-panel rounded-xl border border-tribal-border p-4 h-full">
    <h3 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
      Upcoming Expirations
    </h3>

    <div v-if="upcoming.length === 0" class="text-zinc-500 text-sm text-center py-8">
      No resources expiring within 90 days.
    </div>

    <ul v-else class="space-y-2 overflow-y-auto max-h-[600px] pr-1">
      <li
        v-for="resource in upcoming"
        :key="resource.id"
        class="p-3 bg-tribal-card rounded-lg border border-tribal-border hover:border-amber-500/30 cursor-pointer transition-colors"
        @click="openResourceDetail(resource)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-white text-sm font-medium truncate">{{ resource.name }}</p>
            <p class="text-zinc-500 text-xs mt-0.5 truncate">{{ resource.dri }}</p>
          </div>
          <span class="shrink-0 text-xs text-zinc-500 bg-tribal-muted/30 px-2 py-0.5 rounded">{{ resource.type }}</span>
        </div>
        <div class="mt-2">
          <StatusBadge :resource="resource" />
        </div>
      </li>
    </ul>
  </div>
</template>
