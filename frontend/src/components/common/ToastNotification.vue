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
            ? 'bg-accent-green-dark/90 border-accent-green/50 text-zinc-100'
            : 'bg-danger-dark/90 border-danger/50 text-zinc-100',
        ]"
      >
        <span v-if="toast.type === 'success'" class="text-accent-green mt-0.5">✓</span>
        <span v-else class="text-danger mt-0.5">✕</span>
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
