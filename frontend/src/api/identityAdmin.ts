import axios from '@/api/http'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const base = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/admin/identity` : `${API_BASE_URL}/admin/identity`

export interface IdentityProviderView {
  id: number
  provider_key: string
  provider_type: string
  display_name: string
  enabled: boolean
  config: Record<string, unknown>
  secret_status: Record<string, boolean>
  group_role_mapping: Record<string, string[]>
}

export interface UserView {
  id: number
  username: string
  display_name: string
  email?: string
  active: boolean
  is_emergency: boolean
  roles: Array<{ role: string; source: string; provider_id?: number }>
}

export const identityAdminApi = {
  async providers() {
    return (await axios.get<{ items: IdentityProviderView[] }>(`${base}/providers`)).data.items
  },
  async saveProvider(providerKey: string, payload: Record<string, unknown>) {
    return (await axios.put<IdentityProviderView>(`${base}/providers/${providerKey}`, payload)).data
  },
  async users() {
    return (await axios.get<{ items: UserView[] }>(`${base}/users`)).data.items
  },
  async saveUser(userId: number, payload: Record<string, unknown>) {
    return (await axios.put<UserView>(`${base}/users/${userId}`, payload)).data
  }
}
