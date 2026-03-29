<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts } = useToast()
</script>

<template>
  <div class="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        :class="[
          'pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 shadow-lg max-w-sm text-sm',
          toast.type === 'success'
            ? 'bg-emerald-900/90 border-emerald-500/50 text-emerald-100'
            : 'bg-red-900/90 border-red-500/50 text-red-100',
        ]"
      >
        <span v-if="toast.type === 'success'" class="text-emerald-400 mt-0.5">✓</span>
        <span v-else class="text-red-400 mt-0.5">✕</span>
        <span>{{ toast.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(1rem);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(1rem);
}
</style>
