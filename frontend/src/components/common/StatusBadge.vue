<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, CircleCheck, Clock, Infinity as NoExpiry, TriangleAlert } from '@lucide/vue'
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

// Status is never colour-only: each urgency level also has its own icon.
const look = computed(() => {
  switch (u.value) {
    case 'overdue':
      return { icon: CircleAlert, cls: 'badge border-status-overdue/40 bg-status-overdue/10 text-status-overdue' }
    case 'critical':
      return { icon: TriangleAlert, cls: 'badge border-status-critical/40 bg-status-critical/10 text-status-critical' }
    case 'warning':
      return { icon: Clock, cls: 'badge border-status-warning/40 bg-status-warning/10 text-status-warning' }
    case 'upcoming':
      return { icon: Clock, cls: 'badge border-status-upcoming/40 bg-status-upcoming/10 text-status-upcoming' }
    case 'ok':
      return { icon: CircleCheck, cls: 'badge-ok' }
    case 'none':
    default:
      return { icon: NoExpiry, cls: 'badge-neutral' }
  }
})
</script>

<template>
  <span :class="look.cls">
    <component :is="look.icon" :size="12" aria-hidden="true" />
    {{ label }}
  </span>
</template>
