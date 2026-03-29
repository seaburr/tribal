<script setup lang="ts">
import { ref, provide, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useResourcesStore } from '../stores/resources'
import { useToast } from '../composables/useToast'
import AppHeader from '../components/layout/AppHeader.vue'
import OverviewTab from '../components/overview/OverviewTab.vue'
import ResourcesTab from '../components/resources/ResourcesTab.vue'
import AdminTab from '../components/admin/AdminTab.vue'
import DocsTab from '../components/docs/DocsTab.vue'
import ResourceModal from '../components/resources/ResourceModal.vue'
import ResourceDetailModal from '../components/resources/ResourceDetailModal.vue'
import DeleteConfirmModal from '../components/resources/DeleteConfirmModal.vue'
import ApiKeysModal from '../components/keys/ApiKeysModal.vue'
import { deleteResource } from '../api/resources'
import type { Resource } from '../types'

const authStore = useAuthStore()
const resourcesStore = useResourcesStore()
const { show } = useToast()

type Tab = 'overview' | 'resources' | 'admin' | 'docs'
const activeTab = ref<Tab>('overview')

// ── Modals ─────────────────────────────────────────────────────────────────────
const resourceModalOpen = ref(false)
const resourceModalId = ref<number | null>(null)

const resourceDetailOpen = ref(false)
const resourceDetailItem = ref<Resource | null>(null)

const deleteModalOpen = ref(false)
const deleteModalResource = ref<Resource | null>(null)

const apiKeysModalOpen = ref(false)

// Provide open handlers to child components
function openResourceModal(id?: number) {
  resourceModalId.value = id ?? null
  resourceModalOpen.value = true
}

function openResourceDetail(resource: Resource) {
  resourceDetailItem.value = resource
  resourceDetailOpen.value = true
}

function openDeleteModal(resource: Resource) {
  deleteModalResource.value = resource
  deleteModalOpen.value = true
}

provide('openResourceModal', openResourceModal)
provide('openResourceDetail', openResourceDetail)
provide('openDeleteModal', openDeleteModal)

// ── Resource deletion ──────────────────────────────────────────────────────────
async function handleDeleteConfirmed() {
  if (!deleteModalResource.value) return
  try {
    await deleteResource(deleteModalResource.value.id)
    deleteModalOpen.value = false
    resourceDetailOpen.value = false
    deleteModalResource.value = null
    await resourcesStore.load()
    show('Resource deleted', 'success')
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Delete failed', 'error')
  }
}

async function handleSaved() {
  await resourcesStore.load()
}

async function handleReviewed(updated: Resource) {
  // Update in-place in the store
  const idx = resourcesStore.resources.findIndex(r => r.id === updated.id)
  if (idx >= 0) resourcesStore.resources[idx] = updated
  if (resourceDetailItem.value?.id === updated.id) {
    resourceDetailItem.value = updated
  }
}

function handleEditFromDetail(resource: Resource) {
  resourceDetailOpen.value = false
  openResourceModal(resource.id)
}

function handleDeleteFromDetail(resource: Resource) {
  resourceDetailOpen.value = false
  openDeleteModal(resource)
}

// ── Load resources on mount ────────────────────────────────────────────────────
onMounted(async () => {
  try {
    await resourcesStore.load()
  } catch (e: unknown) {
    show(e instanceof Error ? e.message : 'Failed to load resources', 'error')
  }
})

const tabs = computed(() => {
  const all: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'resources', label: 'Resources' },
  ]
  if (authStore.user?.is_admin) {
    all.push({ key: 'admin', label: 'Admin' })
  }
  all.push({ key: 'docs', label: 'Docs' })
  return all
})
</script>

<template>
  <div class="min-h-screen bg-tribal-bg flex flex-col">
    <!-- Header -->
    <AppHeader
      @add-resource="openResourceModal()"
      @open-api-keys="apiKeysModalOpen = true"
    />

    <!-- Tab navigation -->
    <div class="bg-tribal-panel border-b border-tribal-border px-6">
      <div class="flex gap-6">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="[
            'py-3 text-sm font-medium transition-colors',
            activeTab === tab.key
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-zinc-400 hover:text-zinc-200',
          ]"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- Tab content -->
    <main class="flex-1 p-6">
      <OverviewTab v-if="activeTab === 'overview'" />
      <ResourcesTab v-else-if="activeTab === 'resources'" />
      <AdminTab v-else-if="activeTab === 'admin'" />
      <DocsTab v-else-if="activeTab === 'docs'" />
    </main>

    <!-- Resource create/edit modal -->
    <ResourceModal
      :resource-id="resourceModalId"
      :open="resourceModalOpen"
      @close="resourceModalOpen = false"
      @saved="handleSaved"
    />

    <!-- Resource detail modal -->
    <ResourceDetailModal
      :resource="resourceDetailItem"
      :open="resourceDetailOpen"
      :review-cadence-months="resourcesStore.reviewCadenceMonths"
      @close="resourceDetailOpen = false"
      @edit="handleEditFromDetail"
      @delete="handleDeleteFromDetail"
      @reviewed="handleReviewed"
    />

    <!-- Delete confirmation modal -->
    <DeleteConfirmModal
      :resource="deleteModalResource"
      :open="deleteModalOpen"
      @close="deleteModalOpen = false"
      @confirmed="handleDeleteConfirmed"
    />

    <!-- API Keys modal -->
    <ApiKeysModal
      :open="apiKeysModalOpen"
      @close="apiKeysModalOpen = false"
    />
  </div>
</template>
