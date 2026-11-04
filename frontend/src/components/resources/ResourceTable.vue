<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, ChevronUp, Eye, FileDown, Pencil, Trash2 } from '@lucide/vue'
import IconButton from '../common/IconButton.vue'
import type { Resource } from '../../types'
import StatusBadge from '../common/StatusBadge.vue'
import Pagination from '../common/Pagination.vue'
import { formatDate, urgency } from '../../utils/date'
import { useAuthStore } from '../../stores/auth'
import { getResourceReportUrl } from '../../api/resources'

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

function ariaSort(key: SortKey) {
  if (sortKey.value !== key) return 'none'
  return sortDir.value === 'asc' ? 'ascending' : 'descending'
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
  const base = new Date(resource.last_reviewed_at ?? resource.created_at)
  const dueDate = new Date(base)
  dueDate.setMonth(dueDate.getMonth() + props.reviewCadenceMonths)
  return dueDate <= new Date()
}
</script>

<template>
  <div class="card overflow-hidden">
    <div class="overflow-x-auto">
      <table class="tbl min-w-[720px]">
        <thead>
          <tr class="bg-tribal-card">
            <th
              v-for="col in [
                { key: 'name', label: 'Name' },
                { key: 'type', label: 'Type' },
                { key: 'dri', label: 'DRI' },
                { key: 'expiration_date', label: 'Expiration' },
                { key: 'status', label: 'Status' },
              ]"
              :key="col.key"
              :aria-sort="ariaSort(col.key as SortKey)"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 uppercase tracking-wide hover:text-white"
                @click="setSort(col.key as SortKey)"
              >
                {{ col.label }}
                <template v-if="sortKey === col.key">
                  <ChevronUp v-if="sortDir === 'asc'" :size="12" aria-hidden="true" />
                  <ChevronDown v-else :size="12" aria-hidden="true" />
                </template>
              </button>
            </th>
            <th class="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="resource in paginated"
            :key="resource.id"
            class="hover:bg-tribal-card/50"
          >
            <td>
              <button
                type="button"
                class="text-left font-medium text-white hover:text-accent-blue-light"
                @click="emit('view', resource)"
              >
                {{ resource.name }}
              </button>
              <span v-if="isReviewDue(resource)" class="badge-review ml-2">Review due</span>
            </td>
            <td class="text-zinc-400">{{ resource.type }}</td>
            <td class="text-zinc-400">{{ resource.dri }}</td>
            <td class="text-zinc-400">
              <template v-if="resource.does_not_expire">—</template>
              <template v-else>{{ formatDate(resource.expiration_date) }}</template>
            </td>
            <td><StatusBadge :resource="resource" /></td>
            <td>
              <div class="flex items-center justify-end gap-0.5">
                <IconButton :icon="Eye" label="View details" sm @click="emit('view', resource)" />
                <IconButton :icon="FileDown" label="Download report" sm :href="getResourceReportUrl(resource.id)" />
                <template v-if="!authStore.user?.is_readonly">
                  <IconButton :icon="Pencil" label="Edit" sm @click="emit('edit', resource)" />
                  <IconButton :icon="Trash2" label="Delete" danger sm @click="emit('delete', resource)" />
                </template>
              </div>
            </td>
          </tr>
          <tr v-if="resources.length === 0">
            <td colspan="6" class="py-12 text-center text-zinc-400">
              No resources found. Add your first resource to get started.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="sorted.length > perPage" class="border-t border-tribal-border">
      <Pagination
        :total="sorted.length"
        :page="page"
        :per-page="perPage"
        @update:page="page = $event"
      />
    </div>
  </div>
</template>
