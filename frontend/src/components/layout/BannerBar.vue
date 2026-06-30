<script setup lang="ts">
import { computed } from 'vue'
import type { Banner, BannerLevel } from '../../types'

const props = defineProps<{ banner: Banner | null }>()

// Full class strings per level so Tailwind keeps them at build time.
const levelClasses: Record<BannerLevel, string> = {
  info: 'bg-accent-blue/10 border-accent-blue/40 text-accent-blue-light',
  warning: 'bg-status-warning/10 border-status-warning/40 text-status-warning',
  critical: 'bg-danger/10 border-danger/40 text-danger-light',
}

const visible = computed(() => Boolean(props.banner?.enabled && props.banner?.message))
const classes = computed(() => levelClasses[props.banner?.level ?? 'info'])
</script>

<template>
  <div
    v-if="visible"
    role="status"
    :class="['w-full border-b px-4 sm:px-6 py-2.5 text-sm text-center font-medium', classes]"
  >
    {{ banner?.message }}
  </div>
</template>
