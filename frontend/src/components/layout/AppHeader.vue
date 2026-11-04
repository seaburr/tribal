<script setup lang="ts">
import { ref, computed, onBeforeUnmount, nextTick, watch } from 'vue'
import { ChevronDown, CircleUserRound, KeyRound, LogOut, Menu, Plus, X } from '@lucide/vue'
import { useAuthStore } from '../../stores/auth'
import { useToast } from '../../composables/useToast'

defineProps<{
  tabs: { key: string; label: string }[]
  activeTab: string
}>()

const emit = defineEmits<{
  'add-resource': []
  'open-api-keys': []
  'select-tab': [key: string]
}>()

const authStore = useAuthStore()
const { show } = useToast()
const menuOpen = ref(false)
const navOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
const navButton = ref<HTMLButtonElement | null>(null)
const changingTimezone = ref(false)
const pendingTimezone = ref('')

function closeMenu() {
  menuOpen.value = false
  changingTimezone.value = false
}

function onDocumentClick(e: Event) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) closeMenu()
}

watch(menuOpen, (open) => {
  if (open) document.addEventListener('click', onDocumentClick)
  else document.removeEventListener('click', onDocumentClick)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))

function onEscape() {
  closeMenu()
  if (navOpen.value) {
    navOpen.value = false
    nextTick(() => navButton.value?.focus())
  }
}

function selectTab(key: string) {
  navOpen.value = false
  emit('select-tab', key)
}

function skipToContent(e: Event) {
  e.preventDefault()
  const main = document.getElementById('main')
  main?.focus()
  main?.scrollIntoView()
}

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
  <header class="relative border-b border-tribal-border bg-tribal-panel" @keydown.esc="onEscape">
    <a
      href="#main"
      class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-tribal-card focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      @click="skipToContent"
    >
      Skip to content
    </a>
    <div class="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2 sm:px-6">
      <div class="flex min-w-0 items-center gap-1 lg:gap-3">
        <div class="mr-1 flex items-center gap-2 py-1 pr-2">
          <img src="/tribal_logo.png" alt="" class="h-6 w-6 object-contain" width="24" height="24" />
          <span class="font-semibold tracking-tight text-white">Tribal</span>
        </div>

        <nav aria-label="Main" class="hidden items-center gap-0.5 sm:flex">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            :class="['nav-link', activeTab === tab.key ? 'nav-active' : '']"
            :aria-current="activeTab === tab.key ? 'page' : undefined"
            @click="selectTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <button
          v-if="authStore.user && !authStore.user.is_readonly"
          type="button"
          class="btn-primary"
          aria-label="Add resource"
          title="Add resource"
          @click="emit('add-resource')"
        >
          <Plus :size="16" aria-hidden="true" />
          <span class="hidden md:inline" aria-hidden="true">Add resource</span>
        </button>

        <div ref="menuRef" class="relative">
          <button
            type="button"
            class="nav-link gap-1.5"
            aria-haspopup="true"
            :aria-expanded="menuOpen"
            :aria-label="`Account menu (${authStore.user?.email ?? ''})`"
            @click="menuOpen = !menuOpen"
          >
            <CircleUserRound :size="20" aria-hidden="true" />
            <span class="hidden max-w-40 truncate lg:inline" aria-hidden="true">{{ authStore.user?.display_name || authStore.user?.email }}</span>
            <ChevronDown :size="14" :class="['hidden transition-transform lg:block', menuOpen ? 'rotate-180' : '']" aria-hidden="true" />
          </button>

          <div
            v-if="menuOpen"
            class="absolute right-0 z-20 mt-1 w-64 rounded-md border border-tribal-border bg-tribal-panel py-1 shadow-xl"
          >
            <div class="border-b border-tribal-border px-3 py-2">
              <p class="meta">Signed in as</p>
              <p class="truncate text-sm text-white">{{ authStore.user?.email }}</p>
            </div>

            <div class="border-b border-tribal-border px-3 py-2">
              <template v-if="changingTimezone">
                <label for="header-timezone" class="meta mb-1 block">Timezone</label>
                <select id="header-timezone" v-model="pendingTimezone" class="input">
                  <option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</option>
                </select>
                <div class="mt-2 flex gap-2">
                  <button type="button" class="btn-primary btn-sm flex-1" @click="saveTimezone">Save</button>
                  <button type="button" class="btn-ghost btn-sm flex-1" @click.stop="changingTimezone = false">Cancel</button>
                </div>
              </template>
              <template v-else>
                <p class="meta mb-1">Timezone</p>
                <div class="flex items-center justify-between gap-2">
                  <p class="truncate text-xs text-white">{{ currentTimezone }}</p>
                  <button type="button" class="link shrink-0 text-xs" @click.stop="startChangingTimezone">Change</button>
                </div>
              </template>
            </div>

            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-zinc-300 hover:bg-tribal-card hover:text-white"
              @click="closeMenu(); emit('open-api-keys')"
            >
              <KeyRound :size="16" aria-hidden="true" />
              API keys
            </button>
            <button
              type="button"
              class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger-light hover:bg-danger/10"
              @click="authStore.signOut()"
            >
              <LogOut :size="16" aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>

        <button
          ref="navButton"
          type="button"
          class="btn-icon sm:hidden"
          aria-label="Menu"
          aria-controls="mobile-nav"
          :aria-expanded="navOpen"
          @click="navOpen = !navOpen"
        >
          <X v-if="navOpen" :size="16" aria-hidden="true" />
          <Menu v-else :size="16" aria-hidden="true" />
        </button>
      </div>
    </div>

    <nav
      v-show="navOpen"
      id="mobile-nav"
      aria-label="Main (mobile)"
      class="absolute inset-x-0 top-full z-40 flex flex-col gap-0.5 border-b border-tribal-border bg-tribal-panel px-4 pb-4 pt-2 shadow-xl sm:hidden"
    >
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="['nav-link', activeTab === tab.key ? 'nav-active' : '']"
        :aria-current="activeTab === tab.key ? 'page' : undefined"
        @click="selectTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>
  </header>
</template>
