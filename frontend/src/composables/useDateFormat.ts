import { useAuthStore } from '../stores/auth'
import { formatDateTime as _formatDateTime } from '../utils/date'

/**
 * Returns a formatDateTime function bound to the current user's timezone.
 * Because it reads from the reactive Pinia auth store, Vue will re-render
 * any component using it whenever the user's timezone changes.
 */
export function useDateFormat() {
  const authStore = useAuthStore()

  function formatDateTime(isoDatetime: string | null): string {
    return _formatDateTime(isoDatetime, authStore.user?.timezone ?? undefined)
  }

  return { formatDateTime }
}
