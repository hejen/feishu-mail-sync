import React from 'react'
import { Card, List, Empty } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { SyncLog } from '../types'

interface Props {
  logs: SyncLog[]
  loading: boolean
}

export const SyncLogs: React.FC<Props> = ({ logs, loading }) => {
  return (
    <Card title="📋 同步日志">
      {logs.length === 0 ? (
        <Empty description="暂无同步记录" />
      ) : (
        <List
          loading={loading}
          dataSource={logs}
          renderItem={(log) => (
            <List.Item>
              <List.Item.Meta
                avatar={
                  log.status === 'success' ? (
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                  ) : (
                    <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 20 }} />
                  )
                }
                title={`${new Date(log.sync_time).toLocaleString('zh-CN')} 同步${log.status === 'success' ? '完成' : '失败'}`}
                description={
                  log.status === 'success'
                    ? `新增 ${log.emails_count} 封邮件`
                    : log.error_message
                }
              />
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
