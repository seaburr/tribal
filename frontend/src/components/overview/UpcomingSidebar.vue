<script setup lang="ts">
import { computed, inject } from 'vue'
import { useResourcesStore } from '../../stores/resources'
import StatusBadge from '../common/StatusBadge.vue'
import { daysUntil } from '../../utils/date'
import type { Resource } from '../../types'

const resourcesStore = useResourcesStore()
const openResourceDetail = inject<(resource: Resource) => void>('openResourceDetail')!

function isReviewDue(r: Resource): boolean {
  const cadence = resourcesStore.reviewCadenceMonths
  if (!cadence) return false
  const base = new Date(r.last_reviewed_at ?? r.created_at)
  const dueDate = new Date(base)
  dueDate.setMonth(dueDate.getMonth() + cadence)
  return dueDate <= new Date()
}

const upcoming = computed(() => {
  return resourcesStore.resources
    .filter((r) => {
      const days = r.does_not_expire ? null : daysUntil(r.expiration_date)
      const expiryDue = days !== null && days <= 30
      return expiryDue || isReviewDue(r)
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
      Upcoming Events
    </h3>

    <div v-if="upcoming.length === 0" class="text-zinc-500 text-sm text-center py-8">
      Zarro items due.
    </div>

    <ul v-else class="space-y-2 overflow-y-auto max-h-[600px] pr-1">
      <li
        v-for="resource in upcoming"
        :key="resource.id"
        class="p-3 bg-tribal-card rounded-lg border border-tribal-border hover:border-accent-blue/30 cursor-pointer transition-colors"
        @click="openResourceDetail(resource)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-white text-sm font-medium truncate">{{ resource.name }}</p>
            <p class="text-zinc-500 text-xs mt-0.5 truncate">{{ resource.dri }}</p>
          </div>
          <span class="shrink-0 text-xs text-zinc-500 bg-tribal-muted/30 px-2 py-0.5 rounded">{{ resource.type }}</span>
        </div>
        <div class="mt-2 flex items-center gap-1.5 flex-wrap">
          <StatusBadge :resource="resource" />
          <span
            v-if="isReviewDue(resource)"
            class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-accent-purple/20 text-accent-purple"
          >Review Due</span>
        </div>
      </li>
    </ul>
  </div>
</template>
