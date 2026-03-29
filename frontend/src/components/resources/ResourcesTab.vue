<script setup lang="ts">
import { inject } from 'vue'
import { useResourcesStore } from '../../stores/resources'
import ResourceTable from './ResourceTable.vue'
import type { Resource } from '../../types'

const resourcesStore = useResourcesStore()

const openResourceModal = inject<(id?: number) => void>('openResourceModal')!
const openResourceDetail = inject<(resource: Resource) => void>('openResourceDetail')!
const openDeleteModal = inject<(resource: Resource) => void>('openDeleteModal')!
</script>

<template>
  <div>
    <ResourceTable
      :resources="resourcesStore.resources"
      :review-cadence-months="resourcesStore.reviewCadenceMonths"
      @view="openResourceDetail"
      @edit="r => openResourceModal(r.id)"
      @delete="openDeleteModal"
    />
  </div>
</template>
