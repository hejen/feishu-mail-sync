import { useState, useEffect, useCallback } from 'react'
import { bitable, FieldType, type ITable, type IField } from '@lark-base-open/js-sdk'
import type { Email } from '../types'

// 字段映射配置
const FIELD_MAPPING = {
  subject: { name: '邮件标题', type: FieldType.Text },
  sender: { name: '发件人', type: FieldType.Text },
  receiver: { name: '收件人', type: FieldType.Text },
  date: { name: '发件时间', type: FieldType.DateTime },
  body: { name: '邮件内容', type: FieldType.MultiLineText },
  message_id: { name: '邮件ID', type: FieldType.Text }
}

export function useBitable() {
  const [table, setTable] = useState<ITable | null>(null)
  const [fields, setFields] = useState<IField[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 初始化表格
  useEffect(() => {
    async function initTable() {
      try {
        const activeTable = await bitable.base.getActiveTable()
        setTable(activeTable)
        const fieldList = await activeTable.getFieldList()
        setFields(fieldList)
        setLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : '初始化表格失败')
        setLoading(false)
      }
    }
    initTable()
  }, [])

  // 确保字段存在
  const ensureFields = useCallback(async () => {
    if (!table) return {}

    const existingFields = await table.getFieldList()
    const fieldMap: Record<string, IField> = {}

    for (const [key, config] of Object.entries(FIELD_MAPPING)) {
      const existing = existingFields.find(f => f.name === config.name)
      if (existing) {
        fieldMap[key] = existing
      } else {
        // 创建新字段
        const newField = await table.addField({
          name: config.name,
          type: config.type,
          property: {}
        })
        fieldMap[key] = newField
      }
    }

    return fieldMap
  }, [table])

  // 写入邮件到表格
  const writeEmails = useCallback(async (emails: Email[]) => {
    if (!table) {
      return { success: false, message: '表格未初始化' }
    }

    try {
      const fieldMap = await ensureFields()
      let successCount = 0

      for (const email of emails) {
        try {
          await table.addRecord({
            fields: {
              [fieldMap['subject'].id]: email.subject,
              [fieldMap['sender'].id]: email.sender,
              [fieldMap['receiver'].id]: email.receiver,
              [fieldMap['date'].id]: email.date,
              [fieldMap['body'].id]: email.body,
              [fieldMap['message_id'].id]: email.message_id
            }
          })
          successCount++
        } catch (err) {
          console.error('写入邮件失败:', err)
        }
      }

      return { success: true, count: successCount, total: emails.length }
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : '写入失败'
      }
    }
  }, [table, ensureFields])

  return {
    table,
    fields,
    loading,
    error,
    ensureFields,
    writeEmails
  }
}
