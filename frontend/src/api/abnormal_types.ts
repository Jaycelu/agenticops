/**
 * 异常类型管理API
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface AbnormalType {
  id: number
  type_code: string
  type_name: string
  description: string
  status: 'DRAFT' | 'OBSERVED' | 'ENABLED'
  fingerprint_pattern?: string
  keywords: string[]
  threshold_config: Record<string, any>
  risk_level: 'low' | 'medium' | 'high'
  enable_tracking: boolean
  tracking_config?: Record<string, any>
  occurrence_count: number
  last_occurred_at?: string
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
}

export interface AbnormalTypeStats {
  total: number
  by_status: {
    draft: number
    observed: number
    enabled: number
  }
  top_occurrences: Array<{
    type_code: string
    type_name: string
    occurrence_count: number
    last_occurred_at?: string
  }>
}

export const abnormalTypesApi = {
  // 获取异常类型列表
  getAbnormalTypes: async (params?: { status?: string; skip?: number; limit?: number }) => {
    const response = await axios.get<{ total: number; types: AbnormalType[] }>(
      `${API_BASE_URL}/api/abnormal-types/`,
      { params }
    )
    return response.data
  },

  // 获取异常类型详情
  getAbnormalType: async (typeId: number) => {
    const response = await axios.get<AbnormalType>(
      `${API_BASE_URL}/api/abnormal-types/${typeId}`
    )
    return response.data
  },

  // 创建异常类型
  createAbnormalType: async (typeData: Partial<AbnormalType>) => {
    const response = await axios.post<{ success: boolean; message: string; type: AbnormalType }>(
      `${API_BASE_URL}/api/abnormal-types/`,
      typeData
    )
    return response.data
  },

  // 更新异常类型
  updateAbnormalType: async (typeId: number, typeData: Partial<AbnormalType>) => {
    const response = await axios.put<{ success: boolean; message: string; type: AbnormalType }>(
      `${API_BASE_URL}/api/abnormal-types/${typeId}`,
      typeData
    )
    return response.data
  },

  // 更新异常类型状态
  updateAbnormalTypeStatus: async (typeId: number, status: string) => {
    const response = await axios.patch<{ success: boolean; message: string; type: AbnormalType }>(
      `${API_BASE_URL}/api/abnormal-types/${typeId}/status`,
      { status }
    )
    return response.data
  },

  // 删除异常类型
  deleteAbnormalType: async (typeId: number) => {
    const response = await axios.delete<{ success: boolean; message: string }>(
      `${API_BASE_URL}/api/abnormal-types/${typeId}`
    )
    return response.data
  },

  // 批量更新阈值
  batchUpdateThresholds: async (updates: Array<{ type_code: string; threshold_config: Record<string, any> }>) => {
    const response = await axios.post<{ success: boolean; message: string; updated_count: number }>(
      `${API_BASE_URL}/api/abnormal-types/batch-update-thresholds`,
      { updates }
    )
    return response.data
  },

  // 获取统计信息
  getAbnormalTypesStats: async () => {
    const response = await axios.get<AbnormalTypeStats>(
      `${API_BASE_URL}/api/abnormal-types/stats/summary`
    )
    return response.data
  }
}
