import type { ApiKey, ApiKeyCreated } from '../types'
import { apiFetch } from './client'

export const listApiKeys = () => apiFetch<ApiKey[]>('/api/keys/')

export const createApiKey = (name: string) =>
  apiFetch<ApiKeyCreated>('/api/keys/', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })

export const revokeApiKey = (id: number) =>
  apiFetch<void>(`/api/keys/${id}`, { method: 'DELETE' })
