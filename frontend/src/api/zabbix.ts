import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface ZabbixAlertItem {
  event_id?: string
  name: string
  severity: string
  severity_level: number
  host?: string
  host_name?: string
  clock?: string | null
  acknowledged: boolean
  object_id?: string
  raw: Record<string, any>
  linked_event?: {
    event_id: number
    source_event_id?: number
    status: string
    severity: string
    disposition?: string
    disposition_reason?: string
    case_id?: number
    case_code?: string
    ticket_id?: string
  } | null
}

export interface ZabbixAlertListResponse {
  success: boolean
  configured: boolean
  host?: string
  limit: number
  total: number
  by_severity: Record<string, number>
  alerts: ZabbixAlertItem[]
  error?: string | null
}

export const zabbixApi = {
  async getStatus(): Promise<{ configured: boolean; source: string; message: string }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/zabbix/status` : `${API_BASE_URL}/zabbix/status`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async listAlerts(params?: { host?: string; limit?: number }): Promise<ZabbixAlertListResponse> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/zabbix/alerts` : `${API_BASE_URL}/zabbix/alerts`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async syncAlerts(params?: { host?: string; limit?: number }): Promise<{ success: boolean; configured: boolean; created: number; updated: number; total: number; error?: string | null }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/zabbix/sync-alerts` : `${API_BASE_URL}/zabbix/sync-alerts`
    const response = await axios.post(apiUrl, null, { params })
    return response.data
  }
}
