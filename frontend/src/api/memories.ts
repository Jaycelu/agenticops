import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function buildUrl(path: string): string {
  return API_BASE_URL.startsWith('http') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}${path.replace('/api', '')}`
}

export const memoriesApi = {
  async getOverview() {
    const response = await axios.get(buildUrl('/api/memories/overview'))
    return response.data
  },

  async list(params?: { memory_type?: string; case_id?: number; skip?: number; limit?: number }) {
    const response = await axios.get(buildUrl('/api/memories'), { params })
    return response.data
  }
}
