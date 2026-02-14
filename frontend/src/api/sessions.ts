import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface Session {
  session_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface CreateSessionRequest {
  name: string
}

export interface SessionMessage {
  role: string
  content: string
  timestamp?: number
  execution_results?: any[]
  trace_id?: string
}

export interface SessionDetail {
  session_id: string
  created_at: string
  updated_at: string
  messages: SessionMessage[]
}

export interface SessionResponse {
  success: boolean
  data?: Session
  error?: string
}

export interface SessionDetailResponse {
  success: boolean
  data?: SessionDetail
  error?: string
}

export interface SessionsResponse {
  success: boolean
  data?: Session[]
  error?: string
}

export const sessionsApi = {
  async listSessions(): Promise<SessionsResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions` : `${API_BASE_URL}/sessions`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async createSession(request: CreateSessionRequest): Promise<SessionResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions` : `${API_BASE_URL}/sessions`
      const response = await axios.post(apiUrl, request)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async getSession(sessionId: string): Promise<SessionDetailResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions/${sessionId}` : `${API_BASE_URL}/sessions/${sessionId}`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async deleteSession(sessionId: string): Promise<{ success: boolean; error?: string }> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions/${sessionId}` : `${API_BASE_URL}/sessions/${sessionId}`
      await axios.delete(apiUrl)
      return { success: true }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  }
}