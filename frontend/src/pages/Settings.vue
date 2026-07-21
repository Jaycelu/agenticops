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
  min-height: 100%;
}

.page-content {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: var(--app-grid-gap);
}

.settings-container,
.integration-card,
.active-model-card,
.model-card,
.ssh-credentials-panel,
.ssh-bindings-panel,
.item-card,
.modal-content {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  box-shadow: none;
}

.settings-container {
  overflow: hidden;
}

.settings-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 0 8px;
  background: var(--app-surface-subtle);
  border-bottom: 1px solid var(--app-border);
}

.tab-button,
.mode-button,
.btn-primary,
.btn-secondary,
.btn-test,
.btn-activate,
.btn-edit,
.btn-delete,
.btn-add,
.btn-remove-item,
.btn-close {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: var(--app-radius-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: color var(--app-transition-fast), background var(--app-transition-fast), border-color var(--app-transition-fast), opacity var(--app-transition-fast);
}

.tab-button {
  min-height: 44px;
  padding: 11px 14px;
  color: var(--app-text-soft);
  background: transparent;
  border-radius: 0;
}

.tab-button:hover,
.btn-secondary:hover,
.btn-close:hover {
  color: var(--app-text);
  background: var(--app-surface-subtle);
  border-color: var(--app-border-strong);
}

.tab-button.active {
  color: var(--app-primary);
  background: var(--app-surface);
  box-shadow: inset 0 -3px 0 var(--app-primary);
}

.settings-content {
  padding: 18px;
}

.section-header,
.card-header,
.toggle-row,
.candidate-toolbar,
.binding-item,
.items-header,
.modal-header,
.modal-footer,
.mode-switch-banner,
.helper-banner,
.mode-title,
.section-title,
.model-provider,
.info-row .label,
.form-group label,
.help-text,
.select-all {
  display: flex;
  align-items: center;
}

.section-header,
.card-header,
.toggle-row,
.candidate-toolbar,
.modal-header {
  justify-content: space-between;
}

.section-header {
  margin-bottom: 18px;
}

.section-title,
.mode-title,
.model-provider,
.info-row .label,
.form-group label,
.help-text,
.select-all {
  gap: 7px;
}

.section-icon,
.mode-icon,
.title-icon,
.item-index {
  color: var(--app-primary);
}

.mode-switch-banner,
.helper-banner {
  justify-content: space-between;
  gap: 18px;
  padding: 15px 16px;
  margin-bottom: 18px;
  background: var(--app-surface-subtle);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.mode-info,
.model-info,
.info-row .value,
.binding-main {
  flex: 1;
}

.mode-title h3,
.model-info h3,
.ssh-credentials-panel h3,
.ssh-bindings-panel h3,
.modal-title h2,
.items-header h4 {
  margin: 0;
  color: var(--app-text);
  font-size: 16px;
  font-weight: 650;
}

.mode-description,
.model-provider,
.integration-source,
.credential-meta,
.binding-meta,
.candidate-item small,
.selected-count,
.help-text,
.section-desc,
.empty-items p,
.empty-state p {
  color: var(--app-text-soft);
  font-size: 12px;
}

.mode-controls,
.card-actions,
.section-actions,
.modal-footer {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mode-button,
.btn-secondary,
.btn-close {
  color: var(--app-text);
  background: var(--app-surface);
  border-color: var(--app-border-strong);
}

.mode-button.active,
.btn-primary,
.btn-edit,
.btn-add {
  color: var(--app-text-inverse);
  background: var(--app-primary);
  border-color: var(--app-primary);
}

.btn-test {
  color: var(--app-text-inverse);
  background: var(--app-warning);
  border-color: var(--app-warning);
}

.btn-activate {
  color: var(--app-text-inverse);
  background: var(--app-success);
  border-color: var(--app-success);
}

.btn-delete,
.btn-remove-item {
  color: var(--app-text-inverse);
  background: var(--app-danger);
  border-color: var(--app-danger);
}

button:disabled,
.mode-button:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.integration-grid,
.models-list,
.credential-list,
.ssh-form,
.binding-list,
.item-body {
  display: grid;
  gap: 10px;
}

.integration-grid,
.models-list {
  gap: 14px;
}

.integration-card,
.active-model-card,
.model-card {
  overflow: hidden;
}

.active-model-card,
.model-card.is-active {
  background: var(--app-primary-soft);
  border-color: var(--app-border-strong);
}

.model-card:hover,
.credential-item:hover,
.candidate-item:hover {
  background: var(--app-surface-subtle);
  border-color: var(--app-border-strong);
}

.card-header {
  gap: 12px;
  padding: 16px 18px;
  align-items: flex-start;
  background: var(--app-surface-subtle);
  border-bottom: 1px solid var(--app-border);
}

.card-body {
  padding: 16px 18px;
}

.integration-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.toggle-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text);
  font-weight: 600;
}

.integration-footer,
.items-section,
.binding-list {
  margin-top: 12px;
}

.info-row {
  gap: 12px;
  margin-bottom: 10px;
  align-items: flex-start;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  min-width: 130px;
  color: var(--app-text-soft);
  font-weight: 600;
}

.info-row .value {
  color: var(--app-text);
  word-break: break-all;
}

.badge,
.banner-status,
.binding-status {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  gap: 5px;
  padding: 3px 7px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  color: var(--app-text-soft);
  background: var(--app-surface-subtle);
  font-size: 12px;
  font-weight: 600;
}

.badge-active,
.banner-status.ok,
.binding-status.success {
  color: var(--app-success);
  background: var(--app-success-soft);
  border-color: var(--app-border);
}

.banner-status.warn {
  color: var(--app-warning);
  background: var(--app-warning-soft);
}

.binding-status.failed,
.binding-status.auth_failed {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}

.ssh-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
}

.ssh-credentials-panel,
.ssh-bindings-panel {
  padding: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  margin-bottom: 7px;
  color: var(--app-text);
  font-weight: 600;
}

.form-group input,
.form-group select,
.form-group textarea,
.ssh-form input,
.ssh-form select,
.ssh-form textarea,
.device-filter-grid input,
.device-filter-grid select {
  width: 100%;
  min-height: 36px;
  padding: 8px 10px;
  color: var(--app-text);
  background: var(--app-surface);
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-sm);
  font: inherit;
  transition: border-color var(--app-transition-fast), box-shadow var(--app-transition-fast);
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus,
.ssh-form input:focus,
.ssh-form select:focus,
.ssh-form textarea:focus,
.device-filter-grid input:focus,
.device-filter-grid select:focus {
  outline: none;
  border-color: var(--app-primary);
  box-shadow: var(--app-focus);
}

.credential-item,
.candidate-item,
.binding-item,
.empty-items {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.credential-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  text-align: left;
  cursor: pointer;
}

.credential-item.active,
.candidate-item:has(input:checked) {
  background: var(--app-primary-soft);
  border-color: var(--app-border-strong);
}

.delete-credential-icon {
  color: var(--app-danger);
}

.device-filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.candidate-list {
  max-height: 220px;
  overflow-y: auto;
  padding: 8px;
  margin-bottom: 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.candidate-item {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 8px;
  align-items: center;
  padding: 6px;
}

.candidate-item small {
  grid-column: 2;
}

.binding-item {
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  padding: 10px 12px;
}

.binding-title {
  font-weight: 650;
}

.items-header {
  justify-content: space-between;
  margin-bottom: 14px;
}

.empty-items,
.empty-state {
  padding: 40px;
  color: var(--app-text-muted);
  text-align: center;
}

.item-card {
  padding: 14px;
  margin-bottom: 14px;
  background: var(--app-surface-subtle);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--app-border);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-bg-deep);
}

.modal-content {
  width: min(600px, 90vw);
  max-height: 90vh;
  overflow-y: auto;
}

.modal-content.modal-large,
.modal-large {
  width: min(900px, 92vw);
  max-width: 900px;
}

.modal-scroll {
  max-height: calc(90vh - 180px);
  overflow-y: auto;
}

.modal-header,
.modal-footer {
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--app-border);
}

.modal-footer {
  justify-content: flex-end;
  border-top: 1px solid var(--app-border);
  border-bottom: 0;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.modal-body {
  padding: 18px 20px 22px;
}

.btn-close {
  width: 36px;
  height: 36px;
  padding: 0;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 1024px) {
  .ssh-layout,
  .device-filter-grid,
  .form-row {
    grid-template-columns: 1fr;
  }

  .card-header,
  .mode-switch-banner,
  .helper-banner,
  .binding-item {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
