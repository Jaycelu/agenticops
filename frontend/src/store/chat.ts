import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatApi, ChatRequest, ChatResponse, ExecutionStep } from '@/api/chat'
import { sessionsApi, Session } from '@/api/sessions'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  execution_results?: ExecutionStep[]
  trace_id?: string
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentTraceId = ref<string | null>(null)
  const currentSessionId = ref<string>('default')
  const sessions = ref<Session[]>([])

  async function sendMessage(message: string) {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: Date.now()
    }
    messages.value.push(userMessage)

    isLoading.value = true

    try {
      const request: ChatRequest = {
        message,
        session_id: currentSessionId.value
      }

      const response: ChatResponse = await chatApi.sendMessage(request)

      if (!response.success || !response.data) {
        throw new Error(response.error || '请求失败')
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response || response.data.message || '',
        timestamp: Date.now(),
        execution_results: response.data.execution_results,
        trace_id: response.data.trace_id
      }

      messages.value.push(assistantMessage)
      currentTraceId.value = response.data.trace_id ?? null

      // 刷新会话列表
      await loadSessions()
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '抱歉，发送消息时出现错误，请稍后重试。',
        timestamp: Date.now()
      }
      messages.value.push(errorMessage)
    } finally {
      isLoading.value = false
    }
  }

  async function loadSessions() {
    try {
      const response = await sessionsApi.listSessions()
      if (response.success && response.data) {
        sessions.value = response.data
      }
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }

  async function switchSession(sessionId: string) {
    try {
      const response = await sessionsApi.getSession(sessionId)
      if (!response.success || !response.data) {
        throw new Error(response.error || '获取会话详情失败')
      }

      const sessionDetail = response.data
      currentSessionId.value = sessionId

      // 转换消息格式
      messages.value = sessionDetail.messages.map((msg, index) => ({
        id: `${sessionId}_${index}`,
        role: msg.role as 'user' | 'assistant',
        content: msg.content,
        timestamp: msg.timestamp || Date.now(),
        execution_results: msg.execution_results,
        trace_id: msg.trace_id
      }))

      // 设置当前trace_id
      const lastAssistantMessage = [...messages.value].reverse().find(
        msg => msg.role === 'assistant' && msg.trace_id
      )
      currentTraceId.value = lastAssistantMessage?.trace_id || null
    } catch (error) {
      console.error('Error switching session:', error)
    }
  }

  async function createNewSession() {
    const newSessionId = `session_${Date.now()}`
    try {
      await sessionsApi.createSession({ name: newSessionId })
      currentSessionId.value = newSessionId
      clearMessages()
      await loadSessions()
    } catch (error) {
      console.error('Error creating session:', error)
    }
  }

  async function deleteSession(sessionId: string) {
    try {
      await sessionsApi.deleteSession(sessionId)

      // 如果删除的是当前会话，清空消息
      if (sessionId === currentSessionId.value) {
        clearMessages()
      }

      // 刷新会话列表
      await loadSessions()
    } catch (error) {
      console.error('Error deleting session:', error)
    }
  }

  function clearMessages() {
    messages.value = []
    currentTraceId.value = null
  }

  return {
    messages,
    isLoading,
    currentTraceId,
    currentSessionId,
    sessions,
    sendMessage,
    loadSessions,
    switchSession,
    createNewSession,
    deleteSession,
    clearMessages
  }
})
