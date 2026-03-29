<script setup lang="ts">
import { ref, computed } from 'vue'
import { useResourcesStore } from '../../stores/resources'
import { urgency } from '../../utils/date'

const emit = defineEmits<{
  'date-click': [date: string]
}>()

const resourcesStore = useResourcesStore()

const today = new Date()
const calYear = ref(today.getFullYear())
const calMonth = ref(today.getMonth()) // 0-indexed
const showYearView = ref(false)

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function isoDate(y: number, m: number, d: number) {
  return `${y}-${pad(m + 1)}-${pad(d)}`
}

function getDaysInMonth(y: number, m: number) {
  return new Date(y, m + 1, 0).getDate()
}

function getFirstDayOfWeek(y: number, m: number) {
  return new Date(y, m, 1).getDay()
}

// Build cells for a given year/month
function buildCells(y: number, m: number) {
  const daysInMonth = getDaysInMonth(y, m)
  const firstDay = getFirstDayOfWeek(y, m)
  const cells: Array<{ day: number | null; iso: string | null }> = []

  for (let i = 0; i < firstDay; i++) {
    cells.push({ day: null, iso: null })
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, iso: isoDate(y, m, d) })
  }
  // Pad to full weeks
  while (cells.length % 7 !== 0) {
    cells.push({ day: null, iso: null })
  }
  return cells
}

const cells = computed(() => buildCells(calYear.value, calMonth.value))

const todayISO = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`

function cellUrgency(iso: string | null): 'overdue' | 'upcoming' | null {
  if (!iso) return null
  const resources = resourcesStore.byDate[iso]
  if (!resources || resources.length === 0) return null
  for (const r of resources) {
    const u = urgency(r.expiration_date, r.does_not_expire)
    if (u === 'overdue' || u === 'critical') return 'overdue'
  }
  return 'upcoming'
}

function prevMonth() {
  if (calMonth.value === 0) {
    calMonth.value = 11
    calYear.value--
  } else {
    calMonth.value--
  }
}

function nextMonth() {
  if (calMonth.value === 11) {
    calMonth.value = 0
    calYear.value++
  } else {
    calMonth.value++
  }
}

function goToday() {
  calYear.value = today.getFullYear()
  calMonth.value = today.getMonth()
  showYearView.value = false
}

// Year view: 12 mini-month grids
const yearMonths = computed(() =>
  Array.from({ length: 12 }, (_, m) => ({
    m,
    label: MONTH_NAMES[m].slice(0, 3),
    cells: buildCells(calYear.value, m),
  }))
)
</script>

<template>
  <div class="bg-tribal-panel rounded-xl border border-tribal-border p-4">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <button
          class="text-zinc-400 hover:text-white transition-colors p-1 rounded hover:bg-tribal-card"
          @click="showYearView ? calYear-- : prevMonth()"
        >◀</button>
        <span class="font-semibold text-white min-w-40 text-center">
          <template v-if="showYearView">{{ calYear }}</template>
          <template v-else>{{ MONTH_NAMES[calMonth] }} {{ calYear }}</template>
        </span>
        <button
          class="text-zinc-400 hover:text-white transition-colors p-1 rounded hover:bg-tribal-card"
          @click="showYearView ? calYear++ : nextMonth()"
        >▶</button>
      </div>
      <div class="flex gap-2">
        <button
          class="text-xs px-3 py-1 rounded-lg border border-tribal-border text-zinc-400 hover:text-white hover:border-amber-500/50 transition-colors"
          @click="goToday"
        >
          Today
        </button>
        <button
          :class="[
            'text-xs px-3 py-1 rounded-lg border transition-colors',
            showYearView
              ? 'border-amber-500 text-amber-400'
              : 'border-tribal-border text-zinc-400 hover:border-amber-500/50 hover:text-white',
          ]"
          @click="showYearView = !showYearView"
        >
          Year
        </button>
      </div>
    </div>

    <!-- Month view -->
    <template v-if="!showYearView">
      <!-- Day name headers -->
      <div class="grid grid-cols-7 mb-1">
        <div
          v-for="name in DAY_NAMES"
          :key="name"
          class="text-center text-xs text-zinc-500 py-1 font-medium"
        >
          {{ name }}
        </div>
      </div>
      <!-- Day cells -->
      <div class="grid grid-cols-7 gap-0.5">
        <div
          v-for="(cell, i) in cells"
          :key="i"
          :class="[
            'relative min-h-12 rounded-lg p-1 text-sm transition-colors',
            cell.iso
              ? 'cursor-pointer hover:bg-tribal-card'
              : 'opacity-0 pointer-events-none',
            cell.iso === todayISO ? 'ring-2 ring-amber-500' : '',
            cellUrgency(cell.iso) === 'overdue' ? 'bg-red-500/10' : '',
            cellUrgency(cell.iso) === 'upcoming' ? 'bg-amber-500/10' : '',
          ]"
          @click="cell.iso && emit('date-click', cell.iso)"
        >
          <span
            v-if="cell.day"
            :class="[
              'text-xs font-medium',
              cell.iso === todayISO ? 'text-amber-400' : 'text-zinc-300',
            ]"
          >
            {{ cell.day }}
          </span>
          <!-- Dot indicators -->
          <div
            v-if="cell.iso && resourcesStore.byDate[cell.iso]?.length"
            class="flex gap-0.5 mt-0.5 flex-wrap"
          >
            <span
              v-for="r in resourcesStore.byDate[cell.iso].slice(0, 3)"
              :key="r.id"
              :class="[
                'w-1.5 h-1.5 rounded-full',
                urgency(r.expiration_date, r.does_not_expire) === 'overdue' || urgency(r.expiration_date, r.does_not_expire) === 'critical'
                  ? 'bg-red-400'
                  : urgency(r.expiration_date, r.does_not_expire) === 'warning'
                    ? 'bg-amber-400'
                    : 'bg-yellow-400',
              ]"
            />
            <span
              v-if="resourcesStore.byDate[cell.iso].length > 3"
              class="text-zinc-500 text-xs leading-none"
            >+{{ resourcesStore.byDate[cell.iso].length - 3 }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- Year view -->
    <template v-else>
      <div class="grid grid-cols-3 gap-4">
        <div
          v-for="month in yearMonths"
          :key="month.m"
          class="cursor-pointer rounded-lg p-2 hover:bg-tribal-card/50 transition-colors"
          @click="calMonth = month.m; showYearView = false"
        >
          <p class="text-xs font-semibold text-zinc-400 mb-1 text-center">{{ month.label }}</p>
          <div class="grid grid-cols-7 gap-px">
            <div
              v-for="(cell, i) in month.cells"
              :key="i"
              :class="[
                'w-4 h-4 rounded-sm flex items-center justify-center text-[9px]',
                !cell.day ? 'opacity-0' : '',
                cell.iso === todayISO ? 'ring-1 ring-amber-500 text-amber-400' : 'text-zinc-500',
                cellUrgency(cell.iso) === 'overdue' ? 'bg-red-500/30 text-red-300' : '',
                cellUrgency(cell.iso) === 'upcoming' ? 'bg-amber-500/20 text-amber-300' : '',
              ]"
            >
              {{ cell.day ?? '' }}
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
