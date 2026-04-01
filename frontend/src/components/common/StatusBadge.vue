<script setup lang="ts">
import { computed } from 'vue'
import type { Resource } from '../../types'
import { urgency, daysUntil, formatDate } from '../../utils/date'

const props = defineProps<{ resource: Resource }>()

const u = computed(() => urgency(props.resource.expiration_date, props.resource.does_not_expire))

const label = computed(() => {
  switch (u.value) {
    case 'overdue':
      return 'Overdue'
    case 'critical':
    case 'warning':
    case 'upcoming': {
      const days = daysUntil(props.resource.expiration_date)
      if (days === 0) return 'Expires today'
      if (days === 1) return 'Expires in 1 day'
      return `Expires in ${days} days`
    }
    case 'ok':
      return formatDate(props.resource.expiration_date)
    case 'none':
      return 'No expiry'
  }
})

const cls = computed(() => {
  switch (u.value) {
    case 'overdue':
      return 'bg-status-overdue/15 text-status-overdue border border-status-overdue/25'
    case 'critical':
      return 'bg-status-critical/15 text-status-critical border border-status-critical/25'
    case 'warning':
      return 'bg-status-warning/15 text-status-warning border border-status-warning/25'
    case 'upcoming':
      return 'bg-status-upcoming/15 text-status-upcoming border border-status-upcoming/25'
    case 'ok':
      return 'bg-accent-green/20 text-accent-green border border-accent-green/30'
    case 'none':
      return 'bg-zinc-700/50 text-zinc-400'
  }
})
</script>

<template>
  <span :class="['inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', cls]">
    {{ label }}
  </span>
</template>
