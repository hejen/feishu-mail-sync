import React from 'react'
import { Card, List, Button, Tag, Space } from 'antd'
import { DeleteOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { Account } from '../types'

interface Props {
  accounts: Account[]
  loading: boolean
  syncing: boolean
  onSync: (id: number) => void
  onDelete: (id: number) => void
}

export const AccountList: React.FC<Props> = ({
  accounts,
  loading,
  syncing,
  onSync,
  onDelete
}) => {
  const getProviderName = (provider: string) => {
    const names: Record<string, string> = {
      qq: 'QQ邮箱',
      '163': '163邮箱',
      '126': '126邮箱',
      feishu: '飞书邮箱'
    }
    return names[provider] || provider
  }

  return (
    <Card
      title="📧 邮箱账户"
      style={{ marginBottom: 16 }}
      loading={loading}
    >
      <List
        dataSource={accounts}
        renderItem={(account) => (
          <List.Item
            actions={[
              <Button
                key="sync"
                type="link"
                icon={<SyncOutlined spin={syncing} />}
                onClick={() => onSync(account.id)}
                disabled={syncing}
              >
                同步
              </Button>,
              <Button
                key="delete"
                type="link"
                danger
                icon={<DeleteOutlined />}
                onClick={() => onDelete(account.id)}
              >
                删除
              </Button>
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  {account.email}
                  <Tag color="blue">{getProviderName(account.provider)}</Tag>
                </Space>
              }
              description={
                <Space>
                  {account.is_active ? (
                    <><CheckCircleOutlined style={{ color: '#52c41a' }} /> 已连接</>
                  ) : (
                    <><CloseCircleOutlined style={{ color: '#ff4d4f' }} /> 已禁用</>
                  )}
                  {account.last_sync_time && (
                    <span>上次同步: {new Date(account.last_sync_time).toLocaleString('zh-CN')}</span>
                  )}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  )
}
