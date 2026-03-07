import { useState, useEffect, useCallback, useRef } from 'react'
import { ConfigProvider, Button, message, Space, InputNumber, Progress } from 'antd'
import { PlusOutlined, SyncOutlined } from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'

import { StatusPanel } from './components/StatusPanel'
import { AccountList } from './components/AccountList'
import { SyncLogs } from './components/SyncLogs'
import { AddAccountModal } from './components/AddAccountModal'
import { useBitable } from './hooks/useBitable'
import { useUserId } from './hooks/useUserId'
import * as api from './services/api'
import { setApiUserId } from './services/api'
import type { Account, SyncStatus, SyncLog, Provider } from './types'
import type { SyncProgress } from './services/api'

function App() {
  // 用户身份
  const { userId, loading: userIdLoading, error: userIdError } = useUserId()

  // 同步 userId 到 API 客户端
  useEffect(() => {
    if (userId) {
      setApiUserId(userId)
    }
  }, [userId])

  // 状态
  const [accounts, setAccounts] = useState<Account[]>([])
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [syncLimit, setSyncLimit] = useState(() => {
    const saved = localStorage.getItem('syncLimit')
    return saved ? parseInt(saved) : 100
  })
  const [filterSyncedEmails, setFilterSyncedEmails] = useState<boolean>(() => {
    const saved = localStorage.getItem('filterSyncedEmails')
    return saved ? saved === 'true' : false  // 默认 false（不勾选）
  })
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null)
  const progressPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { writeEmails } = useBitable()

  // 加载数据
  const loadData = useCallback(async () => {
    if (!userId) return

    try {
      const [accountsRes, statusRes, logsRes, providersRes] = await Promise.all([
        api.getAccounts(),
        api.getSyncStatus(),
        api.getSyncLogs(),
        api.getProviders()
      ])
      // 验证 API 响应数据
      setAccounts(Array.isArray(accountsRes.data) ? accountsRes.data : [])
      setSyncStatus(statusRes.data || null)
      setSyncLogs(Array.isArray(logsRes.data) ? logsRes.data.slice(0, 10) : [])
      setProviders(Array.isArray(providersRes.data) ? providersRes.data : [])
    } catch (err) {
      console.error('加载数据失败:', err)
      const errorMsg = err instanceof Error ? err.message : '加载数据失败'
      message.error(errorMsg)
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (userId) {
      loadData()
    }
  }, [loadData, userId])

  // 清理进度轮询
  const clearProgressPoll = useCallback(() => {
    if (progressPollRef.current) {
      clearInterval(progressPollRef.current)
      progressPollRef.current = null
    }
  }, [])

  // 检查同步进度
  const checkSyncProgress = useCallback(async () => {
    const res = await api.getSyncProgress()
    setSyncProgress(res.data)

    if (res.data.status === 'completed') {
      clearProgressPoll()
      message.success(res.data.message || '同步完成')
      await writeSyncedEmails()
      setSyncing(false)
      loadData()
    } else if (res.data.status === 'failed') {
      clearProgressPoll()
      message.error(res.data.error || res.data.message || '同步失败')
      setSyncing(false)
    }
  }, [clearProgressPoll, loadData])

  // 写入同步的邮件到多维表格
  const writeSyncedEmails = useCallback(async () => {
    const emailsRes = await api.getSyncedEmails()
    if (emailsRes.data.length === 0) return

    const result = await writeEmails(emailsRes.data)
    if (result.success) {
      const mockHint = (result as any).isMockMode ? ' (本地模拟模式)' : ''
      message.success(`已写入 ${result.count} 封邮件到多维表格${mockHint}`)
    } else {
      message.error(result.message || '写入多维表格失败')
    }
  }, [writeEmails])

  // 开始进度轮询
  const startProgressPoll = useCallback(() => {
    clearProgressPoll()
    
    const MAX_FAILS = 5
    let failCount = 0

    progressPollRef.current = setInterval(async () => {
      try {
        await checkSyncProgress()
        failCount = 0
      } catch (err) {
        failCount++
        console.error(`获取进度失败 (${failCount}/${MAX_FAILS}):`, err)
        
        if (failCount >= MAX_FAILS) {
          clearProgressPoll()
          message.error('获取同步进度失败，请刷新页面')
          setSyncing(false)
        }
      }
    }, 1000)
  }, [clearProgressPoll, checkSyncProgress])

  // 组件卸载时清理
  useEffect(() => {
    return () => clearProgressPoll()
  }, [clearProgressPoll])

  // 同步所有账户（异步模式）
  const handleSyncAll = async () => {
    if (syncing) return

    setSyncing(true)
    setSyncProgress({ total: 0, current: 0, status: 'syncing', message: '启动同步...', error: null })

    try {
      await api.manualSync(syncLimit, filterSyncedEmails)
      message.info('同步任务已启动，请稍候...')
      startProgressPoll()
    } catch (err: any) {
      setSyncing(false)
      setSyncProgress(null)
      message.error(err.response?.data?.detail || '启动同步失败')
    }
  }

  // 同步单个账户（异步模式）
  const handleSyncAccount = async (id: number) => {
    if (syncing) return

    setSyncing(true)
    setSyncProgress({ total: 0, current: 0, status: 'syncing', message: '启动同步...', error: null })

    try {
      await api.manualSyncAccount(id, syncLimit, filterSyncedEmails)
      message.info('同步任务已启动，请稍候...')
      startProgressPoll()
    } catch (err: any) {
      setSyncing(false)
      setSyncProgress(null)
      message.error(err.response?.data?.detail || '启动同步失败')
    }
  }

  // 删除账户
  const handleDeleteAccount = async (id: number) => {
    try {
      await api.deleteAccount(id)
      message.success('删除成功')
      loadData()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : '删除失败'
      message.error(errorMsg)
    }
  }

  // 添加账户
  const handleAddAccount = async (data: { email: string; auth_code: string; provider: string }) => {
    try {
      await api.createAccount(data)
      message.success('添加成功')
      setModalVisible(false)
      loadData()
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : '添加失败'
      message.error(errorMsg)
    }
  }

  // 处理同步条数变更
  const handleSyncLimitChange = (value: number | null) => {
    const limit = Math.max(1, Math.min(99999, value || 100))
    setSyncLimit(limit)
    localStorage.setItem('syncLimit', String(limit))
  }

  // 处理过滤已同步邮件变更
  const handleFilterSyncedChange = (checked: boolean) => {
    setFilterSyncedEmails(checked)
    localStorage.setItem('filterSyncedEmails', String(checked))
  }

  // 等待用户身份加载
  if (userIdLoading) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center' }}>
          正在加载用户信息...
        </div>
      </ConfigProvider>
    )
  }

  // 用户身份加载失败
  if (userIdError) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center', color: 'red' }}>
          加载失败: {userIdError}
        </div>
      </ConfigProvider>
    )
  }

  // 没有用户ID（不应该发生）
  if (!userId) {
    return (
      <ConfigProvider locale={zhCN}>
        <div style={{ padding: 16, maxWidth: 400, margin: '0 auto', textAlign: 'center', color: 'red' }}>
          无法获取用户身份
        </div>
      </ConfigProvider>
    )
  }

  return (
    <ConfigProvider locale={zhCN}>
      <div style={{ padding: 16, maxWidth: 400, margin: '0 auto' }}>
        <h1 style={{ marginBottom: 16 }}>📬 邮箱同步助手</h1>

        <StatusPanel status={syncStatus} loading={loading} />

        <AccountList
          accounts={accounts}
          loading={loading}
          syncing={syncing}
          onSync={handleSyncAccount}
          onDelete={handleDeleteAccount}
        />

        {/* 暂时隐藏同步设置 */}
        {/* <SyncSettings
          autoSync={autoSync}
          syncInterval={syncInterval}
          onAutoSyncChange={setAutoSync}
          onIntervalChange={setSyncInterval}
        /> */}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8 }}>每次同步条数</label>
          <InputNumber
            min={1}
            max={99999}
            value={syncLimit}
            onChange={handleSyncLimitChange}
            style={{ width: '100%' }}
            placeholder="1-99999"
          />
        </div>

        {/* 同步进度条 */}
        {syncing && syncProgress && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
            <div style={{ marginBottom: 8, fontSize: 14 }}>
              {syncProgress.message || '同步中...'}
            </div>
            <Progress
              percent={syncProgress.total > 0 ? Math.round((syncProgress.current / syncProgress.total) * 100) : 0}
              status={syncProgress.status === 'failed' ? 'exception' : 'active'}
              format={() => `${syncProgress.current} / ${syncProgress.total || '?'}`}
            />
          </div>
        )}

        <Space style={{ width: '100%', marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSyncAll}
            loading={syncing}
            block
          >
            立即同步全部
          </Button>
          <Button
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
            block
          >
            添加邮箱账户
          </Button>
        </Space>

        <SyncLogs logs={syncLogs} loading={loading} />

        <AddAccountModal
          visible={modalVisible}
          providers={providers}
          loading={loading}
          onSubmit={handleAddAccount}
          onCancel={() => setModalVisible(false)}
        />
      </div>
    </ConfigProvider>
  )
}

export default App
