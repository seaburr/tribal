import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '../types'
import { getMe, logout as apiLogout, updateMe } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loaded = ref(false)

  async function load() {
    try {
      const u = await getMe()
      user.value = u
      // If the user has no saved timezone, detect from the browser and persist it.
      if (!u.timezone) {
        const detected = Intl.DateTimeFormat().resolvedOptions().timeZone
        try {
          user.value = await updateMe({ timezone: detected })
        } catch {
          // Non-fatal — the user will just see browser-default formatting
        }
      }
    } catch {
      user.value = null
    } finally {
      loaded.value = true
    }
  }

  async function setTimezone(tz: string) {
    user.value = await updateMe({ timezone: tz })
  }

  async function signOut() {
    await apiLogout()
    user.value = null
    window.location.href = '/login'
  }

  return { user, loaded, load, signOut, setTimezone }
})
