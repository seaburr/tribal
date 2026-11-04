<script setup lang="ts">
import { computed } from 'vue'
import { X } from '@lucide/vue'
import IconButton from './IconButton.vue'
import { modalStack } from '../../composables/useModal'
import { useToast } from '../../composables/useToast'

const { toasts, dismiss } = useToast()

const tone = {
  success: 'border-emerald-500/50 text-emerald-200',
  error: 'border-danger/60 text-red-200',
} as const
const glyph = { success: '✓', error: '!' } as const

// A modal <dialog> makes everything outside it inert, so toasts move into whichever dialog is on top.
const target = computed(() => modalStack.value[modalStack.value.length - 1] ?? 'body')
</script>

<template>
  <Teleport :to="target">
    <div class="pointer-events-none fixed inset-x-0 bottom-0 z-60 flex flex-col items-center gap-2 px-4 pb-4 sm:items-end sm:px-6">
      <div
        v-for="t in toasts"
        :key="t.id"
        :role="t.type === 'error' ? 'alert' : 'status'"
        :class="['pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-lg border bg-tribal-card px-3 py-2.5 text-sm shadow-xl', tone[t.type]]"
      >
        <span aria-hidden="true" class="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold">{{ glyph[t.type] }}</span>
        <p class="min-w-0 flex-1 wrap-break-word">{{ t.message }}</p>
        <IconButton :icon="X" label="Dismiss notification" sm @click="dismiss(t.id)" />
      </div>
    </div>
  </Teleport>
</template>
