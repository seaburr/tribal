<script setup lang="ts">
import { ref, useId } from 'vue'
import { X } from '@lucide/vue'
import IconButton from './IconButton.vue'
import { useModal } from '../../composables/useModal'

const props = defineProps<{
  title: string
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const dialog = ref<HTMLDialogElement | null>(null)
const titleId = useId()
const modal = useModal(dialog, () => props.open, () => emit('close'))
</script>

<template>
  <dialog
    ref="dialog"
    :aria-labelledby="titleId"
    class="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-lg border border-tribal-border bg-tribal-panel p-0 text-white shadow-xl backdrop:bg-black/70"
    @cancel="modal.onNativeCancel"
    @click="modal.onBackdrop"
  >
    <template v-if="open">
      <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-tribal-border bg-tribal-panel px-4 py-3">
        <h2 :id="titleId" class="section-title min-w-0 wrap-break-word">{{ title }}</h2>
        <IconButton :icon="X" label="Close" sm @click="emit('close')" />
      </div>
      <div class="p-4">
        <slot />
      </div>
    </template>
  </dialog>
</template>
