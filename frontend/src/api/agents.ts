import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildUrl(path: string): string {
  return API_BASE_URL.startsWith('http') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}${path.replace('/api', '')}`
}

export const agentsApi = {
  async getCatalog() {
    const response = await axios.get(buildUrl('/api/agents/catalog'))
    return response.data
  },

  async getHealth() {
    const response = await axios.get(buildUrl('/api/agents/health'))
    return response.data
  },

  async listRuns(params?: { case_id?: number; agent_type?: string; status?: string; skip?: number; limit?: number }) {
    const response = await axios.get(buildUrl('/api/agents/runs'), { params })
    return response.data
  }
}
