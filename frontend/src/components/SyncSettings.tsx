import React from 'react'
import { Card, Switch, Select, Space } from 'antd'

interface Props {
  autoSync: boolean
  syncInterval: number
  onAutoSyncChange: (checked: boolean) => void
  onIntervalChange: (minutes: number) => void
}

export const SyncSettings: React.FC<Props> = ({
  autoSync,
  syncInterval,
  onAutoSyncChange,
  onIntervalChange
}) => {
  return (
    <Card title="⚙️ 同步设置" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>自动同步</span>
          <Switch checked={autoSync} onChange={onAutoSyncChange} />
        </div>
        {autoSync && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>同步间隔</span>
            <Select
              value={syncInterval}
              onChange={onIntervalChange}
              style={{ width: 120 }}
              options={[
                { value: 15, label: '15 分钟' },
                { value: 30, label: '30 分钟' },
                { value: 60, label: '60 分钟' }
              ]}
            />
          </div>
        )}
      </Space>
    </Card>
  )
}
