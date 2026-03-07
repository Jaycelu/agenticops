import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildUrl(path: string): string {
  return API_BASE_URL.startsWith('http') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}${path.replace('/api', '')}`
}

export interface CaseSummary {
  id: number
  case_code: string
  title: string
  summary?: string
  source_event_id?: number
  site_id?: number
  netbox_device_id?: number
  device_ip?: string
  host?: string
  priority: string
  risk_level: string
  status: string
  current_phase: string
  opened_at?: string
  last_activity_at?: string
}

export interface CaseOverview {
  total_cases: number
  open_cases: number
  executing_cases: number
  resolved_cases: number
  high_risk_cases: number
  by_phase: Record<string, number>
}

export const casesApi = {
  async getOverview(): Promise<CaseOverview> {
    const response = await axios.get(buildUrl('/api/cases/overview'))
    return response.data
  },

  async list(params?: {
    site_id?: number
    status?: string
    current_phase?: string
    skip?: number
    limit?: number
  }): Promise<{ total: number; items: CaseSummary[] }> {
    const response = await axios.get(buildUrl('/api/cases'), { params })
    return response.data
  },

  async get(caseId: number) {
    const response = await axios.get(buildUrl(`/api/cases/${caseId}`))
    return response.data
  },

  async getEvidence(caseId: number) {
    const response = await axios.get(buildUrl(`/api/cases/${caseId}/evidence`))
    return response.data
  },

  async getAgents(caseId: number) {
    const response = await axios.get(buildUrl(`/api/cases/${caseId}/agents`))
    return response.data
  },

  async getPlans(caseId: number) {
    const response = await axios.get(buildUrl(`/api/cases/${caseId}/plans`))
    return response.data
  }
}
