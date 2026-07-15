import axios from 'axios'
import { configureAxios } from '@/api/http'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function buildUrl(path: string): string {
  return API_BASE_URL.startsWith('http') ? path : path.replace('/api', '')
}

const api = configureAxios(axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
}))

export const listSSHCredentials = async () => {
  const response = await api.get(buildUrl('/api/ssh/credentials'))
  return response.data
}

export const createSSHCredential = async (payload: any) => {
  const response = await api.post(buildUrl('/api/ssh/credentials'), payload)
  return response.data
}

export const updateSSHCredential = async (id: number, payload: any) => {
  const response = await api.put(buildUrl(`/api/ssh/credentials/${id}`), payload)
  return response.data
}

export const deleteSSHCredential = async (id: number) => {
  const response = await api.delete(buildUrl(`/api/ssh/credentials/${id}`))
  return response.data
}

export const queryNetBoxDevices = async (params?: {
  site?: string
  tag?: string
  name?: string
  role?: string
  vendor?: string
  device_type?: string
}) => {
  const response = await api.get(buildUrl('/api/ssh/netbox/devices'), { params })
  return response.data
}

export const bindCredentialDevices = async (credentialId: number, netboxDeviceIds: number[]) => {
  const response = await api.post(buildUrl(`/api/ssh/credentials/${credentialId}/bind-devices`), {
    netbox_device_ids: netboxDeviceIds
  })
  return response.data
}

export const listCredentialBindings = async (credentialId: number) => {
  const response = await api.get(buildUrl(`/api/ssh/credentials/${credentialId}/bindings`))
  return response.data
}

export const testSSHConnectivity = async (payload: { credential_id: number; netbox_device_id: number }) => {
  const response = await api.post(buildUrl('/api/ssh/connectivity-test'), payload)
  return response.data
}
