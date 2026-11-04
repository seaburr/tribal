<script setup lang="ts">
import type { Resource } from '../../types'
import ConfirmDialog from '../common/ConfirmDialog.vue'

defineProps<{
  resource: Resource | null
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  confirmed: []
}>()
</script>

<template>
  <ConfirmDialog
    :open="open"
    title="Delete resource"
    message="The resource will be soft-deleted. An admin can restore it from the Admin page."
    confirm-label="Delete resource"
    danger
    :require-text="resource?.name"
    @confirm="emit('confirmed')"
    @cancel="emit('close')"
  />
</template>
