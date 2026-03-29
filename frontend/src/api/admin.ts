import type { AdminSettings, User, AuditEntry, AdminApiKey, DeletedResource, Resource, Team } from '../types'
import { apiFetch } from './client'

export const getAdminSettings = () => apiFetch<AdminSettings>('/admin/settings')

export const updateAdminSettings = (data: AdminSettings) =>
  apiFetch<AdminSettings>('/admin/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const testAdminWebhook = () =>
  apiFetch<void>('/admin/webhook-test', { method: 'POST' })

export const listAdminTeams = () => apiFetch<Team[]>('/admin/teams')

export const createTeam = (name: string) =>
  apiFetch<Team>('/admin/teams', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })

export const updateTeam = (id: number, name: string) =>
  apiFetch<Team>(`/admin/teams/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  })

export const listUsers = () => apiFetch<User[]>('/admin/users')

export const setUserRole = (id: number, is_admin: boolean) =>
  apiFetch<User>(`/admin/users/${id}/role`, {
    method: 'PUT',
    body: JSON.stringify({ is_admin }),
  })

export const setUserReadonly = (id: number, is_readonly: boolean) =>
  apiFetch<User>(`/admin/users/${id}/readonly`, {
    method: 'PUT',
    body: JSON.stringify({ is_readonly }),
  })

export const deleteUser = (id: number) =>
  apiFetch<void>(`/admin/users/${id}`, { method: 'DELETE' })

export const getAuditLog = (limit: number, offset: number) =>
  apiFetch<AuditEntry[]>(`/admin/audit-log?limit=${limit}&offset=${offset}`)

export const listDeletedResources = () =>
  apiFetch<DeletedResource[]>('/admin/resources/deleted')

export const restoreResource = (id: number) =>
  apiFetch<Resource>(`/admin/resources/${id}/restore`, { method: 'POST' })

export const purgeResource = (id: number) =>
  apiFetch<void>(`/admin/resources/${id}/purge`, { method: 'DELETE' })

export const listAdminApiKeys = () => apiFetch<AdminApiKey[]>('/admin/api-keys')

export const revokeAdminApiKey = (id: number) =>
  apiFetch<void>(`/admin/api-keys/${id}`, { method: 'DELETE' })
