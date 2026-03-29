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
      return 'bg-red-500/20 text-red-400 border border-red-500/30'
    case 'critical':
      return 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
    case 'warning':
      return 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
    case 'upcoming':
      return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
    case 'ok':
      return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
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
