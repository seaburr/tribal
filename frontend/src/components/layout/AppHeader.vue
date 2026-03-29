<script setup lang="ts">
import { ref } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { useAuthStore } from '../../stores/auth'

defineEmits<{
  'add-resource': []
  'open-api-keys': []
}>()

const authStore = useAuthStore()
const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)

onClickOutside(menuRef, () => {
  menuOpen.value = false
})
</script>

<template>
  <header class="bg-tribal-panel border-b border-tribal-border px-6 py-3 flex items-center justify-between">
    <!-- Left: Logo + Brand -->
    <div class="flex items-center gap-3">
      <img src="/static/tribal_logo.png" alt="Tribal" class="h-6 w-6 object-contain" />
      <span class="text-amber-400 font-bold text-lg tracking-tight">Tribal</span>
    </div>

    <!-- Right: Add Resource + User Menu -->
    <div class="flex items-center gap-3">
      <!-- Add Resource button (hidden for readonly users) -->
      <button
        v-if="authStore.user && !authStore.user.is_readonly"
        class="bg-amber-500 hover:bg-amber-400 text-black font-semibold rounded-lg px-4 py-2 text-sm transition-colors"
        @click="$emit('add-resource')"
      >
        + Add Resource
      </button>

      <!-- User menu -->
      <div ref="menuRef" class="relative">
        <button
          class="flex items-center gap-2 text-zinc-300 hover:text-white transition-colors px-3 py-2 rounded-lg hover:bg-tribal-card text-sm"
          @click="menuOpen = !menuOpen"
        >
          <span>{{ authStore.user?.display_name || authStore.user?.email }}</span>
          <svg
            :class="['w-4 h-4 transition-transform', menuOpen ? 'rotate-180' : '']"
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
            class="absolute right-0 mt-1 w-48 bg-tribal-card border border-tribal-border rounded-xl shadow-xl z-20 py-1"
          >
            <div class="px-4 py-2 border-b border-tribal-border">
              <p class="text-xs text-zinc-500">Signed in as</p>
              <p class="text-sm text-white truncate">{{ authStore.user?.email }}</p>
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
