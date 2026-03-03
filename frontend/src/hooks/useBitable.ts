import { useState, useEffect, useCallback } from 'react'
import { bitable, FieldType, type ITable, type IField } from '@lark-base-open/js-sdk'
import type { Email } from '../types'

// 字段映射配置
const FIELD_MAPPING = {
  subject: { name: '邮件标题', type: FieldType.Text },
  sender: { name: '发件人', type: FieldType.Text },
  receiver: { name: '收件人', type: FieldType.Text },
  date: { name: '发件时间', type: FieldType.DateTime },
  body: { name: '邮件内容', type: FieldType.Text },
  message_id: { name: '邮件ID', type: FieldType.Text },
  attachments: { name: '附件', type: FieldType.Attachment }
}

// 将 base64 字符串转换为 Blob
function base64ToBlob(base64: string, filename: string): Blob {
  const byteCharacters = atob(base64)
  const byteNumbers = new Array(byteCharacters.length)
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i)
  }
  const byteArray = new Uint8Array(byteNumbers)

  // 根据文件扩展名推断 MIME 类型
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const mimeTypes: Record<string, string> = {
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'txt': 'text/plain',
    'zip': 'application/zip'
  }
  const mimeType = mimeTypes[ext] || 'application/octet-stream'

  return new Blob([byteArray], { type: mimeType })
}

// 检测是否在飞书环境中
async function checkFeishuEnv(): Promise<boolean> {
  try {
    // 检查是否在 iframe 中
    if (window === window.top) {
      console.log('[Bitable] 不在 iframe 中，使用模拟模式')
      return false
    }

    // 尝试调用 bitable SDK 来验证是否在飞书环境中
    // bitable 是通过 ES 模块导入的，不是全局变量
    const table = await bitable.base.getActiveTable()
    console.log('[Bitable] 飞书环境检测成功，表格:', table)
    return true
  } catch (err) {
    console.log('[Bitable] 飞书环境检测失败:', err)
    return false
  }
}

// 模拟表格类 - 用于本地开发
class MockTable {
  private records: any[] = []

  async getFieldList(): Promise<any[]> {
    return Object.entries(FIELD_MAPPING).map(([key, { name, type }]) => ({
      id: key,
      name,
      type,
      getName: async () => name
    }))
  }

  async addField(config: any): Promise<string> {
    return config.name
  }

  async getField(id: string): Promise<any> {
    return { id, getName: async () => id }
  }

  async addRecord(record: any): Promise<void> {
    this.records.push(record)
    console.log('[Mock] 模拟写入邮件记录:', record)
  }

  getRecordCount(): number {
    return this.records.length
  }
}

export function useBitable() {
  const [table, setTable] = useState<ITable | MockTable | null>(null)
  const [fields, setFields] = useState<IField[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMockMode, setIsMockMode] = useState(false)

  // 初始化表格
  useEffect(() => {
    async function initTable() {
      // 检测是否在飞书环境中（异步检测）
      const isFeishuEnv = await checkFeishuEnv()

      if (isFeishuEnv) {
        try {
          const activeTable = await bitable.base.getActiveTable()
          setTable(activeTable)
          const fieldList = await activeTable.getFieldList()
          setFields(fieldList)
          setLoading(false)
          console.log('[Bitable] 飞书环境初始化成功')
        } catch (err) {
          setError(err instanceof Error ? err.message : '初始化表格失败')
          setLoading(false)
          console.error('[Bitable] 飞书环境初始化失败:', err)
        }
      } else {
        // 本地开发模式 - 使用模拟表格
        console.log('[Mock] 本地开发模式：使用模拟 Bitable')
        const mockTable = new MockTable()
        setTable(mockTable as unknown as ITable)
        setIsMockMode(true)
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

    for (const [key, { name, type }] of Object.entries(FIELD_MAPPING)) {
      // 需要异步获取字段名称
      let foundField: IField | undefined
      for (const field of existingFields) {
        const fieldName = await field.getName()
        if (fieldName === name) {
          foundField = field
          break
        }
      }

      if (foundField) {
        fieldMap[key] = foundField
      } else {
        // 创建新字段 - 使用类型断言避免复杂的类型推断问题
        const newFieldId = await table.addField({
          name,
          type,
        } as any)
        // 获取新创建的字段
        const newField = await table.getField(newFieldId)
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
          // 处理附件上传
          let attachmentTokens: { file_token: string }[] = []

          if (email.attachments && email.attachments.length > 0 && !isMockMode) {
            try {
              // 将所有附件转换为 File 对象
              const files: File[] = email.attachments.map(attachment => {
                const blob = base64ToBlob(attachment.content, attachment.filename)
                return new File([blob], attachment.filename, { type: blob.type })
              })

              // 使用飞书 SDK 批量上传附件
              const fileTokens = await bitable.base.batchUploadFile(files)

              // 将 file_token 转换为附件字段需要的格式
              attachmentTokens = fileTokens.map(token => ({ file_token: token }))
            } catch (uploadErr) {
              console.error('上传附件失败:', uploadErr)
              // 继续处理，不中断流程
            }
          }

          // 将 ISO 日期字符串转换为毫秒时间戳（飞书 DateTime 字段要求）
          const dateTimestamp = email.date ? new Date(email.date).getTime() : null

          await table.addRecord({
            fields: {
              [fieldMap['subject'].id]: email.subject,
              [fieldMap['sender'].id]: email.sender,
              [fieldMap['receiver'].id]: email.receiver,
              [fieldMap['date'].id]: dateTimestamp,
              [fieldMap['body'].id]: email.body,
              [fieldMap['message_id'].id]: email.message_id,
              [fieldMap['attachments'].id]: attachmentTokens
            }
          })
          successCount++
        } catch (err) {
          console.error('写入邮件失败:', err)
        }
      }

      // 如果是模拟模式，在结果中标注
      if (isMockMode) {
        return {
          success: true,
          count: successCount,
          total: emails.length,
          isMockMode: true,
          message: '(本地模拟模式)'
        }
      }

      return { success: true, count: successCount, total: emails.length }
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : '写入失败'
      }
    }
  }, [table, ensureFields, isMockMode])

  return {
    table,
    fields,
    loading,
    error,
    ensureFields,
    writeEmails,
    isMockMode
  }
}
