import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AdminSettings, User, AuditEntry, AdminApiKey, DeletedResource } from '../types'
import * as adminApi from '../api/admin'

export const useAdminStore = defineStore('admin', () => {
  const settings = ref<AdminSettings | null>(null)
  const users = ref<User[]>([])
  const auditLog = ref<AuditEntry[]>([])
  const apiKeys = ref<AdminApiKey[]>([])
  const deletedResources = ref<DeletedResource[]>([])

  async function loadSettings() {
    settings.value = await adminApi.getAdminSettings()
  }

  async function loadUsers() {
    users.value = await adminApi.listUsers()
  }

  async function loadAuditLog(limit = 100, offset = 0) {
    const entries = await adminApi.getAuditLog(limit, offset)
    if (offset === 0) auditLog.value = entries
    else auditLog.value = [...auditLog.value, ...entries]
  }

  async function loadApiKeys() {
    apiKeys.value = await adminApi.listAdminApiKeys()
  }

  async function loadDeletedResources() {
    deletedResources.value = await adminApi.listDeletedResources()
  }

  return {
    settings,
    users,
    auditLog,
    apiKeys,
    deletedResources,
    loadSettings,
    loadUsers,
    loadAuditLog,
    loadApiKeys,
    loadDeletedResources,
  }
})
