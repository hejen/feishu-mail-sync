// 邮箱提供商
export interface Provider {
  name: string
  value: string
  imap_server: string
  imap_port: number
  help_url: string
}

// 邮箱账户
export interface Account {
  id: number
  email: string
  provider: string
  imap_server: string
  imap_port: number
  last_sync_time: string | null
  is_active: boolean
  created_at: string
}

// 创建账户请求
export interface AccountCreate {
  email: string
  auth_code: string
  provider: string
}

// 同步状态
export interface SyncStatus {
  is_syncing: boolean
  last_sync_time: string | null
  total_emails: number
  accounts: Array<{
    email: string
    status: string
    last_sync: string | null
  }>
}

// 同步日志
export interface SyncLog {
  id: number
  account_id: number
  sync_time: string
  emails_count: number
  status: string
  error_message: string | null
}

// 邮件数据
export interface Email {
  message_id: string
  subject: string
  sender: string
  receiver: string
  date: string
  body: string
  attachments: Array<{
    filename: string
    content: string  // base64
  }>
}

// 通用响应
export interface MessageResponse {
  message: string
  success: boolean
}
