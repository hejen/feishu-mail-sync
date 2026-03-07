import React, { useState, useEffect } from 'react'
import { Modal, Form, Input, Select, Alert } from 'antd'
import type { Provider } from '../types'

interface Props {
  visible: boolean
  providers: Provider[]
  loading: boolean
  onSubmit: (data: { email: string; auth_code: string; provider: string }) => void
  onCancel: () => void
}

export const AddAccountModal: React.FC<Props> = ({
  visible,
  providers,
  loading,
  onSubmit,
  onCancel
}) => {
  const [form] = Form.useForm()
  const [selectedProvider, setSelectedProvider] = useState<string>('qq')

  useEffect(() => {
    if (providers && providers.length > 0) {
      setSelectedProvider(providers[0].value)
    }
  }, [providers])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit(values)
  }

  const selectedProviderConfig = (providers && Array.isArray(providers)) 
    ? providers.find(p => p.value === selectedProvider) 
    : undefined

  return (
    <Modal
      title="添加邮箱账户"
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      okText="确认添加"
      cancelText="取消"
    >
      <Form form={form} layout="vertical" initialValues={{ provider: 'qq' }}>
        <Form.Item
          name="provider"
          label="邮箱提供商"
          rules={[{ required: true, message: '请选择邮箱提供商' }]}
        >
          <Select onChange={setSelectedProvider}>
            {providers && Array.isArray(providers) && providers.map(p => (
              <Select.Option key={p.value} value={p.value}>
                {p.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="email"
          label="邮箱地址"
          rules={[
            { required: true, message: '请输入邮箱地址' },
            { type: 'email', message: '请输入有效的邮箱地址' }
          ]}
        >
          <Input placeholder="example@qq.com" />
        </Form.Item>

        <Form.Item
          name="auth_code"
          label="授权码"
          rules={[{ required: true, message: '请输入授权码' }]}
        >
          <Input.Password placeholder="请输入邮箱授权码" />
        </Form.Item>

        {selectedProviderConfig && (
          <Alert
            message="如何获取授权码？"
            description={
              <a href={selectedProviderConfig.help_url} target="_blank" rel="noopener noreferrer">
                点击查看 {selectedProviderConfig.name} 授权码获取指南
              </a>
            }
            type="info"
            showIcon
          />
        )}
      </Form>
    </Modal>
  )
}
