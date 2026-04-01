<script setup lang="ts">
defineProps<{
  title: string
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="emit('close')"
      >
        <!-- Overlay -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="emit('close')" />

        <!-- Panel -->
        <div
          class="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-tribal-panel rounded-xl border border-tribal-border border-t-2 border-t-blue-500 shadow-2xl"
        >
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-tribal-border">
            <h2 class="text-lg font-semibold text-white">{{ title }}</h2>
            <button
              class="text-zinc-400 hover:text-white transition-colors p-2 rounded min-w-[2rem] min-h-[2rem]"
              aria-label="Close"
              @click="emit('close')"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="px-6 py-5">
            <slot />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
