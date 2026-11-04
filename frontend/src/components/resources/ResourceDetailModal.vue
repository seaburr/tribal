<script setup lang="ts">
import { computed } from 'vue'
import { Check, FileDown, Pencil, Trash2 } from '@lucide/vue'
import type { Resource } from '../../types'
import BaseModal from '../common/BaseModal.vue'
import StatusBadge from '../common/StatusBadge.vue'
import { formatDate } from '../../utils/date'
import { useDateFormat } from '../../composables/useDateFormat'
import { useAuthStore } from '../../stores/auth'
import { reviewResource } from '../../api/resources'
import { getResourceReportUrl } from '../../api/resources'
import { useToast } from '../../composables/useToast'

const props = defineProps<{
  resource: Resource | null
  open: boolean
  reviewCadenceMonths: number | null
}>()

const emit = defineEmits<{
  close: []
  edit: [resource: Resource]
  delete: [resource: Resource]
  reviewed: [resource: Resource]
}>()

const authStore = useAuthStore()
const { show } = useToast()
const { formatDateTime } = useDateFormat()

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function linkify(text: string): string {
  if (!text) return ''
  const urlRegex = /(https?:\/\/[^\s<>"']+)/g
  const parts = text.split(urlRegex)
  return parts
    .map((part, i) => {
      if (i % 2 === 1) {
        // URL match
        const escaped = escapeHtml(part)
        return `<a href="${escaped}" target="_blank" rel="noopener noreferrer" class="link underline">${escaped}</a>`
      }
      return escapeHtml(part).replace(/\n/g, '<br>')
    })
    .join('')
}

const purposeHtml = computed(() => (props.resource ? linkify(props.resource.purpose) : ''))
const instructionsHtml = computed(() =>
  props.resource ? linkify(props.resource.generation_instructions) : ''
)

function isReviewDue(): boolean {
  if (!props.reviewCadenceMonths || !props.resource) return false
  const base = new Date(props.resource.last_reviewed_at ?? props.resource.created_at)
  const dueDate = new Date(base)
  dueDate.setMonth(dueDate.getMonth() + props.reviewCadenceMonths)
  return dueDate <= new Date()
}

async function handleReview() {
  if (!props.resource) return
  try {
    const updated = await reviewResource(props.resource.id)
    show('Resource marked as reviewed', 'success')
    emit('reviewed', updated)
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Review failed', 'error')
  }
}

function openReport() {
  if (!props.resource) return
  window.open(getResourceReportUrl(props.resource.id), '_blank')
}
</script>

<template>
  <BaseModal
    :title="resource?.name ?? ''"
    :open="open"
    @close="emit('close')"
  >
    <div v-if="!resource" class="py-8 text-center text-zinc-400">Loading…</div>

    <div v-else class="space-y-5">
      <!-- Header row: type + status -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="badge-neutral">
          {{ resource.type }}
        </span>
        <StatusBadge :resource="resource" />
        <span v-if="isReviewDue()" class="badge-review">Review due</span>
      </div>

      <!-- Details grid -->
      <div class="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
        <div>
          <p class="table-th mb-1">Expiration</p>
          <p class="text-white">
            {{ resource.does_not_expire ? 'Does not expire' : formatDate(resource.expiration_date) }}
          </p>
        </div>
        <div>
          <p class="table-th mb-1">DRI</p>
          <p class="text-white">{{ resource.dri }}</p>
        </div>
        <div v-if="resource.provider">
          <p class="table-th mb-1">Provider</p>
          <p class="text-white">{{ resource.provider }}</p>
        </div>
        <div v-if="reviewCadenceMonths">
          <p class="table-th mb-1">Last reviewed</p>
          <p class="text-white">{{ formatDateTime(resource.last_reviewed_at) }}</p>
        </div>
        <div>
          <p class="table-th mb-1">Created</p>
          <p class="text-white">{{ formatDateTime(resource.created_at) }}</p>
        </div>
        <div>
          <p class="table-th mb-1">Updated</p>
          <p class="text-white">{{ formatDateTime(resource.updated_at) }}</p>
        </div>
      </div>

      <!-- Purpose -->
      <div v-if="resource.purpose">
        <p class="table-th mb-1">Purpose</p>
        <p class="text-sm leading-relaxed text-zinc-300 wrap-break-word" v-html="purposeHtml" />
      </div>

      <!-- Instructions -->
      <div v-if="resource.generation_instructions">
        <p class="table-th mb-1">Rotation / generation instructions</p>
        <div
          class="rounded-md border border-tribal-border bg-tribal-card p-3 text-sm leading-relaxed text-zinc-300 wrap-break-word"
          v-html="instructionsHtml"
        />
      </div>

      <!-- Secret Manager Link -->
      <div v-if="resource.secret_manager_link">
        <p class="table-th mb-1">Secret manager</p>
        <a
          :href="resource.secret_manager_link"
          target="_blank"
          rel="noopener noreferrer"
          class="link text-sm break-all underline"
        >
          {{ resource.secret_manager_link }}
        </a>
      </div>

      <!-- Actions -->
      <div class="flex flex-wrap gap-2 border-t border-tribal-border pt-4">
        <button type="button" class="btn-secondary" @click="openReport">
          <FileDown :size="16" aria-hidden="true" />
          Download report
        </button>
        <template v-if="!authStore.user?.is_readonly">
          <button v-if="reviewCadenceMonths" type="button" class="btn-secondary" @click="handleReview">
            <Check :size="16" aria-hidden="true" />
            Mark reviewed
          </button>
          <button type="button" class="btn-secondary" @click="emit('edit', resource)">
            <Pencil :size="16" aria-hidden="true" />
            Edit
          </button>
          <button type="button" class="btn-danger" @click="emit('delete', resource)">
            <Trash2 :size="16" aria-hidden="true" />
            Delete
          </button>
        </template>
      </div>
    </div>
  </BaseModal>
</template>
