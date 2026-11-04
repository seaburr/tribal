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
  <nav v-if="total > perPage" aria-label="Pagination" class="flex items-center justify-between gap-3 px-3 py-2">
    <span class="meta">{{ from }}–{{ to }} of {{ total }}</span>
    <div class="flex gap-2">
      <button type="button" class="btn-secondary btn-sm" :disabled="page <= 1" @click="emit('update:page', page - 1)">Previous</button>
      <button type="button" class="btn-secondary btn-sm" :disabled="page >= totalPages" @click="emit('update:page', page + 1)">Next</button>
    </div>
  </nav>
</template>
