import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface BaseConfig {
  key: string
  name: string
  filter: string
  time_range: string
}

export interface BaseConfigsResponse {
  bases: BaseConfig[]
}

export interface LogEntry {
  timestamp: string
  hostname: string
  message: string
  level: string
  raw: any
}

export interface LogsResponse {
  base: string
  base_name_cn: string
  query: string
  time_range: string
  total: number
  logs: LogEntry[]
}

export interface LogQueryParams {
  query?: string
  time_range?: string
  limit?: number
  offset?: number
}

export interface AggregationParams {
  base_name: string
  time_range?: string
  filter?: string
  aggregation: {
    by_device: boolean
    by_level: boolean
    by_time_window: string
  }
}

export interface LevelGroup {
  level: string
  count: number
  time_range: string
  logs: LogEntry[]
}

export interface AggregatedGroup {
  device: string
  total_count: number
  level_groups: LevelGroup[]
}

export interface AggregationResponse {
  success: boolean
  total_logs: number
  total_available?: number
  aggregated_groups: AggregatedGroup[]
  has_more?: boolean
}

export interface AggregatedGroup {
  device: string
  total_count: number
  level_groups: LevelGroup[]
}

export interface LevelGroup {
  level: string
  count: number
  time_range: string
  logs: LogEntry[]
}

export interface AggregationParams {
  base_name: string
  time_range?: string
  filter?: string
  aggregation: {
    by_device: boolean
    by_level: boolean
    by_time_window?: string
  }
}

export interface DeviceLogAnalysisRequest {
  base_name: string
  base_name_cn?: string
  device: string
  logs: LogEntry[]
}

export interface DeviceLogAnalysisResponse {
  success: boolean
  result?: string
  device: string
  log_count: number
  error?: string
}

export const logsApi = {
  async getBases(): Promise<BaseConfigsResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/bases` : `${API_BASE_URL}/logs/bases`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async queryLogs(params?: LogQueryParams): Promise<LogsResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/query` : `${API_BASE_URL}/logs/query`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async queryLogsByBase(
    baseName: string,
    params?: LogQueryParams
  ): Promise<LogsResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/base/${baseName}` : `${API_BASE_URL}/logs/base/${baseName}`
    const response = await axios.get(
      apiUrl,
      { params }
    )
    return response.data
  },

  async queryDeyangLogs(params?: LogQueryParams): Promise<LogsResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/deyang` : `${API_BASE_URL}/logs/deyang`
    const response = await axios.get(
      apiUrl,
      { params }
    )
    return response.data
  },

  async clearCache(): Promise<{ message: string }> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/clear-cache` : `${API_BASE_URL}/logs/clear-cache`
    const response = await axios.post(apiUrl)
    return response.data
  },

  async aggregateLogs(params: AggregationParams): Promise<AggregationResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/aggregate` : `${API_BASE_URL}/logs/aggregate`
    const response = await axios.post(apiUrl, params)
    return response.data
  },

  async analyzeDeviceLogs(params: DeviceLogAnalysisRequest): Promise<DeviceLogAnalysisResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/analyze-device` : `${API_BASE_URL}/logs/analyze-device`
    const response = await axios.post(apiUrl, params)
    return response.data
  },

  async analyzeSingleLog(log: LogEntry): Promise<{ success: boolean; analysis: string; log_count: number; device_info?: { hostname: string; device_ip: string } }> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/logs/analyze-single` : `${API_BASE_URL}/logs/analyze-single`
    const response = await axios.post(apiUrl, { 
      message: log.message,
      hostname: log.hostname
    })
    return response.data
  }
}