<script setup lang="ts">
import { ref, computed, inject } from 'vue'
import { useResourcesStore } from '../../stores/resources'
import CalendarView from '../calendar/CalendarView.vue'
import DatelistModal from '../calendar/DatelistModal.vue'
import UpcomingSidebar from './UpcomingSidebar.vue'
import type { Resource } from '../../types'

const resourcesStore = useResourcesStore()
const openResourceDetail = inject<(resource: Resource) => void>('openResourceDetail')!

const selectedDate = ref<string | null>(null)

const dateResources = computed(() =>
  selectedDate.value ? (resourcesStore.byDate[selectedDate.value] ?? []) : []
)

function onDateClick(date: string) {
  if (resourcesStore.byDate[date]?.length) {
    selectedDate.value = date
  }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <!-- Calendar (takes 2/3 width on large screens) -->
    <div class="lg:col-span-2">
      <CalendarView @date-click="onDateClick" />
    </div>

    <!-- Upcoming sidebar (takes 1/3 width) -->
    <div class="lg:col-span-1">
      <UpcomingSidebar />
    </div>
  </div>

  <!-- Date list modal -->
  <DatelistModal
    :date="selectedDate"
    :resources="dateResources"
    @close="selectedDate = null"
    @view-resource="r => { selectedDate = null; openResourceDetail(r) }"
  />
</template>
