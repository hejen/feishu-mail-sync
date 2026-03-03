import { useState, useEffect, useCallback } from 'react'
import { ConfigProvider, Button, message, Space, InputNumber } from 'antd'
import { PlusOutlined, SyncOutlined } from '@ant-design/icons'
import zhCN from 'antd/locale/zh_CN'

import { StatusPanel } from './components/StatusPanel'
import { AccountList } from './components/AccountList'
import { SyncLogs } from './components/SyncLogs'
import { AddAccountModal } from './components/AddAccountModal'
import { useBitable } from './hooks/useBitable'
import * as api from './services/api'
import type { Account, SyncStatus, SyncLog, Provider } from './types'

function App() {
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

  const { writeEmails } = useBitable()

  // 加载数据
  const loadData = useCallback(async () => {
    try {
      const [accountsRes, statusRes, logsRes, providersRes] = await Promise.all([
        api.getAccounts(),
        api.getSyncStatus(),
        api.getSyncLogs(),
        api.getProviders()
      ])
      setAccounts(accountsRes.data)
      setSyncStatus(statusRes.data)
      setSyncLogs(logsRes.data.slice(0, 10))
      setProviders(providersRes.data)
    } catch (err) {
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // 同步所有账户
  const handleSyncAll = async () => {
    if (syncing) return

    setSyncing(true)
    try {
      const res = await api.manualSync(syncLimit)
      message.success(res.data.message)

      // 获取同步的邮件并写入多维表格
      const emailsRes = await api.getSyncedEmails()
      if (emailsRes.data.length > 0) {
        const result = await writeEmails(emailsRes.data)
        if (result.success) {
          const mockHint = (result as any).isMockMode ? ' (本地模拟模式)' : ''
          message.success(`已写入 ${result.count} 封邮件到多维表格${mockHint}`)
        } else {
          message.error(result.message || '写入多维表格失败')
        }
      }

      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '同步失败')
    } finally {
      setSyncing(false)
    }
  }

  // 同步单个账户
  const handleSyncAccount = async (id: number) => {
    if (syncing) return

    setSyncing(true)
    try {
      const res = await api.manualSyncAccount(id, syncLimit)
      message.success(res.data.message)

      // 获取同步的邮件并写入多维表格
      const emailsRes = await api.getSyncedEmails()
      if (emailsRes.data.length > 0) {
        const result = await writeEmails(emailsRes.data)
        if (result.success) {
          const mockHint = (result as any).isMockMode ? ' (本地模拟模式)' : ''
          message.success(`已写入 ${result.count} 封邮件到多维表格${mockHint}`)
        } else {
          message.error(result.message || '写入多维表格失败')
        }
      }

      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '同步失败')
    } finally {
      setSyncing(false)
    }
  }

  // 删除账户
  const handleDeleteAccount = async (id: number) => {
    try {
      await api.deleteAccount(id)
      message.success('删除成功')
      loadData()
    } catch (err) {
      message.error('删除失败')
    }
  }

  // 添加账户
  const handleAddAccount = async (data: { email: string; auth_code: string; provider: string }) => {
    try {
      await api.createAccount(data)
      message.success('添加成功')
      setModalVisible(false)
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '添加失败')
    }
  }

  // 处理同步条数变更
  const handleSyncLimitChange = (value: number | null) => {
    const limit = Math.max(1, Math.min(99999, value || 100))
    setSyncLimit(limit)
    localStorage.setItem('syncLimit', String(limit))
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
