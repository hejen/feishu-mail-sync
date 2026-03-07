import React from 'react'
import { Card, Statistic, Row, Col } from 'antd'
import { MailOutlined, ClockCircleOutlined } from '@ant-design/icons'
import type { SyncStatus } from '../types'

interface Props {
  status: SyncStatus | null
  loading: boolean
}

export const StatusPanel: React.FC<Props> = ({ status, loading }) => {
  return (
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={16}>
        <Col span={12}>
          <Statistic
            title="已连接邮箱"
            value={status?.accounts?.length || 0}
            prefix={<MailOutlined />}
            loading={loading}
          />
        </Col>
        <Col span={12}>
          <Statistic
            title="已同步邮件"
            value={status?.total_emails || 0}
            prefix={<ClockCircleOutlined />}
            loading={loading}
          />
        </Col>
      </Row>
      {status?.last_sync_time && (
        <div style={{ marginTop: 8, color: '#888', fontSize: 12 }}>
          上次同步: {new Date(status.last_sync_time).toLocaleString('zh-CN')}
        </div>
      )}
    </Card>
  )
}
