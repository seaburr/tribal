import type { User } from '../types'
import { apiFetch } from './client'

export const getMe = () => apiFetch<User>('/auth/me')

export const login = (email: string, password: string) =>
  apiFetch<void>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })

export const register = (email: string, password: string, display_name?: string) =>
  apiFetch<void>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name }),
  })

export const logout = () => apiFetch<void>('/auth/logout', { method: 'POST' })
