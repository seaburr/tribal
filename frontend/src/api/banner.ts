import type { Banner } from '../types'
import { apiFetch } from './client'

// The login banner is public (shown before sign-in); the app banner requires auth.
export const getLoginBanner = () => apiFetch<Banner>('/api/login-banner')
export const getAppBanner = () => apiFetch<Banner>('/api/banner')
