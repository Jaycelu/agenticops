import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export interface ChatRequest {
  message: string
  session_id?: string
}

export interface ExecutionStep {
  [key: string]: unknown
}

export interface ChatResponse {
  success: boolean
  data?: {
    response: string
    message?: string
    trace_id?: string
    execution_results?: ExecutionStep[]
    execution_plan?: any
  }
  error?: string
}

export interface Session {
  id: string
  name: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface SessionsResponse {
  success: boolean
  data?: Session[]
  error?: string
}

export const chatApi = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/chat/` : `${API_BASE_URL}/chat/`
      const response = await axios.post(apiUrl, request)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async getSessions(): Promise<SessionsResponse> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions` : `${API_BASE_URL}/sessions`
      const response = await axios.get(apiUrl)
      return { success: true, data: response.data }
    } catch (error: any) {
      return { success: false, error: error.response?.data?.message || error.message }
    }
  },

  async createSession(name: string): Promise<{ success: boolean; data?: Session; error?: string }> {
    try {
      // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
      const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/sessions` : `${API_BASE_URL}/sessions`
      const response = await axios.post(apiUrl, { name })
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
