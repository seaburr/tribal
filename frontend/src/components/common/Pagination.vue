<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  total: number
  page: number
  perPage?: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const perPage = computed(() => props.perPage ?? 25)
const totalPages = computed(() => Math.ceil(props.total / perPage.value))
const from = computed(() => (props.page - 1) * perPage.value + 1)
const to = computed(() => Math.min(props.page * perPage.value, props.total))
</script>

<template>
  <div v-if="total > perPage" class="flex items-center justify-between mt-4 text-sm text-zinc-400">
    <span>{{ from }}–{{ to }} of {{ total }}</span>
    <div class="flex gap-2">
      <button
        :disabled="page <= 1"
        :class="[
          'px-3 py-1.5 rounded-lg border transition-colors',
          page <= 1
            ? 'border-tribal-border text-zinc-600 cursor-not-allowed'
            : 'border-tribal-border hover:border-accent-blue/50 hover:text-accent-blue',
        ]"
        @click="emit('update:page', page - 1)"
      >
        ← Prev
      </button>
      <button
        :disabled="page >= totalPages"
        :class="[
          'px-3 py-1.5 rounded-lg border transition-colors',
          page >= totalPages
            ? 'border-tribal-border text-zinc-600 cursor-not-allowed'
            : 'border-tribal-border hover:border-accent-blue/50 hover:text-accent-blue',
        ]"
        @click="emit('update:page', page + 1)"
      >
        Next →
      </button>
    </div>
  </div>
</template>
