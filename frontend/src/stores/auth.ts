import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '../types'
import { getMe, logout as apiLogout } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loaded = ref(false)

  async function load() {
    try {
      user.value = await getMe()
    } catch {
      user.value = null
    } finally {
      loaded.value = true
    }
  }

  async function signOut() {
    await apiLogout()
    user.value = null
    window.location.href = '/login'
  }

  return { user, loaded, load, signOut }
})
