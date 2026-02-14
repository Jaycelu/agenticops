<template>
  <div class="dashboard">
    <div class="dashboard-content">
      <div class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">
            <MessageSquare class="title-icon" :size="20" />
            <h2>会话列表</h2>
          </div>
          <button @click="handleNewSession" class="btn-new">
            <Plus :size="16" />
            新建会话
          </button>
        </div>
        <div class="session-list">
          <div
            v-for="session in chatStore.sessions"
            :key="session.session_id"
            :class="['session-item', { active: session.session_id === chatStore.currentSessionId }]"
            @click="handleSwitchSession(session.session_id)"
          >
            <div class="session-content">
              <div class="session-title">{{ session.title }}</div>
              <div class="session-meta">
                <span class="session-time">{{ formatTime(session.updated_at) }}</span>
                <span class="session-count">{{ session.message_count }}条消息</span>
              </div>
            </div>
            <button
              v-if="session.session_id !== chatStore.currentSessionId"
              @click.stop="handleDeleteSession(session.session_id)"
              class="btn-delete"
              title="删除会话"
            >
              <Trash2 :size="14" />
            </button>
          </div>
          <div v-if="chatStore.sessions.length === 0" class="no-sessions">
            <MessageSquareOff :size="48" />
            <p>暂无会话</p>
            <p class="hint">点击"新建会话"开始对话</p>
          </div>
        </div>
      </div>

      <div class="main-content">
        <div class="chat-container">
          <div class="messages" ref="messagesContainer">
            <div
              v-for="message in chatStore.messages"
              :key="message.id"
              :class="['message', message.role]"
            >
              <div class="message-avatar">
                <User v-if="message.role === 'user'" :size="20" />
                <Bot v-else :size="20" />
              </div>
              <div class="message-content">
                <div class="message-text">{{ message.content }}</div>
                <div class="message-time">{{ formatTime(message.timestamp) }}</div>
              </div>
            </div>
            <div v-if="chatStore.isLoading" class="message assistant animate-pulse">
              <div class="message-avatar">
                <Bot :size="20" />
              </div>
              <div class="message-content">
                <div class="message-text typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <div class="input-area">
            <div class="input-wrapper">
              <textarea
                v-model="inputMessage"
                @keydown.enter.prevent="handleSend"
                placeholder="输入您的问题，例如：查询核心交换机的信息"
                rows="1"
                :disabled="chatStore.isLoading"
                class="chat-input"
                @input="autoResize"
              ></textarea>
              <button
                @click="handleSend"
                :disabled="!inputMessage.trim() || chatStore.isLoading"
                class="btn-send"
                title="发送消息"
              >
                <Send :size="18" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="trace-panel">
        <div class="trace-header">
          <div class="trace-title">
            <Terminal class="title-icon" :size="18" />
            <h3>执行结果</h3>
          </div>
          <span v-if="chatStore.currentTraceId" class="trace-id">
            Trace ID: {{ chatStore.currentTraceId }}
          </span>
        </div>
        <div class="trace-content">
          <div
            v-for="(msg, index) in chatStore.messages"
            :key="index"
            class="trace-message"
          >
            <div v-if="msg.execution_results && msg.execution_results.length > 0">
              <div v-for="(step, stepIndex) in msg.execution_results" :key="stepIndex" class="trace-step">
                <div class="step-header">
                  <span class="step-number">Step {{ stepIndex + 1 }}</span>
                  <span :class="['step-status', step.status]">
                    <component :is="getStatusIcon(step.status)" :size="12" />
                    {{ step.status }}
                  </span>
                </div>
                <div class="step-details">
                  <div class="step-detail">
                    <span class="label">工具:</span>
                    <span class="value">{{ step.tool }}</span>
                  </div>
                  <div class="step-detail">
                    <span class="label">操作:</span>
                    <span class="value">{{ step.action }}</span>
                  </div>
                  <div class="step-detail" v-if="step.result">
                    <span class="label">结果:</span>
                    <pre class="value json-result">{{ JSON.stringify(step.result, null, 2) }}</pre>
                  </div>
                  <div class="step-detail" v-if="step.error">
                    <span class="label error">错误:</span>
                    <span class="value error">{{ step.error }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!hasExecutionResults" class="no-trace">
            <TerminalSquare :size="48" />
            <p>暂无执行轨迹</p>
            <p class="hint">AI执行工具时会显示详细结果</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/store/chat'
import { MessageSquare, Plus, Trash2, MessageSquareOff, User, Bot, Send, Terminal, TerminalSquare, CheckCircle2, Clock, XCircle, Loader2 } from 'lucide-vue-next'

const chatStore = useChatStore()
const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const hasExecutionResults = computed(() => {
  return chatStore.messages.some(msg => msg.execution_results && msg.execution_results.length > 0)
})

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return CheckCircle2
    case 'running':
      return Loader2
    case 'failed':
      return XCircle
    default:
      return Clock
  }
}

function formatTime(timestamp: number | string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 24 * 60 * 60 * 1000 && date.getDate() === now.getDate()) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
}

async function handleSend() {
  if (!inputMessage.value.trim() || chatStore.isLoading) return

  const message = inputMessage.value
  inputMessage.value = ''

  await chatStore.sendMessage(message)

  await nextTick()
  scrollToBottom()
}

async function handleNewSession() {
  await chatStore.createNewSession()
}

async function handleSwitchSession(sessionId: string) {
  if (sessionId === chatStore.currentSessionId) return
  await chatStore.switchSession(sessionId)
  await nextTick()
  scrollToBottom()
}

async function handleDeleteSession(sessionId: string) {
  if (confirm('确定要删除这个会话吗？')) {
    await chatStore.deleteSession(sessionId)
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function autoResize(event: Event) {
  const target = event.target as HTMLTextAreaElement
  target.style.height = 'auto'
  target.style.height = Math.min(target.scrollHeight, 120) + 'px'
}

onMounted(async () => {
  await chatStore.loadSessions()
  scrollToBottom()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

.dashboard-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  width: 280px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: white;
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.title-icon {
  color: #4a9eff;
}

.sidebar-header h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.btn-new {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  width: 100%;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
}

.btn-new:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 6px;
  position: relative;
  transition: all 0.3s;
  background: rgba(255, 255, 255, 0.05);
}

.session-item.active {
  background: linear-gradient(135deg, rgba(74, 158, 255, 0.2) 0%, rgba(74, 158, 255, 0.1) 100%);
  border-left: 3px solid #4a9eff;
}

.session-item:hover:not(.active) {
  background: rgba(255, 255, 255, 0.1);
  transform: translateX(2px);
}

.session-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  opacity: 0.6;
  gap: 8px;
}

.session-time {
  flex: 1;
}

.btn-delete {
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  border: none;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: all 0.3s;
  flex-shrink: 0;
}

.btn-delete:hover {
  background: rgba(220, 53, 69, 0.2);
  color: #ff6b6b;
}

.no-sessions {
  text-align: center;
  color: rgba(255, 255, 255, 0.4);
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.no-sessions p {
  margin: 0;
  font-size: 14px;
}

.no-sessions .hint {
  font-size: 12px;
  opacity: 0.6;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.message.assistant .message-avatar {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
}

.message-content {
  padding: 14px 18px;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  max-width: 100%;
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #f8f9fa;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-text {
  margin-bottom: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.message-time {
  font-size: 11px;
  opacity: 0.7;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: currentColor;
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
  opacity: 0.6;
}

.typing-indicator span:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-8px);
  }
}

.animate-pulse {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.input-area {
  padding: 20px 24px;
  border-top: 1px solid #e8eef5;
  background: white;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: #f8f9fa;
  border-radius: 12px;
  padding: 8px;
  border: 2px solid transparent;
  transition: all 0.3s;
}

.input-wrapper:focus-within {
  border-color: #4a9eff;
  background: white;
  box-shadow: 0 0 0 4px rgba(74, 158, 255, 0.1);
}

.chat-input {
  flex: 1;
  padding: 10px 14px;
  border: none;
  background: transparent;
  resize: none;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  min-height: 40px;
  max-height: 120px;
}

.chat-input:focus {
  outline: none;
}

.chat-input::placeholder {
  color: #999;
}

.btn-send {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
  flex-shrink: 0;
}

.btn-send:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
}

.btn-send:disabled {
  background: #ccc;
  cursor: not-allowed;
  transform: none;
}

.trace-panel {
  width: 420px;
  background: #f8f9fa;
  border-left: 1px solid #e8eef5;
  display: flex;
  flex-direction: column;
}

.trace-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8eef5;
  background: white;
}

.trace-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.trace-title h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.trace-id {
  font-size: 11px;
  color: #666;
  font-family: 'Monaco', 'Menlo', monospace;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 4px;
}

.trace-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.trace-step {
  background: white;
  border: 1px solid #e8eef5;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  animation: slideIn 0.3s ease-out;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.step-number {
  font-weight: 600;
  color: #333;
  font-size: 13px;
}

.step-status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.step-status.pending {
  background: #fff3e0;
  color: #e65100;
}

.step-status.running {
  background: #e3f2fd;
  color: #1565c0;
}

.step-status.completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.step-status.failed {
  background: #ffebee;
  color: #c62828;
}

.step-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.step-detail {
  display: flex;
  gap: 8px;
  font-size: 13px;
  align-items: flex-start;
}

.step-detail .label {
  color: #666;
  min-width: 50px;
  flex-shrink: 0;
}

.step-detail .value {
  flex: 1;
  color: #333;
  word-break: break-word;
}

.step-detail .value.error {
  color: #dc3545;
}

.json-result {
  background: #f8f9fa;
  padding: 10px;
  border-radius: 6px;
  font-size: 11px;
  overflow-x: auto;
  margin: 0;
  border: 1px solid #e8eef5;
}

.no-trace {
  text-align: center;
  color: #999;
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.no-trace p {
  margin: 0;
  font-size: 14px;
}

.no-trace .hint {
  font-size: 12px;
  opacity: 0.6;
}
</style>