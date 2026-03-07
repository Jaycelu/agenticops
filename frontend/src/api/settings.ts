import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface LLMModel {
  id: string
  name: string
  provider: string
  model_name: string
  api_url: string
  api_key: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateModelRequest {
  name: string
  provider: string
  model_name: string
  api_url: string
  api_key: string
}

export interface UpdateModelRequest {
  name?: string
  provider?: string
  model_name?: string
  api_url?: string
  api_key?: string
}

export interface ModelResponse {
  success: boolean
  data?: LLMModel
  error?: string
}

export interface ModelsResponse {
  success: boolean
  data?: LLMModel[]
  error?: string
}

export interface ProvidersResponse {
  success: boolean
  data?: string[]
  error?: string
}

export interface IntegrationConfig {
  integration_type: string
  display_name: string
  enabled: boolean
  config: Record<string, string>
  secret_status: Record<string, boolean>
  updated_at?: string | null
  source: string
}

export interface IntegrationListResponse {
  success: boolean
  data?: IntegrationConfig[]
  error?: string
}

export interface IntegrationResponse {
  success: boolean
  data?: IntegrationConfig
  error?: string
}

export interface IntegrationSaveRequest {
  enabled: boolean
  config: Record<string, string>
  secrets: Record<string, string>
  clear_secrets?: string[]
}

export interface LogScope {
  id: number
  scope_key: string
  display_name: string
  netbox_site_id?: number | null
  site_code_snapshot?: string | null
  site_name_snapshot?: string | null
  aliases: string[]
  query_filter: string
  default_time_range: string
  enabled: boolean
  sort_order: number
  scope_metadata: Record<string, any>
  updated_at?: string | null
}

export interface LogScopePayload {
  scope_key: string
  display_name: string
  netbox_site_id?: number | null
  site_code_snapshot?: string | null
  site_name_snapshot?: string | null
  aliases: string[]
  query_filter: string
  default_time_range: string
  enabled: boolean
  sort_order: number
  scope_metadata?: Record<string, any>
}

export const settingsApi = {
  async getModels(): Promise<ModelsResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models` : `${API_BASE_URL}/settings/models`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async getActiveModel(): Promise<ModelResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/active` : `${API_BASE_URL}/settings/models/active`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async getProviders(): Promise<ProvidersResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/providers` : `${API_BASE_URL}/settings/models/providers`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async createModel(request: CreateModelRequest): Promise<ModelResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models` : `${API_BASE_URL}/settings/models`
      const response = await axios.post(apiUrl, request)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async updateModel(modelId: string, request: UpdateModelRequest): Promise<ModelResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/${modelId}` : `${API_BASE_URL}/settings/models/${modelId}`
      const response = await axios.put(apiUrl, request)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async activateModel(modelId: string): Promise<{ success: boolean; message?: string; error?: string }> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/${modelId}/activate` : `${API_BASE_URL}/settings/models/${modelId}/activate`
      const response = await axios.post(apiUrl)
      return { success: true, message: response.data?.message || '激活成功' }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async deleteModel(modelId: string): Promise<{ success: boolean; error?: string }> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/${modelId}` : `${API_BASE_URL}/settings/models/${modelId}`
      await axios.delete(apiUrl)
      return { success: true }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async testModel(modelId: string): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/models/test/${modelId}` : `${API_BASE_URL}/settings/models/test/${modelId}`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async getIntegrations(): Promise<IntegrationListResponse> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/integrations` : `${API_BASE_URL}/settings/integrations`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data?.data || [] }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async updateIntegration(
    integrationType: string,
    request: IntegrationSaveRequest,
  ): Promise<IntegrationResponse> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http')
        ? `${API_BASE_URL}/api/settings/integrations/${integrationType}`
        : `${API_BASE_URL}/settings/integrations/${integrationType}`
      const response = await axios.put(apiUrl, request)
      return { success: true, data: response.data?.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async testIntegration(
    integrationType: string,
  ): Promise<{ success: boolean; message?: string; details?: any; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http')
        ? `${API_BASE_URL}/api/settings/integrations/${integrationType}/test`
        : `${API_BASE_URL}/settings/integrations/${integrationType}/test`
      const response = await axios.post(apiUrl)
      return {
        success: Boolean(response.data?.success),
        message: response.data?.message,
        details: response.data?.details,
      }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async getSshSecurityStatus(): Promise<{ success: boolean; data?: any; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/ssh-security` : `${API_BASE_URL}/settings/ssh-security`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data?.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async getLogScopes(): Promise<{ success: boolean; data?: LogScope[]; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/log-scopes` : `${API_BASE_URL}/settings/log-scopes`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data?.data || [] }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async createLogScope(payload: LogScopePayload): Promise<{ success: boolean; data?: LogScope; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/log-scopes` : `${API_BASE_URL}/settings/log-scopes`
      const response = await axios.post(apiUrl, payload)
      return { success: true, data: response.data?.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async updateLogScope(scopeId: number, payload: LogScopePayload): Promise<{ success: boolean; data?: LogScope; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/log-scopes/${scopeId}` : `${API_BASE_URL}/settings/log-scopes/${scopeId}`
      const response = await axios.put(apiUrl, payload)
      return { success: true, data: response.data?.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async deleteLogScope(scopeId: number): Promise<{ success: boolean; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/log-scopes/${scopeId}` : `${API_BASE_URL}/settings/log-scopes/${scopeId}`
      await axios.delete(apiUrl)
      return { success: true }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  },

  async testLogScope(scopeId: number): Promise<{ success: boolean; message?: string; details?: any; error?: string }> {
    try {
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/settings/log-scopes/${scopeId}/test` : `${API_BASE_URL}/settings/log-scopes/${scopeId}/test`
      const response = await axios.post(apiUrl)
      return {
        success: Boolean(response.data?.success),
        message: response.data?.message,
        details: response.data?.details,
      }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.detail || error.message }
    }
  }
}
