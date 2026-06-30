import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Banner } from '../types'
import { getAppBanner } from '../api/banner'

export const useBannerStore = defineStore('banner', () => {
  const appBanner = ref<Banner | null>(null)

  async function loadAppBanner() {
    try {
      appBanner.value = await getAppBanner()
    } catch {
      // Non-fatal — a missing banner just means none is shown.
      appBanner.value = null
    }
  }

  return { appBanner, loadAppBanner }
})
