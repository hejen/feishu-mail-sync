import axios from 'axios'
import type { Account, AccountCreate, SyncStatus, SyncLog, Provider, MessageResponse, Email } from '../types'

// 后端 API 地址（使用相对路径，由 Nginx 代理）
const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

// ===== 账户管理 =====
export const getAccounts = () =>
  api.get<Account[]>('/accounts')

export const createAccount = (data: AccountCreate) =>
  api.post<MessageResponse>('/accounts', data)

export const deleteAccount = (id: number) =>
  api.delete<MessageResponse>(`/accounts/${id}`)

export const updateAccount = (id: number, data: { is_active?: boolean; auth_code?: string }) =>
  api.put<MessageResponse>(`/accounts/${id}`, data)

// ===== 同步操作 =====
export const manualSync = (limit?: number) =>
  api.post<MessageResponse>('/sync/manual', null, { params: { limit } })

export const manualSyncAccount = (id: number, limit?: number) =>
  api.post<MessageResponse>(`/sync/manual/${id}`, null, { params: { limit } })

export const getSyncStatus = () =>
  api.get<SyncStatus>('/sync/status')

export const getSyncLogs = (limit = 20) =>
  api.get<SyncLog[]>('/sync/logs', { params: { limit } })

export const getSyncedEmails = () =>
  api.get<Email[]>('/sync/emails')

// ===== 配置管理 =====
export const getProviders = () =>
  api.get<Provider[]>('/config/providers')

export const updateSyncInterval = (intervalMinutes: number) =>
  api.put<MessageResponse>('/config/sync-interval', { interval_minutes: intervalMinutes })

export default api
