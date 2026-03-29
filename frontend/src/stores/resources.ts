import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Resource, Team } from '../types'
import { listResources, listTeams } from '../api/resources'
import { getAdminSettings } from '../api/admin'

export const useResourcesStore = defineStore('resources', () => {
  const resources = ref<Resource[]>([])
  const teams = ref<Team[]>([])
  const reviewCadenceMonths = ref<number | null>(null)

  async function load() {
    const [r, t, settings] = await Promise.all([
      listResources(),
      listTeams(),
      getAdminSettings().catch(() => null),
    ])
    resources.value = r
    teams.value = t
    if (settings) reviewCadenceMonths.value = settings.review_cadence_months
  }

  // Map of ISO date string → resources expiring that day
  const byDate = computed(() => {
    const map: Record<string, Resource[]> = {}
    for (const r of resources.value) {
      if (r.expiration_date) {
        if (!map[r.expiration_date]) map[r.expiration_date] = []
        map[r.expiration_date].push(r)
      }
    }
    return map
  })

  return { resources, teams, reviewCadenceMonths, load, byDate }
})
