import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildUrl(path: string): string {
  return API_BASE_URL.startsWith('http') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}${path.replace('/api', '')}`
}

export const fabricApi = {
  async getOverview() {
    const response = await axios.get(buildUrl('/api/fabric/overview'))
    return response.data
  },

  async listPlans(params?: { case_id?: number; status?: string; skip?: number; limit?: number }) {
    const response = await axios.get(buildUrl('/api/fabric/plans'), { params })
    return response.data
  },

  async listExecutions(params?: {
    case_id?: number
    remediation_plan_id?: number
    status?: string
    skip?: number
    limit?: number
  }) {
    const response = await axios.get(buildUrl('/api/fabric/executions'), { params })
    return response.data
  }
}
