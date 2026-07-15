import { defineStore } from 'pinia'
import axios from '@/api/http'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

function authUrl(path: string): string {
  return API_BASE_URL.startsWith('http')
    ? `${API_BASE_URL}/api/auth${path}`
    : `${API_BASE_URL}/auth${path}`
}

export interface AuthUser {
  id: number
  username: string
  display_name: string
  roles: string[]
  permissions: string[]
}

export interface AuthProvider {
  key: string
  type: 'local' | 'ldap' | 'oidc' | 'saml'
  display_name: string
  flow: 'credentials' | 'redirect'
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    providers: [] as AuthProvider[],
    initialized: false,
    loading: false
  }),
  getters: {
    authenticated: (state) => state.user !== null
  },
  actions: {
    async loadProviders() {
      const response = await axios.get<{ items: AuthProvider[] }>(authUrl('/providers'))
      this.providers = response.data.items
    },
    async initialize(force = false) {
      if (this.initialized && !force) return this.authenticated
      try {
        const response = await axios.get<{ user: AuthUser }>(authUrl('/me'))
        this.user = response.data.user
      } catch {
        this.user = null
      } finally {
        this.initialized = true
      }
      return this.authenticated
    },
    async login(providerKey: string, username: string, password: string) {
      this.loading = true
      try {
        const response = await axios.post<{ user: AuthUser }>(authUrl(`/login/${providerKey}`), {
          username,
          password
        })
        this.user = response.data.user
        this.initialized = true
      } finally {
        this.loading = false
      }
    },
    startRedirect(providerKey: string) {
      window.location.assign(authUrl(`/login/${providerKey}/start`))
    },
    async logout() {
      try {
        await axios.post(authUrl('/logout'))
      } finally {
        this.user = null
        this.initialized = true
      }
    },
    clear() {
      this.user = null
      this.initialized = true
    }
  }
})
