<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Resource } from '../../types'
import StatusBadge from '../common/StatusBadge.vue'
import Pagination from '../common/Pagination.vue'
import { formatDate, urgency } from '../../utils/date'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{
  resources: Resource[]
  reviewCadenceMonths: number | null
}>()

const emit = defineEmits<{
  view: [resource: Resource]
  edit: [resource: Resource]
  delete: [resource: Resource]
}>()

const authStore = useAuthStore()

type SortKey = 'name' | 'type' | 'dri' | 'expiration_date' | 'status'
const sortKey = ref<SortKey>('expiration_date')
const sortDir = ref<'asc' | 'desc'>('asc')
const page = ref(1)
const perPage = 25

function setSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
  page.value = 1
}

function sortIndicator(key: SortKey) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

function urgencyScore(r: Resource): number {
  const u = urgency(r.expiration_date, r.does_not_expire)
  const scores: Record<string, number> = {
    overdue: 0,
    critical: 1,
    warning: 2,
    upcoming: 3,
    ok: 4,
    none: 5,
  }
  return scores[u] ?? 5
}

const sorted = computed(() => {
  const arr = [...props.resources]
  arr.sort((a, b) => {
    let va: string | number = ''
    let vb: string | number = ''

    switch (sortKey.value) {
      case 'name':
        va = a.name.toLowerCase()
        vb = b.name.toLowerCase()
        break
      case 'type':
        va = a.type.toLowerCase()
        vb = b.type.toLowerCase()
        break
      case 'dri':
        va = a.dri.toLowerCase()
        vb = b.dri.toLowerCase()
        break
      case 'expiration_date':
        va = a.does_not_expire ? '9999-99-99' : (a.expiration_date ?? '9999-99-99')
        vb = b.does_not_expire ? '9999-99-99' : (b.expiration_date ?? '9999-99-99')
        break
      case 'status':
        va = urgencyScore(a)
        vb = urgencyScore(b)
        break
    }

    if (va < vb) return sortDir.value === 'asc' ? -1 : 1
    if (va > vb) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return arr
})

const paginated = computed(() => {
  const start = (page.value - 1) * perPage
  return sorted.value.slice(start, start + perPage)
})

function isReviewDue(resource: Resource): boolean {
  if (!props.reviewCadenceMonths) return false
  if (!resource.last_reviewed_at) return true
  const reviewed = new Date(resource.last_reviewed_at)
  const dueDate = new Date(reviewed)
  dueDate.setMonth(dueDate.getMonth() + props.reviewCadenceMonths)
  return dueDate <= new Date()
}
</script>

<template>
  <div class="bg-tribal-panel rounded-xl border border-tribal-border overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-tribal-card border-b border-tribal-border">
            <th
              v-for="col in [
                { key: 'name', label: 'Name' },
                { key: 'type', label: 'Type' },
                { key: 'dri', label: 'DRI' },
                { key: 'expiration_date', label: 'Expiration' },
                { key: 'status', label: 'Status' },
              ]"
              :key="col.key"
              class="text-left text-zinc-400 text-xs uppercase tracking-wider px-4 py-3 cursor-pointer hover:text-white select-none transition-colors"
              @click="setSort(col.key as SortKey)"
            >
              {{ col.label }}{{ sortIndicator(col.key as SortKey) }}
            </th>
            <th class="text-zinc-400 text-xs uppercase tracking-wider px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="resource in paginated"
            :key="resource.id"
            class="border-b border-tribal-border/50 hover:bg-tribal-card/50 transition-colors"
          >
            <td class="px-4 py-3">
              <button
                class="text-white hover:text-amber-400 font-medium transition-colors text-left"
                @click="emit('view', resource)"
              >
                {{ resource.name }}
              </button>
              <span
                v-if="isReviewDue(resource)"
                class="ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30"
              >
                Review Due
              </span>
            </td>
            <td class="px-4 py-3">
              <span class="text-zinc-400">{{ resource.type }}</span>
            </td>
            <td class="px-4 py-3 text-zinc-400">{{ resource.dri }}</td>
            <td class="px-4 py-3 text-zinc-400">
              <template v-if="resource.does_not_expire">—</template>
              <template v-else>{{ formatDate(resource.expiration_date) }}</template>
            </td>
            <td class="px-4 py-3">
              <StatusBadge :resource="resource" />
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center justify-end gap-2">
                <!-- View -->
                <button
                  class="text-zinc-400 hover:text-white transition-colors p-1"
                  title="View details"
                  @click="emit('view', resource)"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </button>
                <!-- Edit (non-readonly) -->
                <button
                  v-if="!authStore.user?.is_readonly"
                  class="text-zinc-400 hover:text-amber-400 transition-colors p-1"
                  title="Edit"
                  @click="emit('edit', resource)"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <!-- Delete (non-readonly) -->
                <button
                  v-if="!authStore.user?.is_readonly"
                  class="text-red-400 hover:text-red-300 transition-colors p-1"
                  title="Delete"
                  @click="emit('delete', resource)"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
          <tr v-if="resources.length === 0">
            <td colspan="6" class="px-4 py-12 text-center text-zinc-500">
              No resources found. Add your first resource to get started.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="px-4 py-3 border-t border-tribal-border/50">
      <Pagination
        :total="sorted.length"
        :page="page"
        :per-page="perPage"
        @update:page="page = $event"
      />
    </div>
  </div>
</template>
