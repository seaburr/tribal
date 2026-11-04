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
  <div class="card card-pad h-full">
    <h2 class="section-title mb-3">Upcoming events</h2>

    <div v-if="upcoming.length === 0" class="py-8 text-center text-sm text-zinc-400">
      Zarro items due.
    </div>

    <ul v-else class="max-h-[600px] space-y-2 overflow-y-auto pr-1">
      <li v-for="resource in upcoming" :key="resource.id">
        <button
          type="button"
          class="w-full rounded-md border border-tribal-border bg-tribal-card p-3 text-left transition-colors hover:border-zinc-500"
          @click="openResourceDetail(resource)"
        >
          <span class="flex items-start justify-between gap-2">
            <span class="min-w-0">
              <span class="block truncate text-sm font-medium text-white">{{ resource.name }}</span>
              <span class="meta mt-0.5 block truncate">{{ resource.dri }}</span>
            </span>
            <span class="meta shrink-0">{{ resource.type }}</span>
          </span>
          <span class="mt-2 flex flex-wrap items-center gap-1.5">
            <StatusBadge :resource="resource" />
            <span v-if="isReviewDue(resource)" class="badge-review">Review due</span>
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>
