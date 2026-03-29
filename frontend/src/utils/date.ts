export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function daysUntil(isoDate: string | null): number | null {
  if (!isoDate) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(isoDate + 'T00:00:00')
  return Math.floor((target.getTime() - today.getTime()) / 86400000)
}

export function formatDate(isoDate: string | null): string {
  if (!isoDate) return '—'
  const [y, m, d] = isoDate.split('-')
  return `${m}/${d}/${y}`
}

export function formatDateTime(isoDatetime: string | null): string {
  if (!isoDatetime) return '—'
  return new Date(isoDatetime).toLocaleString()
}

export type Urgency = 'overdue' | 'critical' | 'warning' | 'upcoming' | 'ok' | 'none'

export function urgency(isoDate: string | null, doesNotExpire: boolean): Urgency {
  if (doesNotExpire) return 'none'
  const days = daysUntil(isoDate)
  if (days === null) return 'none'
  if (days < 0) return 'overdue'
  if (days <= 7) return 'critical'
  if (days <= 30) return 'warning'
  if (days <= 60) return 'upcoming'
  return 'ok'
}
