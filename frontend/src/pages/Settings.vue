<template>
  <div class="page">
    <div class="page-content">
      <div class="page-header">
        <div class="page-title">
          <Settings class="title-icon" :size="28" />
          <h1>系统设置</h1>
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

        <!-- SSH 管理 -->
        <div v-if="currentTab === 'ssh'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <ShieldCheck class="section-icon" :size="20" />
              <h2>SSH 资产管理</h2>
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
              <div class="device-filter-bar">
                <input v-model="siteFilter" placeholder="按站点过滤" />
                <input v-model="tagFilter" placeholder="按Tag过滤" />
                <button class="btn-secondary" @click="loadNetBoxDeviceCandidates">同步NetBox设备</button>
              </div>
              <div class="candidate-list">
                <label v-for="device in candidateDevices" :key="device.id" class="candidate-item">
                  <input v-model="selectedDeviceIds" type="checkbox" :value="device.id" />
                  <span>{{ device.name }} ({{ device.primary_ip || '无IP' }})</span>
                  <small>{{ device.site }} / {{ device.role || '-' }} / {{ device.platform || '-' }}</small>
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

        <!-- 命令模板设置 -->
        <div v-if="currentTab === 'command_templates'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <Server class="section-icon" :size="20" />
              <h2>命令模板设置</h2>
            </div>
          </div>
          <div class="ssh-layout">
            <div class="ssh-credentials-panel">
              <h3>模板列表</h3>
              <div class="credential-list">
                <button
                  v-for="item in commandTemplates"
                  :key="item.id"
                  class="credential-item"
                  :class="{ active: selectedCommandTemplateId === item.id }"
                  @click="selectCommandTemplate(item.id)"
                >
                  <div>
                    <strong>{{ item.name }}</strong>
                    <div class="credential-meta">{{ item.vendor }} / {{ item.template_type }}</div>
                  </div>
                  <Trash2 :size="14" class="delete-credential-icon" @click.stop="removeCommandTemplate(item.id)" />
                </button>
              </div>
            </div>
            <div class="ssh-bindings-panel">
              <h3>{{ selectedCommandTemplateId ? '编辑模板' : '新建模板' }}</h3>
              <div class="ssh-form">
                <input v-model="commandTemplateForm.name" placeholder="模板名称，如基础信息采集" />
                <input v-model="commandTemplateForm.vendor" placeholder="厂商，如Huawei/Cisco" />
                <input v-model="commandTemplateForm.template_type" placeholder="模板类型，如diagnosis_default" />
                <textarea v-model="commandTemplateForm.description" rows="2" placeholder="模板描述"></textarea>
                <textarea v-model="commandTemplateForm.commandsText" rows="8" placeholder="每行一个命令"></textarea>
                <div style="display: flex; gap: 8px;">
                  <button class="btn-primary" @click="saveCommandTemplate">{{ selectedCommandTemplateId ? '更新模板' : '创建模板' }}</button>
                  <button class="btn-secondary" @click="resetCommandTemplateForm">重置</button>
                </div>
              </div>

              <h3 style="margin-top: 12px;">批量下发校验</h3>
              <div class="device-filter-bar">
                <input v-model="cmdDeviceSiteFilter" placeholder="按站点过滤设备" />
                <input v-model="cmdDeviceTagFilter" placeholder="按Tag过滤设备" />
                <button class="btn-secondary" @click="loadCommandTemplateDevices">加载设备</button>
              </div>
              <div class="candidate-list">
                <label v-for="device in commandTemplateDevices" :key="device.id" class="candidate-item">
                  <input v-model="selectedCommandTemplateDeviceIds" type="checkbox" :value="device.id" />
                  <span>{{ device.name }} ({{ device.vendor || '-' }})</span>
                  <small>{{ device.primary_ip || '-' }} / {{ device.site || '-' }}</small>
                </label>
              </div>
              <button class="btn-primary" @click="runCommandTemplateValidation">校验模板与设备厂商匹配</button>
              <div v-if="commandTemplateValidationResult" style="margin-top: 8px;">
                <div v-if="commandTemplateValidationResult.is_all_matched" class="binding-status success">全部匹配，可下发</div>
                <div v-else class="binding-status failed">存在厂商不匹配设备：{{ commandTemplateValidationResult.mismatched.length }} 台</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 巡检模板设置 -->
        <div v-if="currentTab === 'templates'" class="settings-content">
          <div class="section-header">
            <div class="section-title">
              <FileText class="section-icon" :size="20" />
              <h2>巡检模板</h2>
            </div>
            <div class="section-actions">
              <p class="section-desc">配置和管理网络设备巡检模板，支持连接测试</p>
              <button @click="openCreateTemplateModal" class="btn-primary">
                <Plus :size="16" />
                添加模板
              </button>
            </div>
          </div>

          <!-- 模板列表 -->
          <div class="templates-list">
            <div
              v-for="template in templates"
              :key="template.id"
              class="template-card"
            >
              <div class="template-header">
                <div class="template-info">
                  <h3>{{ template.name }}</h3>
                  <p class="template-role">{{ template.device_role }}</p>
                </div>
                <div class="template-actions">
                  <button @click="viewTemplateDetail(template.id)" class="btn-view">
                    <Info :size="14" />
                    详情
                  </button>
                  <button @click="openTestModal(template.id)" class="btn-test">
                    <Zap :size="14" />
                    测试
                  </button>
                  <button @click="editTemplate(template.id)" class="btn-edit">
                    <Pencil :size="14" />
                    编辑
                  </button>
                  <button @click="deleteTemplate(template.id)" class="btn-delete">
                    <Trash2 :size="14" />
                    删除
                  </button>
                </div>
              </div>
              <div class="template-body">
                <p class="template-desc">{{ template.description }}</p>
                <div class="template-meta">
                  <span class="meta-item">
                    <Hash :size="12" />
                    {{ template.item_count }} 个巡检项
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="templates.length === 0" class="empty-state">
            <FileText class="empty-icon" :size="64" />
            <h3>暂无巡检模板</h3>
            <p>系统正在加载巡检模板...</p>
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

    <!-- 模板详情模态框 -->
    <div v-if="showTemplateDetail" class="modal-overlay" @click.self="showTemplateDetail = false">
      <div class="modal-content modal-large">
        <div class="modal-header">
          <div class="modal-title">
            <FileText :size="20" />
            <h3>{{ selectedTemplate?.name }}</h3>
          </div>
          <button @click="showTemplateDetail = false" class="btn-close">
            <X :size="18" />
          </button>
        </div>
        <div class="modal-body">
          <div class="template-detail-info">
            <div class="info-row">
              <span class="label">设备角色:</span>
              <span class="value">{{ selectedTemplate?.device_role }}</span>
            </div>
            <div class="info-row">
              <span class="label">描述:</span>
              <span class="value">{{ selectedTemplate?.description }}</span>
            </div>
            <div class="info-row">
              <span class="label">巡检项数量:</span>
              <span class="value">{{ selectedTemplate?.items.length }}</span>
            </div>
          </div>
          
          <div class="template-items">
            <h4>巡检项列表</h4>
            <div class="items-list">
              <div 
                v-for="item in selectedTemplate?.items" 
                :key="item.id"
                class="item-card"
              >
                <div class="item-header">
                  <span class="item-name">{{ item.name }}</span>
                  <span :class="['severity-badge', getSeverityBadge(item.severity)]">
                    {{ getSeverityText(item.severity) }}
                  </span>
                </div>
                <div class="item-body">
                  <p class="item-desc">{{ item.description }}</p>
                  <div class="item-meta">
                    <span class="meta-tag category">{{ getCategoryName(item.category) }}</span>
                    <span class="meta-tag" v-if="item.device_types.length > 0">
                      {{ item.device_types.join(', ') }}
                    </span>
                  </div>
                  <div class="item-commands" v-if="item.commands.length > 0">
                    <div class="commands-label">执行命令:</div>
                    <div class="commands-list">
                      <code v-for="(cmd, idx) in item.commands" :key="idx">{{ cmd }}</code>
                    </div>
                  </div>
                  <div class="item-threshold" v-if="item.threshold">
                    <div class="threshold-label">阈值配置:</div>
                    <pre>{{ JSON.stringify(item.threshold, null, 2) }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showTemplateDetail = false" class="btn-secondary">
            <X :size="14" />
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- 模板创建/编辑弹窗 -->
    <div v-if="showCreateTemplateModal || showEditTemplateModal" class="modal-overlay" @click.self="showCreateTemplateModal = false; showEditTemplateModal = false">
      <div class="modal-content modal-large">
        <div class="modal-header">
          <div class="modal-title">
            <PlusCircle v-if="!editingTemplateId" :size="20" />
            <Pencil v-else :size="20" />
            <h3>{{ editingTemplateId ? '编辑模板' : '创建模板' }}</h3>
          </div>
          <button @click="showCreateTemplateModal = false; showEditTemplateModal = false" class="btn-close">
            <X :size="18" />
          </button>
        </div>
        <div class="modal-body modal-scroll">
          <div class="form-group">
            <label>模板ID *</label>
            <input v-model="templateForm.template_id" type="text" placeholder="例如: my_custom_template" :disabled="!!editingTemplateId" />
          </div>
          <div class="form-group">
            <label>模板名称 *</label>
            <input v-model="templateForm.name" type="text" placeholder="例如: 自定义巡检模板" />
          </div>
          <div class="form-group">
            <label>设备角色 *</label>
            <input v-model="templateForm.device_role" type="text" placeholder="例如: 核心交换机" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="templateForm.description" placeholder="模板描述" rows="2"></textarea>
          </div>

          <div class="items-section">
            <div class="items-header">
              <h4>巡检项</h4>
              <button @click="addTemplateItem" class="btn-add">
                <Plus :size="14" />
                添加巡检项
              </button>
            </div>

            <div v-if="templateForm.items.length === 0" class="empty-items">
              <FileText :size="48" />
              <p>暂无巡检项，点击上方按钮添加</p>
            </div>

            <div v-for="(item, index) in templateForm.items" :key="index" class="item-card">
              <div class="item-header">
                <span class="item-index">#{{ index + 1 }}</span>
                <button @click="removeTemplateItem(index)" class="btn-remove-item">
                  <Trash2 :size="14" />
                  删除
                </button>
              </div>
              <div class="item-body">
                <div class="form-row">
                  <div class="form-group">
                    <label>巡检项ID</label>
                    <input v-model="item.item_id" type="text" placeholder="item_id" />
                  </div>
                  <div class="form-group">
                    <label>名称</label>
                    <input v-model="item.name" type="text" placeholder="巡检项名称" />
                  </div>
                </div>
                <div class="form-group">
                  <label>描述</label>
                  <input v-model="item.description" type="text" placeholder="巡检项描述" />
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>类别</label>
                    <select v-model="item.category">
                      <option value="device_status">设备状态</option>
                      <option value="port_status">端口状态</option>
                      <option value="link_status">链路状态</option>
                      <option value="route_status">路由状态</option>
                      <option value="security_status">安全状态</option>
                    </select>
                  </div>
                  <div class="form-group">
                    <label>严重级别</label>
                    <select v-model="item.severity">
                      <option value="info">信息</option>
                      <option value="warning">警告</option>
                      <option value="error">错误</option>
                      <option value="critical">严重</option>
                    </select>
                  </div>
                </div>
                <div class="form-group">
                  <label>命令 (每行一个)</label>
                  <textarea v-model="item.commandsText" placeholder="display cpu-usage&#10;display memory-usage" rows="3" @input="updateCommands(index)"></textarea>
                </div>
                <div class="form-row">
                  <div class="form-group">
                    <label>设备类型 (逗号分隔)</label>
                    <input v-model="item.deviceTypesText" type="text" placeholder="huawei, h3c, cisco" @input="updateDeviceTypes(index)" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showCreateTemplateModal = false; showEditTemplateModal = false" class="btn-secondary">
            <X :size="14" />
            取消
          </button>
          <button @click="saveTemplate" class="btn-primary">
            <Check :size="14" />
            保存
          </button>
        </div>
      </div>
    </div>

    <!-- 模板测试模态框 -->
    <div v-if="showTestModal" class="modal-overlay" @click.self="showTestModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">
            <Zap :size="20" />
            <h3>测试巡检模板</h3>
          </div>
          <button @click="showTestModal = false" class="btn-close">
            <X :size="18" />
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>
              <Server :size="14" />
              设备IP地址 *
            </label>
            <input v-model="templateTestForm.device_ip" type="text" placeholder="请输入设备IP地址" />
          </div>
          <div class="form-group">
            <label>
              <Building2 :size="14" />
              设备类型 *
            </label>
            <select v-model="templateTestForm.device_type">
              <option value="huawei">华为 (Huawei)</option>
              <option value="h3c">华三 (H3C)</option>
              <option value="cisco">思科 (Cisco)</option>
              <option value="juniper">瞻博 (Juniper)</option>
            </select>
          </div>
          <div class="form-group">
            <label>
              <User :size="14" />
              SSH用户名 *
            </label>
            <input v-model="templateTestForm.username" type="text" placeholder="请输入SSH用户名" />
          </div>
          <div class="form-group">
            <label>
              <Key :size="14" />
              SSH密码 *
            </label>
            <input v-model="templateTestForm.password" type="password" placeholder="请输入SSH密码" />
          </div>
          <div class="form-group">
            <label>
              <Key :size="14" />
              Enable密码 (可选)
            </label>
            <input v-model="templateTestForm.enable_password" type="password" placeholder="如果需要特权模式请输入" />
          </div>

          <div v-if="testResult" class="test-result">
            <div :class="['result-status', testResult.success ? 'success' : 'error']">
              <CheckCircle2 v-if="testResult.success" :size="16" />
              <XCircle v-else :size="16" />
              {{ testResult.success ? '测试成功' : '测试失败' }}
            </div>
            <div v-if="testResult.message" class="result-message">{{ testResult.message }}</div>
            <div v-if="testResult.result" class="result-details">
              <div class="detail-item">
                <span class="detail-label">总巡检项:</span>
                <span class="detail-value">{{ testResult.result.total_items }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">通过:</span>
                <span class="detail-value success">{{ testResult.result.passed_items }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">失败:</span>
                <span class="detail-value error">{{ testResult.result.failed_items }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">警告:</span>
                <span class="detail-value warning">{{ testResult.result.warning_items }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">执行时间:</span>
                <span class="detail-value">{{ testResult.result.execution_time.toFixed(2) }}秒</span>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showTestModal = false" class="btn-secondary">
            <X :size="14" />
            取消
          </button>
          <button @click="testTemplate" class="btn-primary" :disabled="testingTemplate">
            <Loader2 v-if="testingTemplate" class="animate-spin" :size="14" />
            <Zap v-else :size="14" />
            {{ testingTemplate ? '测试中...' : '开始测试' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

import axios from 'axios'
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
  createCommandTemplate,
  deleteCommandTemplate,
  listCommandTemplates,
  updateCommandTemplate,
  validateTemplateDeployment
} from '@/api/command_templates'
import {
  Settings, Cpu, Plus, Server, Globe, Box, Sliders, CheckCircle2, Zap,
  Power, Pencil, Trash2, Building2, Key, Thermometer, Hash, X, Info,
  Loader2, Check, PlusCircle, FileText, ShieldCheck, User, XCircle
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
  { id: 'models', name: '模型设置', icon: Cpu },
  { id: 'ssh', name: 'SSH 管理', icon: ShieldCheck },
  { id: 'command_templates', name: '命令模板设置', icon: Server },
  { id: 'templates', name: '巡检模板', icon: FileText }
]

const currentTab = ref('models')
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

interface InspectionTemplate {
  id: string
  name: string
  description: string
  device_role: string
  item_count: number
}

interface TemplateDetail {
  id: string
  name: string
  description: string
  device_role: string
  items: Array<{
    id: string
    name: string
    category: string
    description: string
    commands: string[]
    severity: string
    threshold?: any
    enabled: boolean
    device_types: string[]
  }>
}

interface TemplateTestForm {
  template_id: string
  device_ip: string
  username: string
  password: string
  enable_password: string
  device_type: string
}

const templates = ref<InspectionTemplate[]>([])
const selectedTemplate = ref<TemplateDetail | null>(null)
const showTemplateDetail = ref(false)
const showTestModal = ref(false)
const showCreateTemplateModal = ref(false)
const showEditTemplateModal = ref(false)
const editingTemplateId = ref<string | null>(null)
const testingTemplate = ref(false)
const testResult = ref<any>(null)
const templateTestForm = ref<TemplateTestForm>({
  template_id: '',
  device_ip: '',
  username: '',
  password: '',
  enable_password: '',
  device_type: 'huawei'
})
const templateForm = ref({
  template_id: '',
  name: '',
  description: '',
  device_role: '',
  items: [] as any[]
})
const editingTemplateItem = ref<number | null>(null)

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

interface CommandTemplateItem {
  id: number
  name: string
  template_type: string
  vendor: string
  commands: string[]
  description?: string
  enabled: boolean
}

const commandTemplates = ref<CommandTemplateItem[]>([])
const selectedCommandTemplateId = ref<number | null>(null)
const commandTemplateForm = ref({
  name: '',
  template_type: 'diagnosis_default',
  vendor: '',
  description: '',
  commandsText: ''
})
const commandTemplateDevices = ref<any[]>([])
const cmdDeviceSiteFilter = ref('')
const cmdDeviceTagFilter = ref('')
const selectedCommandTemplateDeviceIds = ref<number[]>([])
const commandTemplateValidationResult = ref<any>(null)

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
  const response = await listSSHCredentials()
  sshCredentials.value = response.data || []
  if (!selectedCredentialId.value && sshCredentials.value.length > 0) {
    selectedCredentialId.value = sshCredentials.value[0].id
    await loadCredentialBindings()
  }
}

async function loadNetBoxDeviceCandidates() {
  const response = await queryNetBoxDevices({
    site: siteFilter.value || undefined,
    tag: tagFilter.value || undefined
  })
  candidateDevices.value = response.data || []
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

async function loadCommandTemplates() {
  const response = await listCommandTemplates()
  commandTemplates.value = response.data || []
}

function resetCommandTemplateForm() {
  selectedCommandTemplateId.value = null
  commandTemplateForm.value = {
    name: '',
    template_type: 'diagnosis_default',
    vendor: '',
    description: '',
    commandsText: ''
  }
}

function selectCommandTemplate(id: number) {
  selectedCommandTemplateId.value = id
  const item = commandTemplates.value.find(i => i.id === id)
  if (!item) return
  commandTemplateForm.value = {
    name: item.name,
    template_type: item.template_type,
    vendor: item.vendor,
    description: item.description || '',
    commandsText: (item.commands || []).join('\n')
  }
}

async function saveCommandTemplate() {
  const commands = commandTemplateForm.value.commandsText
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean)
  const payload = {
    name: commandTemplateForm.value.name,
    template_type: commandTemplateForm.value.template_type,
    vendor: commandTemplateForm.value.vendor,
    description: commandTemplateForm.value.description,
    commands
  }
  if (!payload.name || !payload.vendor || commands.length === 0) {
    alert('请填写模板名称、厂商和至少一条命令')
    return
  }
  if (selectedCommandTemplateId.value) {
    await updateCommandTemplate(selectedCommandTemplateId.value, payload)
  } else {
    await createCommandTemplate(payload)
  }
  await loadCommandTemplates()
  resetCommandTemplateForm()
}

async function removeCommandTemplate(id: number) {
  if (!confirm('确认删除该命令模板吗？')) return
  await deleteCommandTemplate(id)
  if (selectedCommandTemplateId.value === id) {
    resetCommandTemplateForm()
  }
  await loadCommandTemplates()
}

async function loadCommandTemplateDevices() {
  const response = await queryNetBoxDevices({
    site: cmdDeviceSiteFilter.value || undefined,
    tag: cmdDeviceTagFilter.value || undefined
  })
  commandTemplateDevices.value = response.data || []
}

async function runCommandTemplateValidation() {
  if (!selectedCommandTemplateId.value) {
    alert('请先选择模板')
    return
  }
  if (selectedCommandTemplateDeviceIds.value.length === 0) {
    alert('请勾选设备')
    return
  }
  const response = await validateTemplateDeployment(
    selectedCommandTemplateId.value,
    selectedCommandTemplateDeviceIds.value
  )
  commandTemplateValidationResult.value = response.data
  if (!response.data.is_all_matched) {
    alert(`存在${response.data.mismatched.length}台设备厂商不匹配，请调整后再下发`)
  }
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
    parameters: { ...model.parameters }
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
    const response = await axios.get(`${API_BASE_URL}/settings/models/test/${modelId}`)
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

async function loadTemplates() {
  try {
    // 注释掉API调用，因为automation模块已被删除
    // const response = await axios.get(`${API_BASE_URL}/automation/inspection/templates`)
    // templates.value = response.data || []
    
    // 暂时使用空数组，避免错误
    templates.value = []
    console.log('Automation module has been removed. Templates loading disabled.')
  } catch (error) {
    console.error('Error loading templates:', error)
    // alert('加载巡检模板失败')  // 注释掉alert，避免干扰用户
    templates.value = []
  }
}

async function viewTemplateDetail(templateId: string) {
  try {
    const response = await axios.get(`${API_BASE_URL}/automation/inspection/templates/${templateId}`)
    selectedTemplate.value = response.data
    showTemplateDetail.value = true
  } catch (error) {
    console.error('Error loading template detail:', error)
    alert('加载模板详情失败')
  }
}

function openTestModal(templateId: string) {
  templateTestForm.value = {
    template_id: templateId,
    device_ip: '',
    username: '',
    password: '',
    enable_password: '',
    device_type: 'huawei'
  }
  testResult.value = null
  showTestModal.value = true
}

async function testTemplate() {
  if (!templateTestForm.value.device_ip || !templateTestForm.value.username || !templateTestForm.value.password) {
    alert('请填写设备IP、用户名和密码')
    return
  }

  testingTemplate.value = true
  try {
    const response = await axios.post(
      `${API_BASE_URL}/automation/inspection/templates/${templateTestForm.value.template_id}/test`,
      {
        template_id: templateTestForm.value.template_id,
        device_ip: templateTestForm.value.device_ip,
        username: templateTestForm.value.username,
        password: templateTestForm.value.password,
        enable_password: templateTestForm.value.enable_password || undefined,
        device_type: templateTestForm.value.device_type
      }
    )
    testResult.value = response.data
    if (response.data.success) {
      alert('连接测试成功！')
    } else {
      alert(`测试失败：${response.data.message}`)
    }
  } catch (error) {
    console.error('Error testing template:', error)
    alert('测试失败：网络错误')
  } finally {
    testingTemplate.value = false
  }
}

function openCreateTemplateModal() {
  templateForm.value = {
    template_id: '',
    name: '',
    description: '',
    device_role: '',
    items: []
  }
  editingTemplateId.value = null
  showCreateTemplateModal.value = true
}

async function editTemplate(templateId: string) {
  try {
    const response = await axios.get(`${API_BASE_URL}/automation/inspection/templates/${templateId}`)
    const template = response.data
    templateForm.value = {
      template_id: template.id,
      name: template.name,
      description: template.description,
      device_role: template.device_role,
      items: template.items.map((item: any) => ({
        item_id: item.id,
        name: item.name,
        category: item.category,
        description: item.description,
        commands: item.commands,
        commandsText: item.commands.join('\n'),
        severity: item.severity,
        threshold: item.threshold,
        device_types: item.device_types,
        deviceTypesText: item.device_types.join(', '),
        enabled: item.enabled
      }))
    }
    editingTemplateId.value = templateId
    showEditTemplateModal.value = true
  } catch (error) {
    console.error('Error loading template for edit:', error)
    alert('加载模板失败')
  }
}

async function saveTemplate() {
  if (!templateForm.value.template_id || !templateForm.value.name || !templateForm.value.device_role) {
    alert('请填写模板ID、名称和设备角色')
    return
  }

  if (templateForm.value.items.length === 0) {
    alert('请至少添加一个巡检项')
    return
  }

  try {
    const templateData = {
      template_id: templateForm.value.template_id,
      name: templateForm.value.name,
      description: templateForm.value.description,
      device_role: templateForm.value.device_role,
      items: templateForm.value.items.map(item => ({
        item_id: item.item_id,
        name: item.name,
        category: item.category,
        description: item.description,
        commands: item.commands,
        severity: item.severity,
        threshold: item.threshold,
        device_types: item.device_types,
        enabled: item.enabled
      }))
    }

    if (editingTemplateId.value) {
      await axios.put(`${API_BASE_URL}/automation/inspection/templates/${editingTemplateId.value}`, templateData)
      alert('模板更新成功')
    } else {
      await axios.post(`${API_BASE_URL}/automation/inspection/templates`, templateData)
      alert('模板创建成功')
    }
    showCreateTemplateModal.value = false
    showEditTemplateModal.value = false
    await loadTemplates()
  } catch (error) {
    console.error('Error saving template:', error)
    alert('保存模板失败')
  }
}

async function deleteTemplate(templateId: string) {
  if (!confirm('确定要删除这个模板吗？')) {
    return
  }

  try {
    await axios.delete(`${API_BASE_URL}/automation/inspection/templates/${templateId}`)
    alert('模板删除成功')
    await loadTemplates()
  } catch (error) {
    console.error('Error deleting template:', error)
    alert('删除模板失败')
  }
}

function addTemplateItem() {
  const newItem = {
    item_id: `item_${Date.now()}`,
    name: '新巡检项',
    category: 'device_status',
    description: '巡检项描述',
    commands: ['display command'],
    severity: 'info',
    threshold: {},
    device_types: ['huawei'],
    enabled: true
  }
  templateForm.value.items.push(newItem)
}

function removeTemplateItem(index: number) {
  templateForm.value.items.splice(index, 1)
}

function getCategoryName(category: string): string {
  const categoryMap: Record<string, string> = {
    device_status: '设备状态',
    port_status: '端口状态',
    link_status: '链路状态',
    route_status: '路由状态',
    security_status: '安全状态'
  }
  return categoryMap[category] || category
}

function updateCommands(index: number) {
  const item = templateForm.value.items[index]
  item.commands = item.commandsText.split('\n').filter(cmd => cmd.trim())
}

function updateDeviceTypes(index: number) {
  const item = templateForm.value.items[index]
  item.device_types = item.deviceTypesText.split(',').map(t => t.trim()).filter(t => t)
}

function getSeverityBadge(severity: string): string {
  const severityMap: Record<string, string> = {
    info: 'info',
    warning: 'warning',
    error: 'error',
    critical: 'critical'
  }
  return severityMap[severity] || 'info'
}

function getSeverityText(severity: string): string {
  const severityMap: Record<string, string> = {
    info: '信息',
    warning: '警告',
    error: '错误',
    critical: '严重'
  }
  return severityMap[severity] || severity
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
  loadModels()
  loadProviders()
  loadTemplates()
  loadSSHCredentials()
  loadNetBoxDeviceCandidates()
  loadCommandTemplates()
  loadCommandTemplateDevices()
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

.page-header h1 {
  color: #333;
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}

.settings-container {
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.settings-nav {
  display: flex;
  border-bottom: 2px solid #e8eef5;
  padding: 0 8px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 500;
}

.tab-button:hover {
  color: #333;
  background: rgba(74, 158, 255, 0.05);
}

.tab-button.active {
  color: #4a9eff;
  border-bottom-color: #4a9eff;
  font-weight: 600;
  background: rgba(74, 158, 255, 0.1);
}

.settings-content {
  padding: 24px;
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
  color: #4a9eff;
}

.section-header h2 {
  margin: 0;
  color: #333;
  font-size: 18px;
  font-weight: 600;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.active-model-card {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border: 2px solid #4a9eff;
  border-radius: 12px;
  margin-bottom: 24px;
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.2);
}

.models-list {
  display: grid;
  gap: 16px;
}

.model-card {
  border: 2px solid #e8eef5;
  border-radius: 12px;
  transition: all 0.3s ease;
  overflow: hidden;
}

.model-card.is-active {
  border-color: #4a9eff;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
}

.model-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 20px;
  border-bottom: 1px solid #e8eef5;
  background: linear-gradient(135deg, #fafbfc 0%, #f5f5f5 100%);
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
  color: #666;
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
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
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
  color: #666;
  font-size: 13px;
  font-weight: 500;
}

.info-row .value {
  flex: 1;
  color: #333;
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
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(255, 152, 0, 0.3);
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
  background: linear-gradient(135deg, #4caf50 0%, #388e3c 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
}

.btn-activate:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(76, 175, 80, 0.4);
}

.btn-edit {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(74, 158, 255, 0.3);
}

.btn-edit:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(74, 158, 255, 0.4);
}

.btn-delete {
  background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
  color: white;
  box-shadow: 0 2px 4px rgba(244, 67, 54, 0.3);
}

.btn-delete:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(244, 67, 54, 0.4);
}

.btn-add {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
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

/* 模板样式 */
.templates-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.template-card {
  background: white;
  border: 2px solid #e8eef5;
  border-radius: 12px;
  padding: 20px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.template-card:hover {
  border-color: #4a9eff;
  box-shadow: 0 4px 12px rgba(74, 158, 255, 0.15);
  transform: translateY(-2px);
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  margin-bottom: 12px;
}

.template-info h3 {
  margin: 0 0 6px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.template-role {
  margin: 0;
  color: #666;
  font-size: 13px;
}

.template-actions {
  display: flex;
  gap: 8px;
}

.btn-view,
.btn-test {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-view {
  background: #f5f5f5;
  color: #333;
}

.btn-view:hover {
  background: #e8eef5;
}

.btn-test {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
}

.btn-test:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
}

.template-body {
  padding-top: 12px;
  border-top: 1px solid #e8eef5;
}

.template-desc {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
}

.template-meta {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #999;
  font-size: 13px;
}

/* 模板详情样式 */
.template-detail-info {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 20px;
}

.template-detail-info .info-row {
  display: flex;
  margin-bottom: 12px;
}

.template-detail-info .info-row:last-child {
  margin-bottom: 0;
}

.template-detail-info .label {
  min-width: 100px;
  color: #666;
  font-size: 14px;
  font-weight: 500;
}

.template-detail-info .value {
  flex: 1;
  color: #333;
  font-size: 14px;
}

.template-items h4 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item-card {
  background: #f8f9fa;
  border: 1px solid #e8eef5;
  border-radius: 10px;
  padding: 16px;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.item-name {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.severity-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.severity-badge.info {
  background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%);
}

.severity-badge.warning {
  background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
  color: #333;
}

.severity-badge.error {
  background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
}

.severity-badge.critical {
  background: linear-gradient(135deg, #d32f2f 0%, #b71c1c 100%);
}

.item-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.item-desc {
  margin: 0;
  color: #666;
  font-size: 13px;
}

.item-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  background: #e8eef5;
  border-radius: 12px;
  font-size: 12px;
  color: #666;
}

.meta-tag.category {
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%);
  color: white;
}

.item-commands,
.item-threshold {
  background: white;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e8eef5;
}

.commands-label,
.threshold-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
}

.commands-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.commands-list code {
  background: #f5f5f5;
  padding: 6px 10px;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #333;
}

.item-threshold pre {
  margin: 0;
  font-size: 12px;
  color: #333;
}

/* 测试结果样式 */
.test-result {
  background: #f8f9fa;
  border-radius: 10px;
  padding: 16px;
  margin-top: 16px;
}

.result-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  font-weight: 600;
  margin-bottom: 12px;
}

.result-status.success {
  background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
  color: #155724;
}

.result-status.error {
  background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
  color: #721c24;
}

.result-message {
  color: #666;
  font-size: 14px;
  margin-bottom: 12px;
}

.result-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
}

.detail-label {
  color: #666;
  font-size: 13px;
}

.detail-value {
  font-weight: 600;
  font-size: 13px;
}

.detail-value.success {
  color: #4caf50;
}

.detail-value.error {
  color: #f44336;
}

.detail-value.warning {
  color: #ff9800;
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
  background: #f5f5f5;
  color: #333;
  border: 2px solid #e8eef5;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-secondary:hover {
  background: #e8eef5;
}

.ssh-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
}

.ssh-credentials-panel,
.ssh-bindings-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  padding: 16px;
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
  background: #fff;
  cursor: pointer;
  padding: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-align: left;
}

.credential-item.active {
  border-color: #0f766e;
  background: #f0fdfa;
}

.credential-meta {
  color: #64748b;
  font-size: 12px;
}

.delete-credential-icon {
  color: #b91c1c;
}

.device-filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.device-filter-bar input {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px;
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
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px;
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
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
