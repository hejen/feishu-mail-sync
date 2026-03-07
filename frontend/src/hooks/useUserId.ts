import { useState, useEffect } from 'react'
import { bitable } from '@lark-base-open/js-sdk'

export interface UseUserIdResult {
  userId: string | null
  loading: boolean
  error: string | null
}

/**
 * 获取当前用户ID的 Hook
 * 
 * 在飞书环境中通过 SDK 获取真实用户ID，
 * 本地开发模式下使用模拟用户ID。
 */
export function useUserId(): UseUserIdResult {
  const [userId, setUserId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchUserId() {
      try {
        // 检测是否在飞书环境（iframe 中）
        if (window === window.top) {
          // 本地开发模式
          setUserId('mock-user-001')
          setLoading(false)
          return
        }

        // 尝试从飞书 SDK 获取用户ID
        const id = await bitable.bridge.getUserId()
        setUserId(id)
        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : '获取用户ID失败')
        setLoading(false)
      }
    }
    
    fetchUserId()
  }, [])

  return { userId, loading, error }
}
