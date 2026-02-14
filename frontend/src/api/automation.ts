/**
 * 自动化中心API客户端
 */
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// ============ 基地管理 ============

export const getSites = async (params?: { skip?: number; limit?: number }) => {
  const response = await api.get('/api/automation/sites', { params })
  return response.data
}

export const getSite = async (siteId: number) => {
  const response = await api.get(`/api/automation/sites/${siteId}`)
  return response.data
}

export const updateSiteAutomationToggle = async (siteId: number, enabled: boolean) => {
  const response = await api.put(`/api/automation/sites/${siteId}/automation-toggle`, null, {
    params: { enabled }
  })
  return response.data
}

// ============ 日志采样 ============

export const getLogSamples = async (params?: {
  site_id?: number
  is_abnormal?: boolean
  start_date?: string
  end_date?: string
  skip?: number
  limit?: number
}) => {
  const response = await api.get('/api/automation/samples', { params })
  return response.data
}

export const getLogSample = async (sampleId: number) => {
  const response = await api.get(`/api/automation/samples/${sampleId}`)
  return response.data
}

// ============ 分析结果 ============

export const getAnalysisResults = async (params?: {
  site_id?: number
  severity?: string
  status?: string
  start_date?: string
  end_date?: string
  skip?: number
  limit?: number
}) => {
  const response = await api.get('/api/automation/analysis-results', { params })
  return response.data
}

export const getAnalysisResult = async (resultId: number) => {
  const response = await api.get(`/api/automation/analysis-results/${resultId}`)
  return response.data
}

// ============ 自动化任务 ============

export const getAutomationTasks = async (params?: {
  site_id?: number
  status?: string
  start_date?: string
  end_date?: string
  skip?: number
  limit?: number
}) => {
  const response = await api.get('/api/automation/tasks', { params })
  return response.data
}

export const getAutomationTask = async (taskId: number) => {
  const response = await api.get(`/api/automation/tasks/${taskId}`)
  return response.data
}

export const getTaskFeedback = async (taskId: number) => {
  const response = await api.get(`/api/automation/tasks/${taskId}/feedback`)
  return response.data
}

export const submitTaskFeedback = async (
  taskId: number,
  payload: {
    verdict: 'correct' | 'incorrect' | 'partial'
    comment?: string
    reviewer?: string
    tags?: string[]
  }
) => {
  const response = await api.post(`/api/automation/tasks/${taskId}/feedback`, payload)
  return response.data
}

export const dispatchTaskConfig = async (taskId: number) => {
  const response = await api.post(`/api/automation/tasks/${taskId}/dispatch-config`)
  return response.data
}

export const getFeedbackStats = async (params?: {
  diagnosis_type?: string
  site_id?: number
  window_days?: number
  min_samples?: number
  start_date?: string
  end_date?: string
}) => {
  const response = await api.get('/api/automation/feedback/stats', { params })
  return response.data
}

export const getFeedbackTrends = async (params?: {
  diagnosis_type?: string
  site_id?: number
  window_days?: number
  start_date?: string
  end_date?: string
}) => {
  const response = await api.get('/api/automation/feedback/trends', { params })
  return response.data
}

export const getFeedbackInsights = async (params?: {
  site_id?: number
  window_days?: number
  min_samples?: number
  top_n?: number
  start_date?: string
  end_date?: string
}) => {
  const response = await api.get('/api/automation/feedback/insights', { params })
  return response.data
}

// ============ 策略管理 ============

export const getAutomationPolicies = async (params?: {
  site_id?: number
  enabled?: boolean
  skip?: number
  limit?: number
}) => {
  const response = await api.get('/api/automation/policies', { params })
  return response.data
}

export const getAutomationPolicy = async (policyId: number) => {
  const response = await api.get(`/api/automation/policies/${policyId}`)
  return response.data
}

// ============ Dashboard统计 ============

export const getDashboardSummary = async (params?: { 
  site_id?: number
  start_date?: string
  end_date?: string
}) => {
  const response = await api.get('/api/automation/dashboard/summary', { params })
  return response.data
}

export const getDashboardTrends = async (params?: {
  site_id?: number
  days?: number
}) => {
  const response = await api.get('/api/automation/dashboard/trends', { params })
  return response.data
}

export const getDashboardHourlyTrends = async (params?: {
  site_id?: number
  date?: string
}) => {
  const response = await api.get('/api/automation/dashboard/hourly-trends', { params })
  return response.data
}

// ============ 手动触发 ============

export const triggerDiagnosis = async (sampleId: number) => {
  const response = await api.post('/api/automation/trigger-diagnosis', { sample_id: sampleId })
  return response.data
}

export const triggerAlerts = async (params?: { site_id?: number }) => {
  const response = await api.post('/api/automation/trigger-alerts', params)
  return response.data
}

export const resolveVendorCommands = async (params: { device_id: number; template_type?: string }) => {
  const response = await api.get('/api/automation/resolve-commands', { params })
  return response.data
}

export default api
