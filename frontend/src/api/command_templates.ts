import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export const listCommandTemplates = async (params?: { vendor?: string; template_type?: string }) => {
  const response = await api.get('/api/command-templates', { params })
  return response.data
}

export const createCommandTemplate = async (payload: any) => {
  const response = await api.post('/api/command-templates', payload)
  return response.data
}

export const updateCommandTemplate = async (id: number, payload: any) => {
  const response = await api.put(`/api/command-templates/${id}`, payload)
  return response.data
}

export const deleteCommandTemplate = async (id: number) => {
  const response = await api.delete(`/api/command-templates/${id}`)
  return response.data
}

export const validateTemplateDeployment = async (templateId: number, deviceIds: number[]) => {
  const response = await api.post('/api/command-templates/validate-deployment', {
    template_id: templateId,
    device_ids: deviceIds,
  })
  return response.data
}
