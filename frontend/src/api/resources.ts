import type { Resource, Team, KeyIdentifyResponse } from '../types'
import { apiFetch } from './client'

export const listResources = () => apiFetch<Resource[]>('/api/resources/')

export const getResource = (id: number) => apiFetch<Resource>(`/api/resources/${id}`)

export const createResource = (data: Partial<Resource>) =>
  apiFetch<Resource>('/api/resources/', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateResource = (id: number, data: Partial<Resource>) =>
  apiFetch<Resource>(`/api/resources/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteResource = (id: number) =>
  apiFetch<void>(`/api/resources/${id}`, { method: 'DELETE' })

export const reviewResource = (id: number) =>
  apiFetch<Resource>(`/api/resources/${id}/review`, { method: 'POST' })

export const certLookup = (endpoint: string) =>
  apiFetch<{ expiration_date: string }>('/api/resources/cert-lookup', {
    method: 'POST',
    body: JSON.stringify({ endpoint }),
  })

export const testWebhook = (webhook_url: string) =>
  apiFetch<void>('/api/resources/webhook-test', {
    method: 'POST',
    body: JSON.stringify({ webhook_url }),
  })

export const listProviders = () => apiFetch<string[]>('/api/resources/providers')

export const identifyKey = (key: string, introspect: boolean) =>
  apiFetch<KeyIdentifyResponse>('/api/resources/identify', {
    method: 'POST',
    body: JSON.stringify({ key, introspect }),
  })

export const listTeams = () => apiFetch<Team[]>('/api/resources/teams')

export const getResourceReportUrl = (id: number) => `/api/resources/${id}/report`
