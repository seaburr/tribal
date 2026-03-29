<script setup lang="ts">
import { computed } from 'vue'
import type { Resource } from '../../types'
import BaseModal from '../common/BaseModal.vue'
import StatusBadge from '../common/StatusBadge.vue'
import { formatDate, formatDateTime } from '../../utils/date'
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
        return `<a href="${escaped}" target="_blank" rel="noopener noreferrer" class="text-amber-400 hover:text-amber-300 underline">${escaped}</a>`
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
  if (!props.resource.last_reviewed_at) return true
  const reviewed = new Date(props.resource.last_reviewed_at)
  const dueDate = new Date(reviewed)
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
    <div v-if="!resource" class="py-8 text-center text-zinc-400">Loading...</div>

    <div v-else class="space-y-5">
      <!-- Header row: type + status -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm text-zinc-500 bg-tribal-muted/30 px-3 py-1 rounded-full border border-tribal-border">
          {{ resource.type }}
        </span>
        <StatusBadge :resource="resource" />
        <span
          v-if="isReviewDue()"
          class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 border border-purple-500/30"
        >
          Review Due
        </span>
      </div>

      <!-- Details grid -->
      <div class="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Expiration</p>
          <p class="text-white">
            {{ resource.does_not_expire ? 'Does not expire' : formatDate(resource.expiration_date) }}
          </p>
        </div>
        <div>
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">DRI</p>
          <p class="text-white">{{ resource.dri }}</p>
        </div>
        <div v-if="resource.provider">
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Provider</p>
          <p class="text-white">{{ resource.provider }}</p>
        </div>
        <div v-if="reviewCadenceMonths">
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Last Reviewed</p>
          <p class="text-white">{{ formatDateTime(resource.last_reviewed_at) }}</p>
        </div>
        <div>
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Created</p>
          <p class="text-white">{{ formatDateTime(resource.created_at) }}</p>
        </div>
        <div>
          <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Updated</p>
          <p class="text-white">{{ formatDateTime(resource.updated_at) }}</p>
        </div>
      </div>

      <!-- Purpose -->
      <div v-if="resource.purpose">
        <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Purpose</p>
        <p class="text-zinc-300 text-sm leading-relaxed" v-html="purposeHtml" />
      </div>

      <!-- Instructions -->
      <div v-if="resource.generation_instructions">
        <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Rotation / Generation Instructions</p>
        <div
          class="bg-tribal-card rounded-lg border border-tribal-border p-3 text-sm text-zinc-300 leading-relaxed"
          v-html="instructionsHtml"
        />
      </div>

      <!-- Secret Manager Link -->
      <div v-if="resource.secret_manager_link">
        <p class="text-zinc-500 text-xs uppercase tracking-wider mb-1">Secret Manager</p>
        <a
          :href="resource.secret_manager_link"
          target="_blank"
          rel="noopener noreferrer"
          class="text-amber-400 hover:text-amber-300 underline text-sm"
        >
          {{ resource.secret_manager_link }}
        </a>
      </div>

      <!-- Actions -->
      <div class="flex flex-wrap gap-2 pt-3 border-t border-tribal-border">
        <button
          class="px-4 py-2 border border-tribal-border text-zinc-400 hover:text-white hover:border-zinc-500 rounded-lg text-sm transition-colors"
          @click="openReport"
        >
          📄 Download Report
        </button>
        <button
          v-if="reviewCadenceMonths && !authStore.user?.is_readonly"
          class="px-4 py-2 border border-purple-500/50 text-purple-400 hover:border-purple-500 rounded-lg text-sm transition-colors"
          @click="handleReview"
        >
          ✓ Mark Reviewed
        </button>
        <button
          v-if="!authStore.user?.is_readonly"
          class="px-4 py-2 border border-amber-500/50 text-amber-400 hover:border-amber-500 rounded-lg text-sm transition-colors"
          @click="emit('edit', resource)"
        >
          ✏️ Edit
        </button>
        <button
          v-if="!authStore.user?.is_readonly"
          class="px-4 py-2 border border-red-500/50 text-red-400 hover:border-red-500 rounded-lg text-sm transition-colors"
          @click="emit('delete', resource)"
        >
          🗑️ Delete
        </button>
      </div>
    </div>
  </BaseModal>
</template>
