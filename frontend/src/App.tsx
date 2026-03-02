import React from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <div style={{ padding: '16px' }}>
        <h1>邮箱同步助手</h1>
        <p>正在加载...</p>
      </div>
    </ConfigProvider>
  )
}

export default App
