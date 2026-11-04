<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import IconButton from '../common/IconButton.vue'
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
  // Pad to always 6 rows (42 cells) for a consistent calendar height
  while (cells.length < 42) {
    cells.push({ day: null, iso: null })
  }
  return cells
}

const cells = computed(() => buildCells(calYear.value, calMonth.value))

const todayISO = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`

// Returns the worst-case color bucket for a calendar cell.
// Priority: overdue > critical > amber > green
type CellColor = 'overdue' | 'critical' | 'amber' | 'green'

function cellColor(iso: string | null): CellColor | null {
  if (!iso) return null
  const resources = resourcesStore.byDate[iso]
  if (!resources || resources.length === 0) return null
  let best = null as CellColor | null
  const rank = { overdue: 4, critical: 3, amber: 2, green: 1 } as const
  for (const r of resources) {
    const u = urgency(r.expiration_date, r.does_not_expire)
    const bucket: CellColor | null =
      u === 'overdue'              ? 'overdue'  :
      u === 'critical'             ? 'critical' :
      u === 'warning'              ? 'amber'    :
      (u === 'upcoming' || u === 'ok') ? 'green' : null
    if (bucket && (best === null || rank[bucket] > rank[best])) best = bucket
  }
  return best
}

// Per-resource dot color used in the month view.
function dotColor(r: { expiration_date: string | null; does_not_expire: boolean }): string {
  const u = urgency(r.expiration_date, r.does_not_expire)
  if (u === 'overdue')  return 'bg-status-overdue'
  if (u === 'critical') return 'bg-status-critical'
  if (u === 'warning')  return 'bg-status-warning'
  return 'bg-accent-green'
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
  <div class="card card-pad">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-1">
        <IconButton :icon="ChevronLeft" :label="showYearView ? 'Previous year' : 'Previous month'" @click="showYearView ? calYear-- : prevMonth()" />
        <h2 class="section-title min-w-20 text-center" aria-live="polite">
          <template v-if="showYearView">{{ calYear }}</template>
          <template v-else>{{ MONTH_NAMES[calMonth].slice(0, 3) }} {{ calYear }}</template>
        </h2>
        <IconButton :icon="ChevronRight" :label="showYearView ? 'Next year' : 'Next month'" @click="showYearView ? calYear++ : nextMonth()" />
      </div>
      <div class="flex gap-2">
        <button type="button" class="btn-secondary btn-sm" @click="goToday">
          Today
        </button>
        <button
          type="button"
          :class="['btn-secondary btn-sm', showYearView ? 'border-status-warning text-status-warning hover:text-status-warning' : '']"
          :aria-pressed="showYearView"
          @click="showYearView = !showYearView"
        >
          Year
        </button>
      </div>
    </div>

    <!-- Fixed-height body shared by both views -->
    <div class="h-[520px] flex flex-col">

    <!-- Month view -->
    <template v-if="!showYearView">
      <!-- Day name headers -->
      <div class="grid grid-cols-7 mb-1 shrink-0">
        <div
          v-for="name in DAY_NAMES"
          :key="name"
          class="text-center text-xs text-zinc-500 py-1 font-medium"
        >
          {{ name }}
        </div>
      </div>
      <!-- Day cells — flex-1 + grid-auto-rows:1fr makes cells fill the height and stay square -->
      <div class="flex-1 grid grid-cols-7 gap-0.5" style="grid-auto-rows: 1fr">
        <component
          :is="cell.iso ? 'button' : 'div'"
          v-for="(cell, i) in cells"
          :key="i"
          :type="cell.iso ? 'button' : undefined"
          :aria-label="cell.iso ? `${cell.iso}${resourcesStore.byDate[cell.iso]?.length ? `, ${resourcesStore.byDate[cell.iso].length} expiring` : ''}` : undefined"
          :class="[
            'relative rounded-md p-1 text-left align-top text-sm transition-colors',
            cell.iso
              ? 'flex flex-col items-start justify-start hover:bg-tribal-card'
              : 'pointer-events-none opacity-0',
            cell.iso === todayISO ? 'ring-2 ring-status-warning' : '',
            cellColor(cell.iso) === 'overdue'  ? 'bg-status-overdue/20 ring-1 ring-status-overdue/35' : '',
            cellColor(cell.iso) === 'critical' ? 'bg-status-critical/15'  : '',
            cellColor(cell.iso) === 'amber'    ? 'bg-status-warning/10'   : '',
            cellColor(cell.iso) === 'green'    ? 'bg-accent-green/10' : '',
          ]"
          @click="cell.iso && emit('date-click', cell.iso)"
        >
          <span
            v-if="cell.day"
            :class="[
              'text-xs font-medium',
              cell.iso === todayISO ? 'text-status-warning' : 'text-zinc-300',
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
              :class="['w-1.5 h-1.5 rounded-full', dotColor(r)]"
            />
            <span
              v-if="resourcesStore.byDate[cell.iso].length > 3"
              class="text-xs leading-none text-zinc-400"
            >+{{ resourcesStore.byDate[cell.iso].length - 3 }}</span>
          </div>
        </component>
      </div>
    </template>

    <!-- Year view -->
    <template v-else>
      <div class="grid grid-cols-3 gap-2">
        <button
          v-for="month in yearMonths"
          :key="month.m"
          type="button"
          :aria-label="`${MONTH_NAMES[month.m]} ${calYear}`"
          class="rounded-md p-1 transition-colors hover:bg-tribal-card/50"
          @click="calMonth = month.m; showYearView = false"
        >
          <p class="mb-1 text-center text-xs font-semibold text-zinc-400">{{ month.label }}</p>
          <div class="grid w-fit grid-cols-7 gap-px mx-auto">
            <div
              v-for="(cell, i) in month.cells"
              :key="i"
              :class="[
                'h-3.5 w-3.5 rounded-xs flex sm:h-4 sm:w-4 items-center justify-center text-[9px]',
                !cell.day ? 'opacity-0' : '',
                cell.iso === todayISO ? 'ring-1 ring-status-warning text-status-warning' : 'text-zinc-500',
                cellColor(cell.iso) === 'overdue'  ? 'bg-status-overdue/60 text-zinc-100 font-bold' : '',
                cellColor(cell.iso) === 'critical' ? 'bg-status-critical/30 text-status-critical'   : '',
                cellColor(cell.iso) === 'amber'    ? 'bg-status-warning/20 text-status-warning'     : '',
                cellColor(cell.iso) === 'green'    ? 'bg-accent-green/20 text-accent-green-light' : '',
              ]"
            >
              {{ cell.day ?? '' }}
            </div>
          </div>
        </button>
      </div>
    </template>

    </div> <!-- end fixed-height body -->
  </div>
</template>
