import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface Alert {
  eventid: string
  name: string
  severity: string
  severity_level: number
  host: string
  clock: string
  acknowledged: number
  status: string
}

export interface Problem {
  eventid: string
  name: string
  severity: string
  severity_level: number
  host: string
  clock: string
  r_clock: string
  acknowledged: number
  status: string
}

export interface Host {
  hostid: string
  host: string
  name: string
  ip: string
  status: string
  groups: string[]
}

export interface Trigger {
  triggerid: string
  description: string
  severity: string
  severity_level: number
  host: string
  status: string
  value: string
}

export interface AlertListResponse {
  count: number
  alerts: Alert[]
}

export interface ProblemListResponse {
  count: number
  problems: Problem[]
}

export interface HostListResponse {
  count: number
  hosts: Host[]
}

export interface TriggerListResponse {
  count: number
  triggers: Trigger[]
}

export interface AlertStatistics {
  total_alerts: number
  acknowledged: number
  unacknowledged: number
  severity_stats: Record<string, number>
  total_hosts: number
  enabled_hosts: number
  disabled_hosts: number
}

export interface AlertEvent {
  id: number
  source: string
  external_event_id?: string
  dedup_key: string
  site_id?: number
  netbox_device_id?: number
  host?: string
  name: string
  severity: string
  severity_level: number
  status: string
  acknowledged: boolean
  occurred_at?: string
  resolved_at?: string
  last_seen_at?: string
  payload: Record<string, any>
}

export const alertsApi = {
  async getAlerts(params?: {
    severity?: number
    host?: string
    time_from?: number
    time_till?: number
    acknowledged?: number
    limit?: number
  }): Promise<AlertListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/alerts` : `${API_BASE_URL}/alerts/alerts`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getProblems(params?: {
    severity?: number
    host?: string
    recent?: string
    limit?: number
  }): Promise<ProblemListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/problems` : `${API_BASE_URL}/alerts/problems`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getHosts(params?: {
    search?: string
    limit?: number
  }): Promise<HostListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/hosts` : `${API_BASE_URL}/alerts/hosts`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getTriggers(params?: {
    severity?: number
    host?: string
    limit?: number
  }): Promise<TriggerListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/triggers` : `${API_BASE_URL}/alerts/triggers`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getStatistics(): Promise<AlertStatistics> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/statistics` : `${API_BASE_URL}/alerts/statistics`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async acknowledgeAlerts(
    eventIds: string[],
    message: string = "已通过NetOps平台确认"
  ): Promise<{ count: number; event_ids: string[]; message: string }> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/acknowledge` : `${API_BASE_URL}/alerts/acknowledge`
    const response = await axios.post(apiUrl, {
      event_ids: eventIds,
      message: message
    })
    return response.data
  },

  async clearCache(): Promise<{ message: string }> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/clear-cache` : `${API_BASE_URL}/alerts/clear-cache`
    const response = await axios.post(apiUrl)
    return response.data
  },

  async getAlertEvents(params?: {
    status?: string
    severity?: string
    source?: string
    site_id?: number
    netbox_device_id?: number
    skip?: number
    limit?: number
  }): Promise<{ page: { total: number; skip: number; limit: number; returned: number; has_more: boolean }; events: AlertEvent[] }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/events` : `${API_BASE_URL}/alerts/events`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async createAlertEvent(payload: {
    source?: string
    external_event_id?: string
    site_id?: number
    netbox_device_id?: number
    host?: string
    name: string
    severity?: string
    severity_level?: number
    occurred_at?: string
    payload?: Record<string, any>
    dedup_key?: string
  }): Promise<AlertEvent> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/events` : `${API_BASE_URL}/alerts/events`
    const response = await axios.post(apiUrl, payload)
    return response.data
  },

  async acknowledgeAlertEvent(eventId: number): Promise<AlertEvent> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/events/${eventId}/acknowledge` : `${API_BASE_URL}/alerts/events/${eventId}/acknowledge`
    const response = await axios.post(apiUrl)
    return response.data
  },

  async resolveAlertEvent(eventId: number): Promise<AlertEvent> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/alerts/events/${eventId}/resolve` : `${API_BASE_URL}/alerts/events/${eventId}/resolve`
    const response = await axios.post(apiUrl)
    return response.data
  }
}
