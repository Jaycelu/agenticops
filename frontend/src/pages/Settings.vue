<template>
  <div class="page app-page">
    <div class="page-content">
      <div class="page-header app-page-header">
        <div class="page-title app-page-title">
          <span class="app-page-title-icon">
            <Settings class="title-icon" :size="24" />
          </span>
          <div class="app-page-copy">
            <h1>系统设置</h1>
          </div>
        </div>
      </div>
      
      <div class="settings-container">
        <!-- 设置导航 -->
        <div class="settings-nav">
          <button 
            v-for="tab in tabs" 
            :key="tab.id"
            @click="currentTab = tab.id"
            :class="['tab-button', { active: currentTab === tab.id }]"
          >
            <component :is="tab.icon" :size="18" />
            {{ tab.name }}
          </button>
        </div>

        <div v-if="currentTab === 'integrations'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <Globe class="section-icon" :size="20" />
              <h2>集成配置</h2>
            </div>
          </div>

          <!-- 自动化模式切换 -->
          <div class="mode-switch-banner">
            <div class="mode-info">
              <div class="mode-title">
                <Activity class="mode-icon" :size="20" />
                <h3>自动化模式</h3>
              </div>
              <p class="mode-description">
                {{ automationMode?.is_observe_only
                  ? '只读分析'
                  : '自动处置' }}
              </p>
            </div>
            <div class="mode-controls">
              <button
                :class="['mode-button', { active: automationMode?.mode === 'observe_only' }]"
                @click="setAutomationMode('observe_only')"
                :disabled="switchingMode"
              >
                <Eye class="mode-btn-icon" :size="16" />
                <span>观察模式</span>
              </button>
              <button
                :class="['mode-button', { active: automationMode?.mode === 'auto' }]"
                @click="setAutomationMode('auto')"
                :disabled="switchingMode"
              >
                <Zap class="mode-btn-icon" :size="16" />
                <span>自动模式</span>
              </button>
            </div>
          </div>

          <div class="helper-banner">
            <div>
              <strong>敏感字段已启用密文存储</strong>
            </div>
            <span :class="['banner-status', sshSecurity?.app_secret_key_configured ? 'ok' : 'warn']">
              {{ sshSecurity?.app_secret_key_configured ? '主密钥已配置' : '缺少 APP_SECRET_KEY' }}
            </span>
          </div>

          <div class="integration-grid">
            <div v-for="integration in integrationMeta" :key="integration.id" class="integration-card">
              <div class="card-header">
                <div class="model-info">
                  <h3>{{ integration.name }}</h3>
                  <p class="model-provider">
                    <Server :size="14" />
                    {{ integration.description }}
                  </p>
                </div>
                <div class="card-actions">
                  <button
                    class="btn-test"
                    :disabled="testingIntegrations[integration.id]"
                    @click="testIntegrationConfig(integration.id)"
                  >
                    <Zap :size="14" />
                    {{ testingIntegrations[integration.id] ? '测试中...' : '测试连接' }}
                  </button>
                  <button
                    class="btn-primary"
                    :disabled="savingIntegrations[integration.id]"
                    @click="saveIntegrationConfig(integration.id)"
                  >
                    <Loader2 v-if="savingIntegrations[integration.id]" class="animate-spin" :size="14" />
                    <Check v-else :size="14" />
                    {{ savingIntegrations[integration.id] ? '保存中...' : '保存配置' }}
                  </button>
                </div>
              </div>
              <div class="card-body">
                <div class="toggle-row">
                  <label class="toggle-label">
                    <input v-model="integrationForms[integration.id].enabled" type="checkbox" />
                    <span>启用 {{ integration.name }}</span>
                  </label>
                  <span class="integration-source">
                    来源：{{ integrationForms[integration.id].source === 'database' ? '设置中心' : integrationForms[integration.id].source === 'env' ? '环境变量兼容' : '未配置' }}
                  </span>
                </div>

                <div class="integration-form-grid">
                  <div v-for="field in integration.configFields" :key="`${integration.id}-${field.key}`" class="form-group">
                    <label>{{ field.label }}</label>
                    <input
                      v-model="integrationForms[integration.id].config[field.key]"
                      type="text"
                      :placeholder="field.placeholder"
                    />
                  </div>

                  <div v-for="field in integration.secretFields" :key="`${integration.id}-${field.key}`" class="form-group">
                    <label>{{ field.label }}</label>
                    <input
                      v-model="integrationForms[integration.id].secrets[field.key]"
                      type="password"
                      :placeholder="integrationForms[integration.id].secretStatus[field.key] ? '已保存，如需更新请重新输入' : field.placeholder"
                    />
                    <p class="help-text">
                      {{ integrationForms[integration.id].secretStatus[field.key] ? '密钥已保存' : '尚未配置' }}
                    </p>
                  </div>
                </div>

                <div class="integration-footer">
                  <span class="help-text">
                    最近更新：{{ integrationForms[integration.id].updatedAt || '尚未保存' }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="section-header log-scope-header">
            <div class="section-title">
              <FileText class="section-icon" :size="20" />
              <h2>日志范围配置</h2>
            </div>
            <button class="btn-secondary" @click="resetLogScopeForm">新建范围</button>
          </div>

          <div class="ssh-layout">
            <div class="ssh-credentials-panel">
              <h3>范围列表</h3>
              <div class="credential-list">
                <button
                  v-for="scope in logScopes"
                  :key="scope.id"
                  class="credential-item"
                  :class="{ active: selectedLogScopeId === scope.id }"
                  @click="selectLogScope(scope.id)"
                >
                  <div>
                    <strong>{{ scope.display_name }}</strong>
                    <div class="credential-meta">
                      {{ scope.scope_key }}
                      <span v-if="scope.site_name_snapshot"> / {{ scope.site_name_snapshot }}</span>
                    </div>
                  </div>
                  <Trash2 :size="14" class="delete-credential-icon" @click.stop="removeLogScope(scope.id)" />
                </button>
              </div>
            </div>

            <div class="ssh-bindings-panel">
              <h3>{{ selectedLogScopeId ? '编辑日志范围' : '新建日志范围' }}</h3>
              <div class="ssh-form">
                <input v-model="logScopeForm.scope_key" placeholder="范围标识，如 campus_a" />
                <input v-model="logScopeForm.display_name" placeholder="显示名称，如 A 园区日志" />
                <select v-model="selectedLogScopeSiteKey" @change="applySelectedLogScopeSite">
                  <option value="">不绑定站点</option>
                  <option v-for="site in siteOptions" :key="site.id" :value="String(site.id)">
                    {{ site.name }} ({{ site.slug || 'no-slug' }})
                  </option>
                </select>
                <input v-model="logScopeForm.site_code_snapshot" placeholder="站点代码快照，如 SITE_A" />
                <input v-model="logScopeForm.site_name_snapshot" placeholder="站点名称快照，如 A 园区" />
                <input v-model="logScopeForm.aliasesText" placeholder="别名，逗号分隔，如 campus-a,园区A" />
                <input v-model="logScopeForm.default_time_range" placeholder="默认时间窗，如 -1d,now" />
                <input v-model.number="logScopeForm.sort_order" type="number" placeholder="排序" />
                <label class="toggle-label">
                  <input v-model="logScopeForm.enabled" type="checkbox" />
                  <span>启用该日志范围</span>
                </label>
                <textarea v-model="logScopeForm.query_filter" rows="6" placeholder="输入 ELK 查询过滤条件"></textarea>
                <div style="display: flex; gap: 8px;">
                  <button class="btn-primary" @click="saveLogScope" :disabled="savingLogScope">
                    {{ savingLogScope ? '保存中...' : selectedLogScopeId ? '更新范围' : '创建范围' }}
                  </button>
                  <button class="btn-secondary" @click="testCurrentLogScope" :disabled="testingLogScope || !selectedLogScopeId">
                    {{ testingLogScope ? '测试中...' : '测试查询' }}
                  </button>
                </div>
                <p v-if="logScopeTestMessage" class="help-text">{{ logScopeTestMessage }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 模型设置 -->
        <div v-if="currentTab === 'models'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <Cpu class="section-icon" :size="20" />
              <h2>模型设置</h2>
            </div>
            <button @click="showCreateModal = true" class="btn-primary">
              <Plus :size="16" />
              添加模型
            </button>
          </div>

          <!-- 当前激活的模型 -->
          <div class="active-model-card" v-if="activeModel">
            <div class="card-header">
              <div class="model-info">
                <div class="badge-container">
                  <span class="badge badge-active">
                    <CheckCircle2 :size="12" />
                    当前激活
                  </span>
                </div>
                <h3>{{ activeModel.name }}</h3>
                <p class="model-provider">
                  <Server :size="14" />
                  {{ getProviderName(activeModel.provider) }}
                </p>
              </div>
              <button @click="testModel(activeModel.id)" class="btn-test" :disabled="testing">
                <Zap :size="14" />
                {{ testing ? '测试中...' : '测试连接' }}
              </button>
            </div>
            <div class="card-body">
              <div class="info-row">
                <span class="label">
                  <Globe :size="14" />
                  API地址:
                </span>
                <span class="value">{{ activeModel.api_url }}</span>
              </div>
              <div class="info-row">
                <span class="label">
                  <Box :size="14" />
                  模型:
                </span>
                <span class="value">{{ activeModel.model }}</span>
              </div>
              <div class="info-row">
                <span class="label">
                  <Sliders :size="14" />
                  参数:
                </span>
                <span class="value">{{ formatParameters(activeModel.parameters) }}</span>
              </div>
            </div>
          </div>

          <!-- 模型列表 -->
          <div class="models-list">
            <div 
              v-for="model in models" 
              :key="model.id"
              class="model-card"
              :class="{ 'is-active': model.is_active }"
            >
              <div class="card-header">
                <div class="model-info">
                  <div class="badge-container">
                    <span v-if="model.is_active" class="badge badge-active">
                      <CheckCircle2 :size="12" />
                      当前激活
                    </span>
                  </div>
                  <h3>{{ model.name }}</h3>
                  <p class="model-provider">
                    <Server :size="14" />
                    {{ getProviderName(model.provider) }}
                  </p>
                </div>
                <div class="card-actions">
                  <button 
                    v-if="!model.is_active" 
                    @click="activateModel(model.id)" 
                    class="btn-activate"
                  >
                    <Power :size="14" />
                    激活
                  </button>
                  <button @click="editModel(model)" class="btn-edit">
                    <Pencil :size="14" />
                    编辑
                  </button>
                  <button @click="deleteModel(model.id)" class="btn-delete">
                    <Trash2 :size="14" />
                    删除
                  </button>
                </div>
              </div>
              <div class="card-body">
                <div class="info-row">
                  <span class="label">
                    <Globe :size="14" />
                    API地址:
                  </span>
                  <span class="value">{{ model.api_url }}</span>
                </div>
                <div class="info-row">
                  <span class="label">
                    <Box :size="14" />
                    模型:
                  </span>
                  <span class="value">{{ model.model }}</span>
                </div>
                <div class="info-row">
                  <span class="label">
                    <Sliders :size="14" />
                    参数:
                  </span>
                  <span class="value">{{ formatParameters(model.parameters) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- SSH 维护通道 -->
        <div v-if="currentTab === 'ssh'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <ShieldCheck class="section-icon" :size="20" />
              <h2>SSH 维护执行通道</h2>
            </div>
          </div>
          <div class="ssh-layout">
            <div class="ssh-credentials-panel">
              <h3>凭据列表</h3>
              <div class="ssh-form">
                <input v-model="sshForm.name" placeholder="凭据名称" />
                <input v-model="sshForm.username" placeholder="用户名" />
                <select v-model="sshForm.auth_type">
                  <option value="password">密码</option>
                  <option value="private_key">私钥</option>
                </select>
                <input v-model.number="sshForm.port" type="number" placeholder="端口" />
                <input v-if="sshForm.auth_type === 'password'" v-model="sshForm.password" type="password" placeholder="密码" />
                <textarea v-else v-model="sshForm.private_key" rows="5" placeholder="粘贴私钥"></textarea>
                <input v-if="sshForm.auth_type === 'private_key'" v-model="sshForm.passphrase" type="password" placeholder="密钥口令(可选)" />
                <button class="btn-primary" @click="createCredential" :disabled="creatingCredential">
                  {{ creatingCredential ? '创建中...' : '新增凭据' }}
                </button>
              </div>
              <div class="credential-list">
                <button
                  v-for="cred in sshCredentials"
                  :key="cred.id"
                  class="credential-item"
                  :class="{ active: selectedCredentialId === cred.id }"
                  @click="selectCredential(cred.id)"
                >
                  <div>
                    <strong>{{ cred.name }}</strong>
                    <div class="credential-meta">{{ cred.username }}@{{ cred.port }} ({{ cred.auth_type }})</div>
                  </div>
                  <Trash2 :size="14" class="delete-credential-icon" @click.stop="removeCredential(cred.id)" />
                </button>
              </div>
            </div>

            <div class="ssh-bindings-panel">
              <h3>设备关联看板</h3>
              <div class="device-filter-grid">
                <input v-model="deviceNameFilter" placeholder="按设备名称搜索" />
                <select v-model="siteFilter">
                  <option value="">全部站点</option>
                  <option v-for="site in sshFilterOptions.sites" :key="site" :value="site">{{ site }}</option>
                </select>
                <select v-model="deviceTypeFilter">
                  <option value="">全部设备类型</option>
                  <option v-for="item in sshFilterOptions.types" :key="item" :value="item">{{ item }}</option>
                </select>
                <select v-model="deviceVendorFilter">
                  <option value="">全部厂商</option>
                  <option v-for="item in sshFilterOptions.vendors" :key="item" :value="item">{{ item }}</option>
                </select>
                <select v-model="deviceRoleFilter">
                  <option value="">全部角色</option>
                  <option v-for="item in sshFilterOptions.roles" :key="item" :value="item">{{ item }}</option>
                </select>
                <input v-model="tagFilter" placeholder="Tag过滤(可选)" />
                <button class="btn-secondary" @click="loadNetBoxDeviceCandidates">加载设备</button>
              </div>
              <div class="candidate-toolbar">
                <label class="select-all">
                  <input type="checkbox" :checked="allCandidateSelected" @change="toggleAllCandidateDevices" />
                  <span>全选当前列表</span>
                </label>
                <span class="selected-count">已选 {{ selectedDeviceIds.length }} / {{ candidateDevices.length }}</span>
              </div>
              <div class="candidate-list">
                <label v-for="device in candidateDevices" :key="device.id" class="candidate-item">
                  <input v-model="selectedDeviceIds" type="checkbox" :value="device.id" />
                  <span>{{ device.name }} ({{ device.primary_ip || '无IP' }})</span>
                  <small>{{ device.site }} / {{ device.role || '-' }} / {{ device.vendor || '-' }} / {{ device.device_type || '-' }}</small>
                </label>
              </div>
              <button class="btn-primary" @click="bindSelectedDevices">批量关联到选中凭据</button>

              <div class="binding-list">
                <div v-for="binding in sshBindings" :key="binding.id" class="binding-item">
                  <div class="binding-main">
                    <div class="binding-title">{{ binding.device_name || binding.netbox_device_id }}</div>
                    <div class="binding-meta">{{ binding.site_name }} / {{ binding.platform || '-' }}</div>
                  </div>
                  <div class="binding-status" :class="binding.last_connectivity_status">
                    {{ statusText(binding.last_connectivity_status) }}
                  </div>
                  <button class="btn-secondary" @click="testBinding(binding)" :disabled="testingBindingId === binding.netbox_device_id">
                    {{ testingBindingId === binding.netbox_device_id ? '检查中...' : '连通性检查' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- 创建/编辑模型弹窗 -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">
            <component :is="editingModel ? Pencil : PlusCircle" :size="20" />
            <h2>{{ editingModel ? '编辑模型' : '添加模型' }}</h2>
          </div>
          <button @click="showCreateModal = false" class="btn-close">
            <X :size="18" />
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>
              <Type :size="14" />
              模型名称 *
            </label>
            <input v-model="modelForm.name" type="text" placeholder="例如：Qwen3-32B-AWQ" />
          </div>

          <div class="form-group">
            <label>
              <Building2 :size="14" />
              提供商 *
            </label>
            <select v-model="modelForm.provider" @change="onProviderChange">
              <option value="">请选择提供商</option>
              <option v-for="provider in providers" :key="provider.id" :value="provider.id">
                {{ provider.name }}
              </option>
            </select>
            <p class="help-text">{{ getProviderDescription(modelForm.provider) }}</p>
          </div>

          <div class="form-group">
            <label>
              <Key :size="14" />
              API密钥 *
            </label>
            <input v-model="modelForm.api_key" type="password" placeholder="请输入API密钥" />
          </div>

          <div class="form-group">
            <label>
              <Globe :size="14" />
              API地址 *
            </label>
            <input v-model="modelForm.api_url" type="text" placeholder="例如：http://localhost:8000/v1" />
            <p class="help-text" v-if="modelForm.provider">
              <Info :size="12" />
              推荐: {{ getProviderExample(modelForm.provider) }}
            </p>
          </div>

          <div class="form-group">
            <label>
              <Box :size="14" />
              模型名称 *
            </label>
            <input v-model="modelForm.model" type="text" placeholder="例如：Qwen/Qwen3-32B-AWQ" />
          </div>

          <div class="form-group">
            <label>
              <Thermometer :size="14" />
              温度 (Temperature)
            </label>
            <input v-model.number="modelForm.parameters.temperature" type="number" step="0.1" min="0" max="2" />
            <p class="help-text">控制输出的随机性，0-2之间，默认0.7</p>
          </div>

          <div class="form-group">
            <label>
              <Hash :size="14" />
              最大令牌数 (Max Tokens)
            </label>
            <input v-model.number="modelForm.parameters.max_tokens" type="number" min="1" max="32000" />
            <p class="help-text">控制输出的最大长度，默认4096</p>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCreateModal = false" class="btn-secondary">
            <X :size="14" />
            取消
          </button>
          <button @click="saveModel" class="btn-primary" :disabled="saving">
            <Loader2 v-if="saving" class="animate-spin" :size="14" />
            <Check v-else :size="14" />
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

import axios from 'axios'
import { settingsApi, type LogScope } from '@/api/settings'
import {
  bindCredentialDevices,
  createSSHCredential,
  deleteSSHCredential,
  listCredentialBindings,
  listSSHCredentials,
  queryNetBoxDevices,
  testSSHConnectivity,
} from '@/api/ssh'
import {
  Settings, Cpu, Plus, Server, Globe, Box, Sliders, CheckCircle2, Zap,
  Power, Pencil, Trash2, Building2, Key, Thermometer, Hash, X, Info,
  Loader2, Check, PlusCircle, FileText, ShieldCheck, Activity, Eye
} from 'lucide-vue-next'

// 使用相对路径，让 Vite 代理处理
const API_BASE_URL = '/api'

interface ModelConfig {
  id: string
  name: string
  provider: string
  api_key: string
  api_url: string
  model: string
  is_active: boolean
  parameters: {
    temperature?: number
    max_tokens?: number
  }
}

interface Provider {
  id: string
  name: string
  description: string
  required_params: string[]
  optional_params: string[]
}

const tabs = [
  { id: 'integrations', name: '集成配置', icon: Globe },
  { id: 'models', name: '模型设置', icon: Cpu },
  { id: 'ssh', name: 'SSH 通道', icon: ShieldCheck }
]

const currentTab = ref('integrations')
const models = ref<ModelConfig[]>([])
const providers = ref<Provider[]>([])
const activeModel = ref<ModelConfig | null>(null)
const showCreateModal = ref(false)
const editingModel = ref<ModelConfig | null>(null)
const saving = ref(false)
const testing = ref(false)

const modelForm = ref({
  name: '',
  provider: '',
  api_key: '',
  api_url: '',
  model: '',
  parameters: {
    temperature: 0.7,
    max_tokens: 4096
  }
})

interface IntegrationFieldMeta {
  key: string
  label: string
  placeholder: string
}

interface IntegrationMeta {
  id: string
  name: string
  description: string
  configFields: IntegrationFieldMeta[]
  secretFields: IntegrationFieldMeta[]
}

interface IntegrationFormState {
  enabled: boolean
  config: Record<string, string>
  secrets: Record<string, string>
  secretStatus: Record<string, boolean>
  updatedAt: string
  source: string
}

interface SiteOption {
  id: number
  name: string
  slug?: string
}

const integrationMeta: IntegrationMeta[] = [
  {
    id: 'netbox',
    name: 'NetBox',
    description: '资产、角色、站点与拓扑数据源',
    configFields: [{ key: 'url', label: 'NetBox URL', placeholder: 'https://netbox.example.com' }],
    secretFields: [{ key: 'api_token', label: 'API Token', placeholder: '输入新的 API Token' }]
  },
  {
    id: 'elk',
    name: 'ELK',
    description: '日志检索与聚合数据源',
    configFields: [{ key: 'url', label: 'ELK API URL', placeholder: 'https://elk.example.com/api/v2/search/sheets/' }],
    secretFields: [
      { key: 'username', label: '用户名', placeholder: '输入 ELK 用户名' },
      { key: 'password', label: '密码', placeholder: '输入 ELK 密码' }
    ]
  },
  {
    id: 'zabbix',
    name: 'Zabbix',
    description: '告警与指标数据源',
    configFields: [
      { key: 'url', label: 'Zabbix URL', placeholder: 'https://zabbix.example.com' },
      { key: 'api_url', label: 'Zabbix API URL', placeholder: 'https://zabbix.example.com/api_jsonrpc.php' }
    ],
    secretFields: [
      { key: 'username', label: '用户名', placeholder: '输入 Zabbix 用户名' },
      { key: 'password', label: '密码', placeholder: '输入 Zabbix 密码' }
    ]
  }
]

function createIntegrationForm(meta: IntegrationMeta): IntegrationFormState {
  return {
    enabled: false,
    config: Object.fromEntries(meta.configFields.map((field) => [field.key, ''])),
    secrets: Object.fromEntries(meta.secretFields.map((field) => [field.key, ''])),
    secretStatus: Object.fromEntries(meta.secretFields.map((field) => [field.key, false])),
    updatedAt: '',
    source: 'default'
  }
}

const integrationForms = ref<Record<string, IntegrationFormState>>(
  Object.fromEntries(integrationMeta.map((meta) => [meta.id, createIntegrationForm(meta)]))
)
const savingIntegrations = ref<Record<string, boolean>>(
  Object.fromEntries(integrationMeta.map((meta) => [meta.id, false]))
)
const testingIntegrations = ref<Record<string, boolean>>(
  Object.fromEntries(integrationMeta.map((meta) => [meta.id, false]))
)
const sshSecurity = ref<{ app_secret_key_configured: boolean; message: string } | null>(null)
const automationMode = ref<{ mode: string; is_observe_only: boolean; description: string } | null>(null)
const switchingMode = ref(false)
const siteOptions = ref<SiteOption[]>([])
const logScopes = ref<LogScope[]>([])
const selectedLogScopeId = ref<number | null>(null)
const selectedLogScopeSiteKey = ref('')
const savingLogScope = ref(false)
const testingLogScope = ref(false)
const logScopeTestMessage = ref('')
const logScopeForm = ref({
  scope_key: '',
  display_name: '',
  netbox_site_id: null as number | null,
  site_code_snapshot: '',
  site_name_snapshot: '',
  aliasesText: '',
  query_filter: '',
  default_time_range: '-1d,now',
  enabled: true,
  sort_order: 100
})

interface SSHCredential {
  id: number
  name: string
  username: string
  auth_type: 'password' | 'private_key'
  port: number
  enabled: boolean
  has_password: boolean
  has_private_key: boolean
}

const sshCredentials = ref<SSHCredential[]>([])
const selectedCredentialId = ref<number | null>(null)
const sshBindings = ref<any[]>([])
const candidateDevices = ref<any[]>([])
const selectedDeviceIds = ref<number[]>([])
const siteFilter = ref('')
const tagFilter = ref('')
const deviceNameFilter = ref('')
const deviceRoleFilter = ref('')
const deviceVendorFilter = ref('')
const deviceTypeFilter = ref('')
const creatingCredential = ref(false)
const testingBindingId = ref<number | null>(null)
const sshForm = ref({
  name: '',
  username: '',
  auth_type: 'password',
  password: '',
  private_key: '',
  passphrase: '',
  port: 22
})

const sshFilterOptions = computed(() => {
  const sites = [...new Set(candidateDevices.value.map((d: any) => d.site).filter(Boolean))] as string[]
  const roles = [...new Set(candidateDevices.value.map((d: any) => d.role).filter(Boolean))] as string[]
  const vendors = [...new Set(candidateDevices.value.map((d: any) => d.vendor).filter(Boolean))] as string[]
  const types = [...new Set(candidateDevices.value.map((d: any) => d.device_type).filter(Boolean))] as string[]
  return {
    sites: sites.sort((a, b) => a.localeCompare(b)),
    roles: roles.sort((a, b) => a.localeCompare(b)),
    vendors: vendors.sort((a, b) => a.localeCompare(b)),
    types: types.sort((a, b) => a.localeCompare(b))
  }
})

const allCandidateSelected = computed(() => {
  return candidateDevices.value.length > 0 && selectedDeviceIds.value.length === candidateDevices.value.length
})

async function loadIntegrations() {
  const [integrationsResponse, sshResponse] = await Promise.all([
    settingsApi.getIntegrations(),
    settingsApi.getSshSecurityStatus()
  ])

  if (integrationsResponse.success && integrationsResponse.data) {
    for (const item of integrationsResponse.data) {
      const meta = integrationMeta.find((entry) => entry.id === item.integration_type)
      if (!meta) continue
      const nextForm = createIntegrationForm(meta)
      nextForm.enabled = item.enabled
      nextForm.source = item.source
      nextForm.updatedAt = item.updated_at || ''
      nextForm.config = { ...nextForm.config, ...(item.config || {}) }
      nextForm.secretStatus = { ...nextForm.secretStatus, ...(item.secret_status || {}) }
      integrationForms.value[item.integration_type] = nextForm
    }
  }

  if (sshResponse.success && sshResponse.data) {
    sshSecurity.value = sshResponse.data
  }
}

async function loadAutomationMode() {
  try {
    const response = await axios.get(`${API_BASE_URL}/settings/automation-mode`)
    if (response.data.success && response.data.data) {
      automationMode.value = response.data.data
    }
  } catch (error) {
    console.error('Error loading automation mode:', error)
  }
}

async function setAutomationMode(mode: string) {
  if (switchingMode.value) return

  switchingMode.value = true
  try {
    const response = await axios.put(`${API_BASE_URL}/settings/automation-mode`, null, {
      params: { mode }
    })

    if (response.data.success) {
      automationMode.value = response.data.data
      alert(response.data.message)
    } else {
      alert('切换模式失败: ' + response.data.message)
    }
  } catch (error) {
    console.error('Error setting automation mode:', error)
    alert('切换模式失败，请检查网络连接')
  } finally {
    switchingMode.value = false
  }
}

async function loadSiteOptions() {
  try {
    const response = await axios.get(`${API_BASE_URL}/sites`)
    siteOptions.value = (response.data?.sites || []).map((site: any) => ({
      id: site.id,
      name: site.name || site.site_name || site.site_code || `Site ${site.id}`,
      slug: site.slug || site.site_code || ''
    }))
  } catch (error) {
    siteOptions.value = []
  }
}

async function loadLogScopes() {
  const response = await settingsApi.getLogScopes()
  if (!response.success || !response.data) {
    return
  }
  logScopes.value = response.data
  if (!selectedLogScopeId.value && logScopes.value.length > 0) {
    selectLogScope(logScopes.value[0].id)
  }
}

function resetLogScopeForm() {
  selectedLogScopeId.value = null
  selectedLogScopeSiteKey.value = ''
  logScopeTestMessage.value = ''
  logScopeForm.value = {
    scope_key: '',
    display_name: '',
    netbox_site_id: null,
    site_code_snapshot: '',
    site_name_snapshot: '',
    aliasesText: '',
    query_filter: '',
    default_time_range: '-1d,now',
    enabled: true,
    sort_order: 100
  }
}

function selectLogScope(scopeId: number) {
  const scope = logScopes.value.find((item) => item.id === scopeId)
  if (!scope) return
  selectedLogScopeId.value = scope.id
  selectedLogScopeSiteKey.value = scope.netbox_site_id ? String(scope.netbox_site_id) : ''
  logScopeTestMessage.value = ''
  logScopeForm.value = {
    scope_key: scope.scope_key,
    display_name: scope.display_name,
    netbox_site_id: scope.netbox_site_id ?? null,
    site_code_snapshot: scope.site_code_snapshot || '',
    site_name_snapshot: scope.site_name_snapshot || '',
    aliasesText: (scope.aliases || []).join(', '),
    query_filter: scope.query_filter,
    default_time_range: scope.default_time_range,
    enabled: scope.enabled,
    sort_order: scope.sort_order
  }
}

function applySelectedLogScopeSite() {
  const siteId = selectedLogScopeSiteKey.value ? Number(selectedLogScopeSiteKey.value) : null
  logScopeForm.value.netbox_site_id = siteId
  const site = siteOptions.value.find((item) => item.id === siteId)
  if (!site) return
  if (!logScopeForm.value.site_name_snapshot) {
    logScopeForm.value.site_name_snapshot = site.name
  }
  if (!logScopeForm.value.site_code_snapshot) {
    logScopeForm.value.site_code_snapshot = (site.slug || site.name || '').toUpperCase().replace(/[^A-Z0-9_]+/g, '_')
  }
}

function buildLogScopePayload() {
  return {
    scope_key: logScopeForm.value.scope_key.trim(),
    display_name: logScopeForm.value.display_name.trim(),
    netbox_site_id: logScopeForm.value.netbox_site_id,
    site_code_snapshot: logScopeForm.value.site_code_snapshot.trim() || null,
    site_name_snapshot: logScopeForm.value.site_name_snapshot.trim() || null,
    aliases: logScopeForm.value.aliasesText.split(',').map((item) => item.trim()).filter(Boolean),
    query_filter: logScopeForm.value.query_filter.trim(),
    default_time_range: logScopeForm.value.default_time_range.trim() || '-1d,now',
    enabled: logScopeForm.value.enabled,
    sort_order: Number(logScopeForm.value.sort_order || 100),
    scope_metadata: {}
  }
}

async function saveLogScope() {
  const payload = buildLogScopePayload()
  if (!payload.scope_key || !payload.display_name || !payload.query_filter) {
    alert('请填写范围标识、显示名称和查询过滤条件')
    return
  }
  savingLogScope.value = true
  try {
    const response = selectedLogScopeId.value
      ? await settingsApi.updateLogScope(selectedLogScopeId.value, payload)
      : await settingsApi.createLogScope(payload)
    if (!response.success) {
      alert(response.error || '保存日志范围失败')
      return
    }
    await loadLogScopes()
    if (response.data) {
      selectLogScope(response.data.id)
    }
    alert('日志范围已保存')
  } finally {
    savingLogScope.value = false
  }
}

async function removeLogScope(scopeId: number) {
  if (!confirm('确认删除该日志范围吗？')) return
  const response = await settingsApi.deleteLogScope(scopeId)
  if (!response.success) {
    alert(response.error || '删除日志范围失败')
    return
  }
  if (selectedLogScopeId.value === scopeId) {
    resetLogScopeForm()
  }
  await loadLogScopes()
}

async function testCurrentLogScope() {
  if (!selectedLogScopeId.value) return
  testingLogScope.value = true
  try {
    const response = await settingsApi.testLogScope(selectedLogScopeId.value)
    logScopeTestMessage.value = response.error || response.message || '测试完成'
  } finally {
    testingLogScope.value = false
  }
}

async function saveIntegrationConfig(integrationType: string) {
  savingIntegrations.value[integrationType] = true
  try {
    const form = integrationForms.value[integrationType]
    const secrets = Object.fromEntries(
      Object.entries(form.secrets).filter(([, value]) => String(value || '').trim() !== '')
    )
    const response = await settingsApi.updateIntegration(integrationType, {
      enabled: form.enabled,
      config: form.config,
      secrets
    })
    if (!response.success) {
      alert(response.error || '保存集成配置失败')
      return
    }
    await loadIntegrations()
    integrationForms.value[integrationType].secrets = Object.fromEntries(
      Object.keys(integrationForms.value[integrationType].secrets).map((key) => [key, ''])
    )
    alert('集成配置已保存')
  } finally {
    savingIntegrations.value[integrationType] = false
  }
}

async function testIntegrationConfig(integrationType: string) {
  testingIntegrations.value[integrationType] = true
  try {
    const response = await settingsApi.testIntegration(integrationType)
    if (response.success) {
      alert(response.message || '连接测试成功')
      return
    }
    alert(response.error || response.message || '连接测试失败')
  } finally {
    testingIntegrations.value[integrationType] = false
  }
}

async function loadModels() {
  try {
    const response = await axios.get(`${API_BASE_URL}/settings/models`)
    models.value = response.data.data || []

    const activeResponse = await axios.get(`${API_BASE_URL}/settings/models/active`)
    if (activeResponse.data.success) {
      activeModel.value = activeResponse.data.model
    }
  } catch (error) {
    console.error('Error loading models:', error)
    alert('加载模型配置失败')
  }
}

async function loadSSHCredentials() {
  try {
    const response = await listSSHCredentials()
    sshCredentials.value = response.data || []
    if (!selectedCredentialId.value && sshCredentials.value.length > 0) {
      selectedCredentialId.value = sshCredentials.value[0].id
      await loadCredentialBindings()
    }
  } catch (error) {
    sshCredentials.value = []
  }
}

async function loadNetBoxDeviceCandidates() {
  try {
    const response = await queryNetBoxDevices({
      site: siteFilter.value || undefined,
      tag: tagFilter.value || undefined,
      name: deviceNameFilter.value || undefined,
      role: deviceRoleFilter.value || undefined,
      vendor: deviceVendorFilter.value || undefined,
      device_type: deviceTypeFilter.value || undefined
    })
    candidateDevices.value = response.data || []
    selectedDeviceIds.value = selectedDeviceIds.value.filter((id) =>
      candidateDevices.value.some((device: any) => device.id === id)
    )
  } catch (error) {
    candidateDevices.value = []
    selectedDeviceIds.value = []
  }
}

function toggleAllCandidateDevices() {
  if (allCandidateSelected.value) {
    selectedDeviceIds.value = []
    return
  }
  selectedDeviceIds.value = candidateDevices.value.map((item: any) => item.id)
}

async function createCredential() {
  if (!sshForm.value.name || !sshForm.value.username) {
    alert('请填写凭据名称和用户名')
    return
  }
  if (sshForm.value.auth_type === 'password' && !sshForm.value.password) {
    alert('请选择密码模式并填写密码')
    return
  }
  if (sshForm.value.auth_type === 'private_key' && !sshForm.value.private_key) {
    alert('请选择密钥模式并填写私钥')
    return
  }

  creatingCredential.value = true
  try {
    await createSSHCredential({ ...sshForm.value })
    sshForm.value = {
      name: '',
      username: '',
      auth_type: 'password',
      password: '',
      private_key: '',
      passphrase: '',
      port: 22
    }
    await loadSSHCredentials()
  } catch (error: any) {
    alert(error?.response?.data?.detail || '创建凭据失败')
  } finally {
    creatingCredential.value = false
  }
}

async function removeCredential(credentialId: number) {
  if (!confirm('确认删除该凭据及所有关联关系吗？')) return
  await deleteSSHCredential(credentialId)
  if (selectedCredentialId.value === credentialId) {
    selectedCredentialId.value = null
    sshBindings.value = []
  }
  await loadSSHCredentials()
}

async function loadCredentialBindings() {
  if (!selectedCredentialId.value) {
    sshBindings.value = []
    return
  }
  const response = await listCredentialBindings(selectedCredentialId.value)
  sshBindings.value = response.data || []
}

async function bindSelectedDevices() {
  if (!selectedCredentialId.value) {
    alert('请先选择左侧凭据')
    return
  }
  if (selectedDeviceIds.value.length === 0) {
    alert('请至少勾选一个设备')
    return
  }
  await bindCredentialDevices(selectedCredentialId.value, selectedDeviceIds.value)
  selectedDeviceIds.value = []
  await loadCredentialBindings()
}

function selectCredential(credentialId: number) {
  selectedCredentialId.value = credentialId
  loadCredentialBindings()
}

async function testBinding(binding: any) {
  if (!selectedCredentialId.value) return
  testingBindingId.value = binding.netbox_device_id
  try {
    const response = await testSSHConnectivity({
      credential_id: selectedCredentialId.value,
      netbox_device_id: binding.netbox_device_id
    })
    const result = response.data || {}
    binding.last_connectivity_status = result.status
    binding.last_connectivity_error = result.error
    binding.last_checked_at = result.checked_at
  } catch (error: any) {
    alert(error?.response?.data?.detail || '连通性检查失败')
  } finally {
    testingBindingId.value = null
  }
}

function statusText(status: string) {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    auth_failed: '认证失败',
    unknown: '未检查'
  }
  return map[status] || status
}

async function loadProviders() {
  try {
    const response = await axios.get(`${API_BASE_URL}/settings/models/providers`)
    providers.value = response.data.providers || []
  } catch (error) {
    console.error('Error loading providers:', error)
  }
}

function getProviderName(providerId: string): string {
  const provider = providers.value.find(p => p.id === providerId)
  return provider ? provider.name : providerId
}

function getProviderDescription(providerId: string): string {
  const provider = providers.value.find(p => p.id === providerId)
  return provider ? provider.description : ''
}

function getProviderExample(providerId: string): string {
  const examples: Record<string, string> = {
    'vllm': 'http://localhost:8000/v1',
    'aihubmix': 'https://api.aihubmix.com/v1',
    'openrouter': 'https://openrouter.ai/api/v1'
  }
  return examples[providerId] || ''
}

function formatParameters(params: any): string {
  if (!params || Object.keys(params).length === 0) return '默认'
  return Object.entries(params)
    .map(([key, value]) => `${key}: ${value}`)
    .join(', ')
}

function onProviderChange() {
  if (modelForm.value.provider === 'vllm') {
    modelForm.value.api_url = 'http://localhost:8000/v1'
    modelForm.value.api_key = ''
  } else if (modelForm.value.provider === 'aihubmix') {
    modelForm.value.api_url = 'https://api.aihubmix.com/v1'
  } else if (modelForm.value.provider === 'openrouter') {
    modelForm.value.api_url = 'https://openrouter.ai/api/v1'
  }
}

function editModel(model: ModelConfig) {
  editingModel.value = model
  modelForm.value = {
    name: model.name,
    provider: model.provider,
    api_key: model.api_key,
    api_url: model.api_url,
    model: model.model,
    parameters: {
      temperature: model.parameters?.temperature ?? 0.7,
      max_tokens: model.parameters?.max_tokens ?? 4096
    }
  }
  showCreateModal.value = true
}

async function saveModel() {
  if (!modelForm.value.name || !modelForm.value.provider || !modelForm.value.api_key || !modelForm.value.api_url || !modelForm.value.model) {
    alert('请填写所有必填字段')
    return
  }

  saving.value = true
  try {
    if (editingModel.value) {
      await axios.put(`${API_BASE_URL}/settings/models/${editingModel.value.id}`, {
        model_id: editingModel.value.id,
        name: modelForm.value.name,
        api_key: modelForm.value.api_key,
        api_url: modelForm.value.api_url,
        model: modelForm.value.model,
        parameters: modelForm.value.parameters
      })
    } else {
      await axios.post(`${API_BASE_URL}/settings/models`, modelForm.value)
    }

    await loadModels()
    showCreateModal.value = false
    resetForm()
  } catch (error) {
    console.error('Error saving model:', error)
    alert('保存模型失败')
  } finally {
    saving.value = false
  }
}

async function activateModel(modelId: string) {
  try {
    await axios.post(`${API_BASE_URL}/settings/models/${modelId}/activate`)
    await loadModels()
  } catch (error) {
    console.error('Error activating model:', error)
    alert('激活模型失败')
  }
}

async function deleteModel(modelId: string) {
  if (!confirm('确定要删除这个模型吗？')) {
    return
  }

  try {
    await axios.delete(`${API_BASE_URL}/settings/models/${modelId}`)
    await loadModels()
  } catch (error) {
    console.error('Error deleting model:', error)
    alert('删除模型失败')
  }
}

async function testModel(modelId: string) {
  testing.value = true
  try {
    const response = await axios.post(`${API_BASE_URL}/settings/models/${modelId}/test`)
    if (response.data.success) {
      alert('模型连接测试成功！')
    } else {
      alert(`测试失败：${response.data.message}`)
    }
  } catch (error) {
    console.error('Error testing model:', error)
    alert('测试模型失败')
  } finally {
    testing.value = false
  }
}

function resetForm() {
  modelForm.value = {
    name: '',
    provider: '',
    api_key: '',
    api_url: '',
    model: '',
    parameters: {
      temperature: 0.7,
      max_tokens: 4096
    }
  }
  editingModel.value = null
}

onMounted(() => {
  loadIntegrations()
  loadSiteOptions()
  loadLogScopes()
  loadModels()
  loadProviders()
  loadSSHCredentials()
  loadNetBoxDeviceCandidates()
  loadAutomationMode()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

.page-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  color: #4a9eff;
}

.settings-container {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.9));
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.settings-nav {
  display: flex;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  padding: 0 8px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(235, 241, 248, 0.92));
  gap: 4px;
  flex-wrap: wrap;
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 18px;
  background: none;
  border: none;
  border-radius: 14px 14px 0 0;
  font-size: 14px;
  color: #5e738f;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 600;
}

.tab-button:hover {
  color: #0f172a;
  background: rgba(59, 130, 246, 0.06);
}

.tab-button.active {
  color: #0f5ae0;
  font-weight: 600;
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.7), rgba(255, 255, 255, 0.86));
  box-shadow: inset 0 3px 0 #7dd3fc;
}

.settings-content {
  padding: 24px;
}

.mode-switch-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 24px;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.08), rgba(16, 185, 129, 0.06));
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  margin-bottom: 24px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.mode-info {
  flex: 1;
}

.mode-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.mode-title h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}

.mode-icon {
  color: #4a9eff;
}

.mode-description {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

.mode-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.mode-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.8);
  border: 1.5px solid rgba(148, 163, 184, 0.24);
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #5e738f;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.mode-button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 1);
  border-color: #4a9eff;
  color: #334155;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(74, 158, 255, 0.16);
}

.mode-button.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.92), rgba(13, 148, 136, 0.88));
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.32);
}

.mode-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-btn-icon {
  font-size: 14px;
}

.helper-banner {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(236, 246, 255, 0.9), rgba(245, 251, 255, 0.82));
  border: 1px solid rgba(125, 211, 252, 0.28);
  margin-bottom: 20px;
}

.helper-banner p {
  margin: 6px 0 0;
  color: #5c6b7a;
  font-size: 13px;
}

.banner-status {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.banner-status.ok {
  background: rgba(56, 142, 60, 0.12);
  color: #2e7d32;
}

.banner-status.warn {
  background: rgba(245, 124, 0, 0.12);
  color: #ef6c00;
}

.integration-grid {
  display: grid;
  gap: 16px;
}

.integration-card {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.92));
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.integration-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #334155;
}

.integration-source {
  font-size: 12px;
  color: #64748b;
}

.integration-footer {
  margin-top: 8px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-icon {
  color: #0f5ae0;
}

.section-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #0f5ae0 0%, #0f766e 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  box-shadow: 0 14px 26px rgba(15, 90, 224, 0.18);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 18px 34px rgba(15, 90, 224, 0.24);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.active-model-card {
  background: linear-gradient(180deg, rgba(230, 244, 255, 0.94), rgba(216, 236, 255, 0.88));
  border: 1px solid rgba(15, 90, 224, 0.24);
  border-radius: 18px;
  margin-bottom: 24px;
  box-shadow: 0 18px 34px rgba(15, 90, 224, 0.12);
}

.models-list {
  display: grid;
  gap: 16px;
}

.model-card {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  transition: all 0.3s ease;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.9));
}

.model-card.is-active {
  border-color: rgba(15, 90, 224, 0.28);
  background: linear-gradient(180deg, rgba(240, 247, 255, 0.96), rgba(255, 255, 255, 0.92));
}

.model-card:hover {
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.08);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(250, 251, 252, 0.96), rgba(245, 248, 252, 0.92));
}

.model-info {
  flex: 1;
}

.badge-container {
  margin-bottom: 8px;
}

.model-info h3 {
  margin: 0 0 6px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.model-provider {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: #5e738f;
  font-size: 13px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.badge-active {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  color: white;
  box-shadow: 0 8px 18px rgba(34, 197, 94, 0.18);
}

.card-actions {
  display: flex;
  gap: 8px;
}

.card-body {
  padding: 18px 20px;
}

.info-row {
  display: flex;
  margin-bottom: 10px;
  align-items: flex-start;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 130px;
  color: #5e738f;
  font-size: 13px;
  font-weight: 500;
}

.info-row .value {
  flex: 1;
  color: #0f172a;
  font-size: 13px;
  word-break: break-all;
  font-weight: 500;
}

.btn-test,
.btn-activate,
.btn-edit,
.btn-delete {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.btn-test {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  box-shadow: 0 8px 18px rgba(245, 158, 11, 0.18);
}

.btn-test:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(255, 152, 0, 0.4);
}

.btn-test:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-activate {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  color: white;
  box-shadow: 0 8px 18px rgba(34, 197, 94, 0.18);
}

.btn-activate:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
}

.btn-edit {
  background: linear-gradient(135deg, #0f5ae0 0%, #2563eb 100%);
  color: white;
  box-shadow: 0 8px 18px rgba(15, 90, 224, 0.18);
}

.btn-edit:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(74, 158, 255, 0.4);
}

.btn-delete {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  color: white;
  box-shadow: 0 8px 18px rgba(220, 38, 38, 0.18);
}

.btn-delete:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(244, 67, 54, 0.4);
}

.btn-add {
  background: linear-gradient(135deg, #0f5ae0 0%, #2563eb 100%);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-add:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(74, 158, 255, 0.4);
}

.btn-remove-item {
  background: rgba(244, 67, 54, 0.1);
  color: #f44336;
  border: 1px solid #f44336;
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.btn-remove-item:hover {
  background: #f44336;
  color: white;
}

.modal-large {
  max-width: 900px;
  max-height: 90vh;
}

.modal-scroll {
  max-height: calc(90vh - 180px);
  overflow-y: auto;
}

.items-section {
  margin-top: 24px;
}

.items-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.items-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.empty-items {
  text-align: center;
  padding: 40px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 2px dashed #dee2e6;
}

.empty-items p {
  margin: 12px 0 0 0;
  color: #666;
}

.item-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e9ecef;
}

.item-index {
  font-weight: 600;
  color: #4a9eff;
  font-size: 14px;
}

.item-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.section-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.section-desc {
  margin-bottom: 0;
  color: #666;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #999;
}

.empty-icon {
  color: #e8eef5;
  margin-bottom: 16px;
}

.empty-state h3 {
  color: #666;
  margin: 0 0 8px 0;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
  animation: modalIn 0.3s ease-out;
}

.modal-content.modal-large {
  max-width: 900px;
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 2px solid #e8eef5;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-title h2 {
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
}

.btn-close {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  color: #666;
  width: 36px;
  height: 36px;
  padding: 0;
  transition: all 0.3s;
}

.btn-close:hover {
  background: #e8eef5;
  color: #333;
}

.modal-body {
  padding: 24px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #333;
  font-weight: 600;
  font-size: 14px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 2px solid #e8eef5;
  border-radius: 10px;
  font-size: 14px;
  box-sizing: border-box;
  transition: all 0.3s;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #4a9eff;
  box-shadow: 0 0 0 4px rgba(74, 158, 255, 0.1);
}

.help-text {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0 0 0;
  font-size: 12px;
  color: #666;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 24px;
  border-top: 2px solid #e8eef5;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.78);
  color: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 14px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.94);
}

.ssh-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
}

.ssh-credentials-panel,
.ssh-bindings-panel {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 251, 255, 0.92) 100%);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 16px;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.05);
  padding: 16px;
}

.ssh-credentials-panel h3,
.ssh-bindings-panel h3 {
  margin-bottom: 10px;
  color: #0f172a;
}

.ssh-form {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.ssh-form input,
.ssh-form select,
.ssh-form textarea {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.credential-list {
  display: grid;
  gap: 8px;
}

.credential-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fbff;
  cursor: pointer;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-align: left;
}

.credential-item.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.credential-meta {
  color: #64748b;
  font-size: 12px;
}

.delete-credential-icon {
  color: #b91c1c;
}

.device-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.device-filter-grid input,
.device-filter-grid select {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  background: #fff;
}

.candidate-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.select-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #334155;
}

.selected-count {
  font-size: 12px;
  color: #64748b;
}

.candidate-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  margin-bottom: 10px;
}

.candidate-item {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 8px;
  align-items: center;
  padding: 6px;
  border-radius: 6px;
  border: 1px solid transparent;
}

.candidate-item:hover {
  border-color: #dbe8ff;
  background: #f8fbff;
}

.candidate-item small {
  grid-column: 2;
  color: #64748b;
}

.binding-list {
  margin-top: 12px;
  display: grid;
  gap: 8px;
}

.binding-item {
  border: 1px solid #dbe8ff;
  border-radius: 8px;
  padding: 10px 12px;
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  background: #fff;
}

.binding-title {
  font-weight: 600;
}

.binding-meta {
  font-size: 12px;
  color: #64748b;
}

.binding-status {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 8px;
  border: 1px solid #cbd5e1;
}

.binding-status.success {
  color: #166534;
  border-color: #86efac;
  background: #f0fdf4;
}

.binding-status.failed,
.binding-status.auth_failed {
  color: #991b1b;
  border-color: #fecaca;
  background: #fef2f2;
}

@media (max-width: 1024px) {
  .ssh-layout {
    grid-template-columns: 1fr;
  }

  .device-filter-grid {
    grid-template-columns: 1fr;
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
