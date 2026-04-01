<script setup lang="ts">
import { ref, computed } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'

defineEmits<{
  'add-resource': []
  'open-api-keys': []
}>()

const authStore = useAuthStore()
const { show } = useToast()
const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const changingTimezone = ref(false)
const pendingTimezone = ref('')

onClickOutside(menuRef, () => {
  menuOpen.value = false
  changingTimezone.value = false
})

// Build timezone list from the browser's Intl API, falling back to a curated set.
const timezones = computed<string[]>(() => {
  try {
    return (Intl as any).supportedValuesOf('timeZone') as string[]
  } catch {
    return [
      'Pacific/Honolulu', 'America/Anchorage', 'America/Los_Angeles',
      'America/Denver', 'America/Chicago', 'America/New_York',
      'America/Halifax', 'America/Sao_Paulo', 'Atlantic/Azores',
      'UTC', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
      'Europe/Helsinki', 'Europe/Moscow', 'Asia/Dubai', 'Asia/Karachi',
      'Asia/Kolkata', 'Asia/Dhaka', 'Asia/Bangkok', 'Asia/Shanghai',
      'Asia/Hong_Kong', 'Asia/Seoul', 'Asia/Tokyo', 'Australia/Perth',
      'Australia/Adelaide', 'Australia/Sydney', 'Pacific/Auckland',
    ]
  }
})

const currentTimezone = computed(() =>
  authStore.user?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone
)

function startChangingTimezone() {
  pendingTimezone.value = currentTimezone.value
  changingTimezone.value = true
}

async function saveTimezone() {
  if (!pendingTimezone.value || pendingTimezone.value === currentTimezone.value) {
    changingTimezone.value = false
    return
  }
  try {
    await authStore.setTimezone(pendingTimezone.value)
    show('Timezone updated', 'success')
  } catch {
    show('Failed to update timezone', 'error')
  } finally {
    changingTimezone.value = false
  }
}
</script>

<template>
  <header class="bg-tribal-panel border-b border-tribal-border px-4 sm:px-6 py-3 flex items-center justify-between">
    <!-- Left: Logo + Brand -->
    <div class="flex items-center gap-3">
      <img src="/tribal_logo.png" alt="Tribal" class="h-6 w-6 object-contain" width="24" height="24" />
      <span class="text-white font-bold text-lg tracking-tight">Tribal</span>
    </div>

    <!-- Right: Add Resource + User Menu -->
    <div class="flex items-center gap-2 sm:gap-3">
      <!-- Add Resource button (hidden for readonly users) -->
      <button
        v-if="authStore.user && !authStore.user.is_readonly"
        class="bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors"
        :class="['sm:px-4 sm:py-2 sm:text-sm', 'px-2.5 py-2']"
        :title="'Add Resource'"
        @click="$emit('add-resource')"
      >
        <span class="hidden sm:inline">+ Add Resource</span>
        <svg class="sm:hidden w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
      </button>

      <!-- User menu -->
      <div ref="menuRef" class="relative">
        <button
          class="flex items-center gap-2 text-zinc-300 hover:text-white transition-colors rounded-lg hover:bg-tribal-card"
          :class="['sm:px-3 sm:py-2 sm:text-sm', 'px-2 py-2']"
          :aria-label="menuOpen ? 'Close account menu' : 'Open account menu'"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          <!-- Mobile: user icon only -->
          <svg class="sm:hidden w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <!-- Desktop: name + chevron -->
          <span class="hidden sm:inline">{{ authStore.user?.display_name || authStore.user?.email }}</span>
          <svg
            :class="['hidden sm:block w-4 h-4 transition-transform', menuOpen ? 'rotate-180' : '']"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <Transition name="dropdown">
          <div
            v-if="menuOpen"
            class="absolute right-0 mt-1 w-64 bg-tribal-card border border-tribal-border rounded-xl shadow-xl z-20 py-1"
          >
            <div class="px-4 py-2 border-b border-tribal-border">
              <p class="text-xs text-zinc-500">Signed in as</p>
              <p class="text-sm text-white truncate">{{ authStore.user?.email }}</p>
            </div>

            <!-- Timezone -->
            <div class="px-4 py-2.5 border-b border-tribal-border">
              <p class="text-xs text-zinc-500 mb-1">Timezone</p>
              <div v-if="changingTimezone" class="flex flex-col gap-1.5">
                <select
                  v-model="pendingTimezone"
                  class="w-full bg-tribal-muted border border-tribal-border rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 transition-colors"
                >
                  <option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</option>
                </select>
                <div class="flex gap-2">
                  <button
                    class="flex-1 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-md px-2 py-1 transition-colors"
                    @click="saveTimezone"
                  >
                    Save
                  </button>
                  <button
                    class="flex-1 text-xs text-zinc-400 hover:text-white transition-colors"
                    @click="changingTimezone = false"
                  >
                    Cancel
                  </button>
                </div>
              </div>
              <div v-else class="flex items-center justify-between gap-2">
                <p class="text-xs text-white truncate">{{ currentTimezone }}</p>
                <button
                  class="text-xs text-blue-400 hover:text-blue-300 transition-colors shrink-0"
                  @click="startChangingTimezone"
                >
                  Change
                </button>
              </div>
            </div>

            <button
              class="w-full text-left px-4 py-2.5 text-sm text-zinc-300 hover:text-white hover:bg-tribal-muted/30 transition-colors"
              @click="menuOpen = false; $emit('open-api-keys')"
            >
              🔑 API Keys
            </button>
            <button
              class="w-full text-left px-4 py-2.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
              @click="authStore.signOut()"
            >
              Sign Out
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </header>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-0.25rem);
}
</style>
