<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { Resource } from '../../types'
import BaseModal from '../common/BaseModal.vue'

const props = defineProps<{
  resource: Resource | null
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  confirmed: []
}>()

const confirmInput = ref('')

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) confirmInput.value = ''
  },
)

const canDelete = computed(
  () => confirmInput.value === props.resource?.name,
)
</script>

<template>
  <BaseModal title="Delete Resource" :open="open" @close="emit('close')">
    <div v-if="resource" class="space-y-4">
      <div class="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
        <p class="text-red-400 text-sm font-medium">⚠️ This action cannot be easily undone</p>
        <p class="text-zinc-400 text-sm mt-1">
          The resource will be soft-deleted and can be restored by an admin from the Admin panel.
        </p>
      </div>

      <p class="text-zinc-300 text-sm">
        Type <span class="font-mono text-white bg-tribal-card px-1.5 py-0.5 rounded border border-tribal-border">{{ resource.name }}</span> to confirm deletion:
      </p>

      <input
        v-model="confirmInput"
        type="text"
        :placeholder="resource.name"
        class="w-full bg-tribal-card border border-tribal-border rounded-lg px-3 py-2 text-white placeholder-zinc-600 focus:outline-none focus:border-red-500 transition-colors"
      />

      <div class="flex justify-end gap-3 pt-2 border-t border-tribal-border">
        <button
          type="button"
          class="px-4 py-2 border border-tribal-border text-zinc-400 hover:text-white rounded-lg text-sm transition-colors"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          :disabled="!canDelete"
          class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-lg text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          @click="emit('confirmed')"
        >
          Delete Resource
        </button>
      </div>
    </div>
  </BaseModal>
</template>
