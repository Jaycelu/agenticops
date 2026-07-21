<template>
  <div class="page app-page">
    <div class="page-content">
      <div class="page-header app-page-header">
        <div class="page-title app-page-title">
          <span class="app-page-title-icon">
            <Server :size="24" />
          </span>
          <div class="app-page-copy">
            <h1>资产视图</h1>
          </div>
        </div>
        <button @click="showColumnSettings = true" class="app-button app-button-secondary">
          <Settings2 :size="16" />
          列设置
        </button>
      </div>

      <div class="content-layout">
        <!-- 左侧导航 -->
        <div class="sidebar">
          <div class="nav-item" :class="{ active: activeTab === 'devices' }" @click="switchTab('devices')">
            <div class="nav-icon">
              <Monitor :size="22" />
            </div>
            <div class="nav-text">
              <div class="nav-title">设备</div>
              <div class="nav-count">{{ deviceCount }} 台</div>
            </div>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'ips' }" @click="switchTab('ips')">
            <div class="nav-icon">
              <Globe :size="22" />
            </div>
            <div class="nav-text">
              <div class="nav-title">IP地址</div>
              <div class="nav-count">{{ ipCount }} 个</div>
            </div>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'racks' }" @click="switchTab('racks')">
            <div class="nav-icon">
              <HardDrive :size="22" />
            </div>
            <div class="nav-text">
              <div class="nav-title">机柜</div>
              <div class="nav-count">{{ rackCount }} 个</div>
            </div>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'vlans' }" @click="switchTab('vlans')">
            <div class="nav-icon">
              <Network :size="22" />
            </div>
            <div class="nav-text">
              <div class="nav-title">VLAN</div>
              <div class="nav-count">{{ vlanCount }} 个</div>
            </div>
          </div>
          <div class="nav-item" :class="{ active: activeTab === 'prefixes' }" @click="switchTab('prefixes')">
            <div class="nav-icon">
              <Router :size="22" />
            </div>
            <div class="nav-text">
              <div class="nav-title">前缀</div>
              <div class="nav-count">{{ prefixCount }} 个</div>
            </div>
          </div>
        </div>

        <!-- 右侧内容 -->
        <div class="main-area">
          <!-- 设备视图 -->
          <div v-if="activeTab === 'devices' && !showDeviceDetail" class="tab-content">
            <div class="filter-section">
              <div class="filter-group">
                <div class="filter-input-wrapper">
                  <Search class="filter-icon" :size="16" />
                  <input
                    v-model="deviceFilters.name"
                    placeholder="设备名称"
                    class="app-input filter-text"
                    @input="debouncedLoadDevices"
                  />
                </div>
                <select v-model="deviceFilters.site" class="app-select filter-select" @change="loadDevices">
                  <option value="">所有站点</option>
                  <option v-for="site in sites" :key="site.name" :value="site.name">
                    {{ site.name }}
                  </option>
                </select>
                <select v-model="deviceFilters.role" class="app-select filter-select" @change="loadDevices">
                  <option value="">所有角色</option>
                  <option value="核心交换机">核心交换机</option>
                  <option value="接入交换机">接入交换机</option>
                  <option value="汇聚交换机">汇聚交换机</option>
                  <option value="防火墙">防火墙</option>
                </select>
                <select v-model="deviceFilters.vendor" class="app-select filter-select" @change="loadDevices">
                  <option value="">所有厂商</option>
                  <option v-for="vendor in vendors" :key="vendor" :value="vendor">
                    {{ vendor }}
                  </option>
                </select>
                <button @click="loadDevices" class="app-button app-button-primary">
                  <Search :size="16" />
                  搜索
                </button>
                <button @click="resetDeviceFilters" class="app-button app-button-secondary">
                  <RotateCcw :size="16" />
                  重置
                </button>
              </div>
            </div>

            <div class="table-section">
              <div v-if="tabLoading.devices" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="devices.length === 0" class="empty app-empty">
                <MonitorOff :size="48" />
                <p>暂无设备数据</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in visibleDeviceColumns" :key="col.key">
                      {{ col.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="device in devices" :key="device.id">
                    <td v-for="col in visibleDeviceColumns" :key="col.key">
                      <span v-if="col.key === 'status'" :class="['app-badge', getStatusClass(device[col.key])]">
                        <component :is="getStatusIcon(device[col.key])" :size="12" />
                        {{ device[col.key] || '-' }}
                      </span>
                      <span v-else-if="col.key === 'action'">
                        <button @click="handleViewDetails(device, 'device')" class="app-button app-button-primary btn-table">
                          <Eye :size="14" />
                          详情
                        </button>
                      </span>
                      <span v-else-if="col.key === 'vendor'" :class="['app-badge', getVendorClass(device.vendor)]">
                        <span class="vendor-dot"></span>
                        {{ device.vendor || '-' }}
                      </span>
                      <span v-else-if="col.key === 'name'">
                        <a @click="openDeviceDetail(device)" class="link-text">{{ device[col.key] || '-' }}</a>
                      </span>
                      <span v-else>{{ device[col.key] || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 设备详情视图 -->
          <div v-if="activeTab === 'devices' && showDeviceDetail && selectedDevice" class="tab-content">
            <div class="rack-detail-header">
              <button @click="closeDeviceDetail" class="app-button app-button-secondary">
                <ArrowLeft :size="16" />
                返回
              </button>
              <h2>设备详情 - {{ selectedDevice.name }}</h2>
            </div>

            <div class="rack-info-section">
              <div class="section-header">
                <Info :size="18" />
                <h3>设备信息</h3>
              </div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">设备名称:</span>
                  <span class="info-value">{{ selectedDevice.name || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">设备类型:</span>
                  <span class="info-value">{{ selectedDevice.device_type || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">所属站点:</span>
                  <span class="info-value">{{ selectedDevice.site || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">设备角色:</span>
                  <span class="info-value">{{ selectedDevice.role || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">厂商:</span>
                  <span :class="['app-badge', getVendorClass(selectedDevice.vendor)]">
                    <span class="vendor-dot"></span>
                    {{ selectedDevice.vendor || '-' }}
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">状态:</span>
                  <span :class="['info-value', 'app-badge', getStatusClass(selectedDevice.status)]">
                    <component :is="getStatusIcon(selectedDevice.status)" :size="12" />
                    {{ selectedDevice.status || '-' }}
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">主IP地址:</span>
                  <span class="info-value">{{ selectedDevice.primary_ip || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">序列号:</span>
                  <span class="info-value">{{ selectedDevice.serial || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">所属机柜:</span>
                  <span class="info-value">{{ selectedDevice.rack || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">位置(U):</span>
                  <span class="info-value">{{ selectedDevice.position || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">面向:</span>
                  <span class="info-value">{{ selectedDevice.face || '-' }}</span>
                </div>
                <div class="info-item full-width">
                  <span class="info-label">设备标签:</span>
                  <div class="tags-container">
                    <span v-if="selectedDevice.tags && selectedDevice.tags.length > 0" class="tags-list">
                      <span v-for="tag in selectedDevice.tags" :key="tag" :class="['app-badge', getTagClass(tag)]">
                        <Tag :size="12" />
                        {{ tag }}
                      </span>
                    </span>
                    <span v-else class="info-value">无标签</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="device-config-section">
              <div class="section-header">
                <Settings2 :size="18" />
                <h3>设备配置</h3>
                <div class="config-actions">
                  <button v-if="!deviceConfig" @click="loadDeviceConfig" class="app-button app-button-primary">
                    <Download :size="14" />
                    查看配置
                  </button>
                  <button v-else @click="loadDeviceConfig" class="app-button app-button-primary">
                    <RefreshCw :size="14" />
                    刷新配置
                  </button>
                  <button @click="showCredentialsDialog = true" class="app-button app-button-primary">
                    <Upload :size="14" />
                    获取并写入NetBox
                  </button>
                </div>
              </div>
              <div v-if="loadingConfig" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载配置中...</p>
              </div>
              <div v-else-if="!deviceConfig" class="empty-config app-empty">
                <FileX :size="48" />
                <p>暂无配置信息，点击上方按钮获取</p>
              </div>
              <div v-else class="config-content">
                <div v-if="!deviceConfig.has_config" class="empty-config app-empty">
                  <FileX :size="48" />
                  <p>该设备暂无配置信息</p>
                </div>
                <div v-else>
                  <div v-if="deviceConfig.config_context && deviceConfig.config_context.running_config" class="config-section">
                    <h4>设备配置</h4>
                    <pre class="config-text">{{ deviceConfig.config_context.running_config }}</pre>
                  </div>
                  <div v-else class="empty-config app-empty">
                    <FileX :size="48" />
                    <p>该设备暂无运行配置</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- IP地址视图 -->
          <div v-if="activeTab === 'ips'" class="tab-content">
            <div class="filter-section">
              <div class="filter-group">
                <div class="filter-input-wrapper">
                  <Search class="filter-icon" :size="16" />
                  <input
                    v-model="ipFilters.address"
                    placeholder="IP地址"
                    class="app-input filter-text"
                    @input="debouncedLoadIPs"
                  />
                </div>
                <select v-model="ipFilters.status" class="app-select filter-select" @change="loadIPs">
                  <option value="">所有状态</option>
                  <option value="Active">Active</option>
                  <option value="Reserved">Reserved</option>
                  <option value="Deprecated">Deprecated</option>
                  <option value="DHCP">DHCP</option>
                </select>
                <button @click="loadIPs" class="app-button app-button-primary">
                  <Search :size="16" />
                  搜索
                </button>
                <button @click="resetIPFilters" class="app-button app-button-secondary">
                  <RotateCcw :size="16" />
                  重置
                </button>
              </div>
            </div>

            <div class="table-section">
              <div v-if="tabLoading.ips" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="ips.length === 0" class="empty app-empty">
                <FileX :size="48" />
                <p>暂无IP数据</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in visibleIPColumns" :key="col.key">
                      {{ col.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ip in ips" :key="ip.id">
                    <td v-for="col in visibleIPColumns" :key="col.key">
                      <span v-if="col.key === 'status'" :class="['app-badge', getStatusClass(ip[col.key])]">
                        <component :is="getStatusIcon(ip[col.key])" :size="12" />
                        {{ ip[col.key] || '-' }}
                      </span>
                      <span v-else>{{ ip[col.key] || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 机柜视图 -->
          <div v-if="activeTab === 'racks' && !showRackDetail" class="tab-content">
            <div class="filter-section">
              <div class="filter-group">
                <div class="filter-input-wrapper">
                  <Search class="filter-icon" :size="16" />
                  <input
                    v-model="rackFilters.name"
                    placeholder="机柜名称"
                    class="app-input filter-text"
                    @input="debouncedLoadRacks"
                  />
                </div>
                <select v-model="rackFilters.site" class="app-select filter-select" @change="loadRacks">
                  <option value="">所有站点</option>
                  <option v-for="site in sites" :key="site.name" :value="site.name">
                    {{ site.name }}
                  </option>
                </select>
                <button @click="loadRacks" class="app-button app-button-primary">
                  <Search :size="16" />
                  搜索
                </button>
                <button @click="resetRackFilters" class="app-button app-button-secondary">
                  <RotateCcw :size="16" />
                  重置
                </button>
              </div>
            </div>

            <div class="table-section">
              <div v-if="tabLoading.racks" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="racks.length === 0" class="empty app-empty">
                <HardDriveOff :size="48" />
                <p>暂无机柜数据</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in visibleRackColumns" :key="col.key">
                      {{ col.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="rack in racks" :key="rack.id">
                    <td v-for="col in visibleRackColumns" :key="col.key">
                      <span v-if="col.key === 'status'" :class="['app-badge', getStatusClass(rack[col.key])]">
                        <component :is="getStatusIcon(rack[col.key])" :size="12" />
                        {{ rack[col.key] || '-' }}
                      </span>
                      <span v-else-if="col.key === 'action'">
                        <button @click="handleViewDetails(rack, 'rack')" class="app-button app-button-primary btn-table">
                          <Eye :size="14" />
                          详情
                        </button>
                      </span>
                      <span v-else-if="col.key === 'name'">
                        <a @click="openRackDetail(rack)" class="link-text">{{ rack.name || '-' }}</a>
                      </span>
                      <span v-else>{{ rack[col.key] || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 机柜详情视图 -->
          <div v-if="showRackDetail && selectedRack" class="tab-content">
            <div class="rack-detail-header">
              <button @click="closeRackDetail" class="app-button app-button-secondary">
                <ArrowLeft :size="16" />
                返回
              </button>
              <h2>机柜详情 - {{ selectedRack.name }}</h2>
            </div>

            <div class="rack-info-section">
              <div class="section-header">
                <Info :size="18" />
                <h3>机柜信息</h3>
              </div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">机柜名称:</span>
                  <span class="info-value">{{ selectedRack.name || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">所属站点:</span>
                  <span class="info-value">{{ selectedRack.site || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">位置:</span>
                  <span class="info-value">{{ selectedRack.location || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">状态:</span>
                  <span :class="['info-value', 'app-badge', getStatusClass(selectedRack.status)]">
                    <component :is="getStatusIcon(selectedRack.status)" :size="12" />
                    {{ selectedRack.status || '-' }}
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">高度(U):</span>
                  <span class="info-value">{{ selectedRack.u_height || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">宽度:</span>
                  <span class="info-value">{{ selectedRack.width || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">角色:</span>
                  <span class="info-value">{{ selectedRack.role || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">资产标签:</span>
                  <span class="info-value">{{ selectedRack.asset_tag || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="rack-devices-section">
              <div class="section-header">
                <Monitor :size="18" />
                <h3>机柜内设备 ({{ rackDevices.length }} 台)</h3>
              </div>
              <div v-if="loading" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="rackDevices.length === 0" class="empty app-empty">
                <MonitorOff :size="48" />
                <p>该机柜内暂无设备</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th>设备名称</th>
                    <th>设备类型</th>
                    <th>设备角色</th>
                    <th>状态</th>
                    <th>位置(U)</th>
                    <th>面向</th>
                    <th>主IP地址</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="device in rackDevices" :key="device.id">
                    <td>
                      <a @click="openDeviceDetail(device)" class="link-text">{{ device.name || '-' }}</a>
                    </td>
                    <td>{{ device.device_type || '-' }}</td>
                    <td>{{ device.role || '-' }}</td>
                    <td>
                      <span :class="['app-badge', getStatusClass(device.status)]">
                        <component :is="getStatusIcon(device.status)" :size="12" />
                        {{ device.status || '-' }}
                      </span>
                    </td>
                    <td>{{ device.position || '-' }}</td>
                    <td>{{ device.face || '-' }}</td>
                    <td>{{ device.primary_ip || '-' }}</td>
                    <td>
                      <button @click="openDeviceDetail(device)" class="app-button app-button-primary btn-table">
                        <Eye :size="14" />
                        详情
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- VLAN视图 -->
          <div v-if="activeTab === 'vlans'" class="tab-content">
            <div class="filter-section">
              <div class="filter-group">
                <div class="filter-input-wrapper">
                  <Search class="filter-icon" :size="16" />
                  <input
                    v-model="vlanFilters.name"
                    placeholder="VLAN名称"
                    class="app-input filter-text"
                    @input="debouncedLoadVLANs"
                  />
                </div>
                <select v-model="vlanFilters.site" class="app-select filter-select" @change="loadVLANs">
                  <option value="">所有站点</option>
                  <option v-for="site in sites" :key="site.name" :value="site.name">
                    {{ site.name }}
                  </option>
                </select>
                <select v-model="vlanFilters.status" class="app-select filter-select" @change="loadVLANs">
                  <option value="">所有状态</option>
                  <option value="active">活跃</option>
                  <option value="reserved">保留</option>
                  <option value="deprecated">已废弃</option>
                </select>
                <button @click="loadVLANs" class="app-button app-button-primary">
                  <Search :size="16" />
                  搜索
                </button>
                <button @click="resetVLANFilters" class="app-button app-button-secondary">
                  <RotateCcw :size="16" />
                  重置
                </button>
              </div>
            </div>

            <div class="table-section">
              <div v-if="tabLoading.vlans" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="vlans.length === 0" class="empty app-empty">
                <FileX :size="48" />
                <p>暂无VLAN数据</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in visibleVLANColumns" :key="col.key">
                      {{ col.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="vlan in vlans" :key="vlan.id">
                    <td v-for="col in visibleVLANColumns" :key="col.key">
                      <span v-if="col.key === 'status'" :class="['app-badge', getStatusClass(vlan[col.key])]">
                        <component :is="getStatusIcon(vlan[col.key])" :size="12" />
                        {{ vlan[col.key] || '-' }}
                      </span>
                      <span v-else>{{ vlan[col.key] || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 前缀视图 -->
          <div v-if="activeTab === 'prefixes' && !showPrefixDetail" class="tab-content">
            <div class="filter-section">
              <div class="filter-group">
                <div class="filter-input-wrapper">
                  <Search class="filter-icon" :size="16" />
                  <input
                    v-model="prefixFilters.prefix"
                    placeholder="前缀地址"
                    class="app-input filter-text"
                    @input="debouncedLoadPrefixes"
                  />
                </div>
                <select v-model="prefixFilters.site" class="app-select filter-select" @change="loadPrefixes">
                  <option value="">所有站点</option>
                  <option v-for="site in sites" :key="site.name" :value="site.name">
                    {{ site.name }}
                  </option>
                </select>
                <select v-model="prefixFilters.family" class="app-select filter-select" @change="loadPrefixes">
                  <option value="">所有协议</option>
                  <option value="4">IPv4</option>
                  <option value="6">IPv6</option>
                </select>
                <select v-model="prefixFilters.status" class="app-select filter-select" @change="loadPrefixes">
                  <option value="">所有状态</option>
                  <option value="active">活跃</option>
                  <option value="reserved">保留</option>
                  <option value="deprecated">已废弃</option>
                </select>
                <button @click="loadPrefixes" class="app-button app-button-primary">
                  <Search :size="16" />
                  搜索
                </button>
                <button @click="resetPrefixFilters" class="app-button app-button-secondary">
                  <RotateCcw :size="16" />
                  重置
                </button>
              </div>
            </div>

            <div class="table-section">
              <div v-if="tabLoading.prefixes" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="prefixes.length === 0" class="empty app-empty">
                <RouterOff :size="48" />
                <p>暂无前缀数据</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th v-for="col in visiblePrefixColumns" :key="col.key">
                      {{ col.label }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="prefix in prefixes" :key="prefix.id">
                    <td v-for="col in visiblePrefixColumns" :key="col.key">
                      <span v-if="col.key === 'status'" :class="['app-badge', getStatusClass(prefix[col.key])]">
                        <component :is="getStatusIcon(prefix[col.key])" :size="12" />
                        {{ prefix[col.key] || '-' }}
                      </span>
                      <span v-else-if="col.key === 'utilization'" class="utilization-cell">
                        <div class="utilization-bar">
                          <div class="utilization-fill" :style="{ width: prefix.utilization + '%' }"></div>
                        </div>
                        <span class="utilization-text">{{ prefix.utilization }}%</span>
                      </span>
                      <a v-else-if="col.key === 'prefix'" @click="openPrefixDetail(prefix)" class="link-text">
                        {{ prefix[col.key] || '-' }}
                      </a>
                      <span v-else>{{ prefix[col.key] || '-' }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 前缀详情视图 -->
          <div v-if="activeTab === 'prefixes' && showPrefixDetail && selectedPrefix" class="tab-content">
            <div class="rack-detail-header">
              <button @click="closePrefixDetail" class="app-button app-button-secondary">
                <ArrowLeft :size="16" />
                返回
              </button>
              <h2>前缀详情 - {{ selectedPrefix.prefix }}</h2>
            </div>

            <div class="rack-info-section">
              <div class="section-header">
                <Info :size="18" />
                <h3>前缀信息</h3>
              </div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="info-label">前缀地址:</span>
                  <span class="info-value">{{ selectedPrefix.prefix || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">所属站点:</span>
                  <span class="info-value">{{ selectedPrefix.site || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">状态:</span>
                  <span :class="['info-value', 'app-badge', getStatusClass(selectedPrefix.status)]">
                    <component :is="getStatusIcon(selectedPrefix.status)" :size="12" />
                    {{ selectedPrefix.status || '-' }}
                  </span>
                </div>
                <div class="info-item">
                  <span class="info-label">协议版本:</span>
                  <span class="info-value">{{ selectedPrefix.family || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">VLAN:</span>
                  <span class="info-value">{{ selectedPrefix.vlan || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">租户:</span>
                  <span class="info-value">{{ selectedPrefix.tenant || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">总IP数:</span>
                  <span class="info-value">{{ selectedPrefix.total_ips || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">已使用IP:</span>
                  <span class="info-value">{{ selectedPrefix.used_ips || '-' }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">利用率:</span>
                  <span class="info-value">{{ selectedPrefix.utilization }}%</span>
                </div>
                <div class="info-item full-width">
                  <span class="info-label">描述:</span>
                  <span class="info-value">{{ selectedPrefix.description || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="rack-devices-section">
              <div class="section-header">
                <Globe :size="18" />
                <h3>前缀内IP地址 ({{ prefixIPs.length }} 个)</h3>
              </div>
              <div v-if="loading" class="loading app-empty">
                <Loader2 class="animate-spin" :size="40" />
                <p>加载中...</p>
              </div>
              <div v-else-if="prefixIPs.length === 0" class="empty app-empty">
                <GlobeOff :size="48" />
                <p>该前缀内暂无IP地址</p>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th>IP地址</th>
                    <th>状态</th>
                    <th>描述</th>
                    <th>DNS名称</th>
                    <th>分配对象类型</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ip in prefixIPs" :key="ip.id">
                    <td>{{ ip.address || '-' }}</td>
                    <td>
                      <span :class="['app-badge', getStatusClass(ip.status)]">
                        <component :is="getStatusIcon(ip.status)" :size="12" />
                        {{ ip.status || '-' }}
                      </span>
                    </td>
                    <td>{{ ip.description || '-' }}</td>
                    <td>{{ ip.dns_name || '-' }}</td>
                    <td>{{ ip.assigned_object_type || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 列设置弹窗 -->
      <div v-if="showColumnSettings" class="modal-overlay" @click="showColumnSettings = false">
        <div class="modal-content column-settings-modal" @click.stop>
          <div class="modal-header app-modal-header">
            <div class="modal-title">
              <Settings2 :size="20" />
              <h2>列设置 - {{ currentTabName }}</h2>
            </div>
            <button @click="showColumnSettings = false" class="btn-close">
              <X :size="18" />
            </button>
          </div>
          <div class="modal-body app-modal-body">
            <div class="column-list">
              <div
                v-for="(col, index) in currentColumns"
                :key="col.key"
                class="column-item"
                draggable="true"
                @dragstart="handleDragStart($event, index)"
                @dragover.prevent
                @drop="handleDrop($event, index)"
              >
                <GripVertical class="drag-handle" :size="16" />
                <input
                  type="checkbox"
                  v-model="col.visible"
                  :id="`col-${col.key}`"
                  class="column-checkbox"
                />
                <label :for="`col-${col.key}`" class="column-label">{{ col.label }}</label>
              </div>
            </div>
            <div class="column-actions">
              <button @click="resetColumns" class="app-button app-button-secondary">
                <RotateCcw :size="14" />
                重置默认
              </button>
              <button @click="saveColumns" class="app-button app-button-primary">
                <Check :size="14" />
                保存
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 详情弹窗 -->
      <div v-if="selectedItem" class="modal-overlay" @click="closeModal">
        <div class="modal-content" @click.stop>
          <div class="modal-header app-modal-header">
            <div class="modal-title">
              <Info :size="20" />
              <h2>{{ modalTitle }}</h2>
            </div>
            <button @click="closeModal" class="btn-close">
              <X :size="18" />
            </button>
          </div>
          <div class="modal-body app-modal-body">
            <div v-for="(value, key) in selectedItem" :key="key" class="detail-row">
              <span class="detail-label">{{ formatLabel(key) }}:</span>
              <span class="detail-value">{{ value || '-' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 凭据输入对话框 -->
      <div v-if="showCredentialsDialog" class="modal-overlay" @click="showCredentialsDialog = false">
        <div class="modal-content credentials-modal" @click.stop>
          <div class="modal-header app-modal-header">
            <div class="modal-title">
              <Lock :size="20" />
              <h2>设备登录凭据</h2>
            </div>
            <button @click="showCredentialsDialog = false" class="btn-close">
              <X :size="18" />
            </button>
          </div>
          <div class="modal-body app-modal-body">
            <div class="form-group">
              <label class="form-label">
                <Key :size="16" />
                用户名
              </label>
              <input
                v-model="credentialsForm.username"
                type="text"
                class="app-input"
                placeholder="请输入用户名"
              />
            </div>
            <div class="form-group">
              <label class="form-label">
                <Lock :size="16" />
                密码
              </label>
              <input
                v-model="credentialsForm.password"
                type="password"
                class="app-input"
                placeholder="请输入密码"
              />
            </div>
            <div class="form-group">
              <label class="form-label">SSH端口</label>
              <input
                v-model="credentialsForm.port"
                type="number"
                class="app-input"
                placeholder="默认22"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Enable密码（可选）</label>
              <input
                v-model="credentialsForm.enable_password"
                type="password"
                class="app-input"
                placeholder="如需要请输入"
              />
            </div>
            <div class="form-actions">
              <button @click="showCredentialsDialog = false" class="app-button app-button-secondary">
                取消
              </button>
              <button @click="handleFetchAndSaveConfig" class="app-button app-button-primary" :disabled="fetchingConfig">
                <Loader2 v-if="fetchingConfig" class="animate-spin" :size="14" />
                {{ fetchingConfig ? '获取中...' : '获取并写入' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { assetsApi, Device, IP, Rack, Site, VLAN, Prefix } from '@/api/assets'
import { 
  Server, Settings2, Monitor, Globe, HardDrive, Network, Router, 
  Search, RotateCcw, Loader2, Eye, Info, ArrowLeft, GripVertical, 
  Check, X, CheckCircle2, XCircle, Clock, AlertCircle, FileX, 
  Tag, Download, RefreshCw, Upload, Lock, Key
} from 'lucide-vue-next'

const debounce = <T extends (...args: any[]) => unknown>(func: T, wait: number) => {
  let timeout: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => {
      void func(...args)
    }, wait)
  }
}
const route = useRoute()

interface ColumnConfig {
  key: string
  label: string
  visible: boolean
}

const activeTab = ref<'devices' | 'ips' | 'racks' | 'vlans' | 'prefixes'>('devices')
const loading = ref(false)
const tabLoading = ref<Record<string, boolean>>({
  devices: false,
  ips: false,
  racks: false,
  vlans: false,
  prefixes: false
})
const selectedItem = ref<any>(null)
const modalTitle = ref('')
const showColumnSettings = ref(false)
const draggedIndex = ref<number | null>(null)
const showRackDetail = ref(false)
const selectedRack = ref<Rack | null>(null)
const rackDevices = ref<Device[]>([])

const showPrefixDetail = ref(false)
const selectedPrefix = ref<any>(null)
const prefixIPs = ref<IP[]>([])

const showDeviceDetail = ref(false)
const selectedDevice = ref<Device | null>(null)
const deviceConfig = ref<any>(null)
const loadingConfig = ref(false)
const showCredentialsDialog = ref(false)
const credentialsForm = ref({
  username: '',
  password: '',
  port: 22,
  enable_password: ''
})
const fetchingConfig = ref(false)

const defaultDeviceColumns: ColumnConfig[] = [
  { key: 'name', label: '设备名称', visible: true },
  { key: 'device_type', label: '设备类型', visible: true },
  { key: 'vendor', label: '厂商', visible: true },
  { key: 'site', label: '所属站点', visible: true },
  { key: 'role', label: '设备角色', visible: true },
  { key: 'status', label: '状态', visible: true },
  { key: 'primary_ip', label: '主IP地址', visible: true },
  { key: 'serial', label: '序列号', visible: false },
  { key: 'action', label: '操作', visible: true }
]

const deviceColumns = ref<ColumnConfig[]>([])

const defaultIPColumns: ColumnConfig[] = [
  { key: 'address', label: 'IP地址', visible: true },
  { key: 'description', label: '描述', visible: true },
  { key: 'status', label: '状态', visible: true },
  { key: 'dns_name', label: 'DNS名称', visible: true },
  { key: 'assigned_object_type', label: '分配对象类型', visible: true },
  { key: 'assigned_object_id', label: '分配对象ID', visible: false }
]

const ipColumns = ref<ColumnConfig[]>([])

const defaultRackColumns: ColumnConfig[] = [
  { key: 'name', label: '机柜名称', visible: true },
  { key: 'site', label: '所属站点', visible: true },
  { key: 'location', label: '位置', visible: true },
  { key: 'status', label: '状态', visible: true },
  { key: 'u_height', label: '高度(U)', visible: true },
  { key: 'width', label: '宽度', visible: false },
  { key: 'role', label: '角色', visible: true },
  { key: 'asset_tag', label: '资产标签', visible: false },
  { key: 'action', label: '操作', visible: true }
]

const rackColumns = ref<ColumnConfig[]>([])

const defaultVLANColumns: ColumnConfig[] = [
  { key: 'vid', label: 'VLAN ID', visible: true },
  { key: 'name', label: 'VLAN名称', visible: true },
  { key: 'site', label: '所属站点', visible: true },
  { key: 'status', label: '状态', visible: true },
  { key: 'role', label: '角色', visible: true },
  { key: 'tenant', label: '租户', visible: false },
  { key: 'description', label: '描述', visible: true }
]

const vlanColumns = ref<ColumnConfig[]>([])

const defaultPrefixColumns: ColumnConfig[] = [
  { key: 'prefix', label: '前缀地址', visible: true },
  { key: 'site', label: '所属站点', visible: true },
  { key: 'status', label: '状态', visible: true },
  { key: 'family', label: '协议版本', visible: true },
  { key: 'vlan', label: 'VLAN名称', visible: true },
  { key: 'vlan_vid', label: 'VLAN ID', visible: true },
  { key: 'used_ips', label: '已使用IP', visible: true },
  { key: 'utilization', label: '利用率', visible: true },
  { key: 'tenant', label: '租户', visible: false },
  { key: 'description', label: '描述', visible: true }
]

const prefixColumns = ref<ColumnConfig[]>([])

const visibleDeviceColumns = computed(() => deviceColumns.value.filter(col => col.visible))
const visibleIPColumns = computed(() => ipColumns.value.filter(col => col.visible))
const visibleRackColumns = computed(() => rackColumns.value.filter(col => col.visible))
const visibleVLANColumns = computed(() => vlanColumns.value.filter(col => col.visible))
const visiblePrefixColumns = computed(() => prefixColumns.value.filter(col => col.visible))

const currentTabName = computed(() => {
  const names = { devices: '设备', ips: 'IP地址', racks: '机柜', vlans: 'VLAN', prefixes: '前缀' }
  return names[activeTab.value]
})

const currentColumns = computed(() => {
  if (activeTab.value === 'devices') return deviceColumns.value
  if (activeTab.value === 'ips') return ipColumns.value
  if (activeTab.value === 'racks') return rackColumns.value
  if (activeTab.value === 'vlans') return vlanColumns.value
  if (activeTab.value === 'prefixes') return prefixColumns.value
  return rackColumns.value
})

const devices = ref<Device[]>([])
const deviceCount = ref(0)
const deviceFilters = ref({
  name: '',
  site: '',
  role: '',
  vendor: ''
})
const vendors = ref<string[]>([])

const ips = ref<IP[]>([])
const ipCount = ref(0)
const ipFilters = ref({
  address: '',
  status: ''
})

const racks = ref<Rack[]>([])
const rackCount = ref(0)
const rackFilters = ref({
  name: '',
  site: ''
})

const vlans = ref<VLAN[]>([])
const vlanCount = ref(0)
const vlanFilters = ref({
  name: '',
  site: '',
  status: ''
})

const prefixes = ref<Prefix[]>([])
const prefixCount = ref(0)
const prefixFilters = ref({
  prefix: '',
  site: '',
  family: '',
  status: ''
})

const sites = ref<Site[]>([])

const debouncedLoadDevices = debounce(loadDevices, 500)
const debouncedLoadIPs = debounce(loadIPs, 500)
const debouncedLoadRacks = debounce(loadRacks, 500)
const debouncedLoadVLANs = debounce(loadVLANs, 500)
const debouncedLoadPrefixes = debounce(loadPrefixes, 500)

function getStatusIcon(status: string) {
  if (!status) return Clock
  const statusLower = status.toLowerCase()
  if (statusLower.includes('active')) return CheckCircle2
  if (statusLower.includes('offline')) return XCircle
  if (statusLower.includes('maintenance')) return AlertCircle
  return Clock
}

function getStatusClass(status: string): string {
  if (!status) return 'status-unknown'
  const statusLower = status.toLowerCase()
  if (statusLower.includes('active')) return 'status-active'
  if (statusLower.includes('offline')) return 'status-offline'
  if (statusLower.includes('maintenance')) return 'status-maintenance'
  return 'status-unknown'
}

function formatLabel(key: string | number): string {
  const labelMap: Record<string, string> = {
    id: 'ID',
    name: '名称',
    device_type: '设备类型',
    site: '站点',
    role: '角色',
    vendor: '厂商',
    status: '状态',
    serial: '序列号',
    primary_ip: '主IP地址',
    address: 'IP地址',
    description: '描述',
    dns_name: 'DNS名称',
    assigned_object_type: '分配对象类型',
    assigned_object_id: '分配对象ID',
    location: '位置',
    u_height: '高度(U)',
    width: '宽度',
    asset_tag: '资产标签'
  }
  return labelMap[String(key)] || String(key)
}

function switchTab(tab: 'devices' | 'ips' | 'racks' | 'vlans' | 'prefixes') {
  activeTab.value = tab
  if (tab !== 'racks') {
    closeRackDetail()
  }
  if (tab !== 'prefixes') {
    closePrefixDetail()
  }
  if (tab !== 'devices') {
    closeDeviceDetail()
  }
  if (tab === 'devices') {
    loadDevices()
  } else if (tab === 'ips') {
    loadIPs()
  } else if (tab === 'racks') {
    loadRacks()
  } else if (tab === 'vlans') {
    loadVLANs()
  } else if (tab === 'prefixes') {
    loadPrefixes()
  }
}

function loadColumnConfig() {
  const savedConfig = localStorage.getItem('assets_column_config')
  if (savedConfig) {
    const config = JSON.parse(savedConfig)
    deviceColumns.value = config.devices || JSON.parse(JSON.stringify(defaultDeviceColumns))
    ipColumns.value = config.ips || JSON.parse(JSON.stringify(defaultIPColumns))
    rackColumns.value = config.racks || JSON.parse(JSON.stringify(defaultRackColumns))
    vlanColumns.value = config.vlans || JSON.parse(JSON.stringify(defaultVLANColumns))
    
    if (config.prefixes && config.prefixes.some((col: any) => col.key === 'used_ips')) {
      prefixColumns.value = config.prefixes
    } else {
      prefixColumns.value = JSON.parse(JSON.stringify(defaultPrefixColumns))
    }
  } else {
    deviceColumns.value = JSON.parse(JSON.stringify(defaultDeviceColumns))
    ipColumns.value = JSON.parse(JSON.stringify(defaultIPColumns))
    rackColumns.value = JSON.parse(JSON.stringify(defaultRackColumns))
    vlanColumns.value = JSON.parse(JSON.stringify(defaultVLANColumns))
    prefixColumns.value = JSON.parse(JSON.stringify(defaultPrefixColumns))
  }
}

function saveColumnConfig() {
  const config = {
    devices: deviceColumns.value,
    ips: ipColumns.value,
    racks: rackColumns.value,
    vlans: vlanColumns.value,
    prefixes: prefixColumns.value
  }
  localStorage.setItem('assets_column_config', JSON.stringify(config))
}

function resetColumns() {
  if (activeTab.value === 'devices') {
    deviceColumns.value = JSON.parse(JSON.stringify(defaultDeviceColumns))
  } else if (activeTab.value === 'ips') {
    ipColumns.value = JSON.parse(JSON.stringify(defaultIPColumns))
  } else if (activeTab.value === 'racks') {
    rackColumns.value = JSON.parse(JSON.stringify(defaultRackColumns))
  } else if (activeTab.value === 'vlans') {
    vlanColumns.value = JSON.parse(JSON.stringify(defaultVLANColumns))
  } else if (activeTab.value === 'prefixes') {
    prefixColumns.value = JSON.parse(JSON.stringify(defaultPrefixColumns))
  }
  saveColumnConfig()
}

function saveColumns() {
  saveColumnConfig()
  showColumnSettings.value = false
}

function handleDragStart(event: DragEvent, index: number) {
  void event
  draggedIndex.value = index
}

function handleDrop(event: DragEvent, dropIndex: number) {
  void event
  if (draggedIndex.value === null || draggedIndex.value === dropIndex) return

  const columns = currentColumns.value
  const [draggedItem] = columns.splice(draggedIndex.value, 1)
  columns.splice(dropIndex, 0, draggedItem)

  draggedIndex.value = null
}

async function loadDevices() {
  tabLoading.value.devices = true
  try {
    const params: any = {}
    if (deviceFilters.value.name) params.name = deviceFilters.value.name
    if (deviceFilters.value.site) params.site = deviceFilters.value.site
    if (deviceFilters.value.role) params.role = deviceFilters.value.role
    if (deviceFilters.value.vendor) params.vendor = deviceFilters.value.vendor

    const cacheKey = `devices_${JSON.stringify(params)}`

    const hasFilters = deviceFilters.value.name || deviceFilters.value.site || deviceFilters.value.role || deviceFilters.value.vendor

    if (!hasFilters) {
      try {
        const cachedData = sessionStorage.getItem(cacheKey)
        const cachedTime = sessionStorage.getItem(cacheKey + '_time')
        const now = Date.now()

        if (cachedData && cachedTime && (now - parseInt(cachedTime)) < 300000) {
          const response = JSON.parse(cachedData)
          devices.value = response.devices
          deviceCount.value = response.count
          tabLoading.value.devices = false
          return
        }
      } catch (cacheError) {
        console.error('Cache parse error:', cacheError)
        sessionStorage.removeItem(cacheKey)
        sessionStorage.removeItem(cacheKey + '_time')
      }
    }

    const response = await assetsApi.getDevices(params)
    devices.value = response.devices
    deviceCount.value = response.count
    const vendorSet = new Set((response.devices || []).map(d => d.vendor).filter(Boolean) as string[])
    if (vendorSet.size > 0) {
      const merged = new Set([...(vendors.value || []), ...Array.from(vendorSet)])
      vendors.value = Array.from(merged).sort((a, b) => a.localeCompare(b))
    }

    sessionStorage.setItem(cacheKey, JSON.stringify(response))
    sessionStorage.setItem(cacheKey + '_time', Date.now().toString())
  } catch (error) {
    console.error('Error loading devices:', error)
    devices.value = []
    deviceCount.value = 0
  } finally {
    tabLoading.value.devices = false
  }
}

async function loadIPs() {
  tabLoading.value.ips = true
  try {
    const params: any = {}
    if (ipFilters.value.address) params.address = ipFilters.value.address
    if (ipFilters.value.status) params.status = ipFilters.value.status

    const cacheKey = `ips_${JSON.stringify(params)}`

    const hasFilters = ipFilters.value.address || ipFilters.value.status

    if (!hasFilters) {
      try {
        const cachedData = sessionStorage.getItem(cacheKey)
        const cachedTime = sessionStorage.getItem(cacheKey + '_time')
        const now = Date.now()

        if (cachedData && cachedTime && (now - parseInt(cachedTime)) < 300000) {
          const response = JSON.parse(cachedData)
          ips.value = response.ips
          ipCount.value = response.count
          tabLoading.value.ips = false
          return
        }
      } catch (cacheError) {
        console.error('Cache parse error:', cacheError)
        sessionStorage.removeItem(cacheKey)
        sessionStorage.removeItem(cacheKey + '_time')
      }
    }

    const response = await assetsApi.getIPs(
      ipFilters.value.address,
      undefined,
      ipFilters.value.status
    )
    ips.value = response.ips
    ipCount.value = response.count

    sessionStorage.setItem(cacheKey, JSON.stringify(response))
    sessionStorage.setItem(cacheKey + '_time', Date.now().toString())
  } catch (error) {
    console.error('Error loading IPs:', error)
    ips.value = []
    ipCount.value = 0
  } finally {
    tabLoading.value.ips = false
  }
}

async function loadRacks() {
  tabLoading.value.racks = true
  try {
    const params: any = {}
    if (rackFilters.value.name) params.name = rackFilters.value.name
    if (rackFilters.value.site) params.site = rackFilters.value.site

    const cacheKey = `racks_${JSON.stringify(params)}`

    const hasFilters = rackFilters.value.name || rackFilters.value.site

    if (!hasFilters) {
      try {
        const cachedData = sessionStorage.getItem(cacheKey)
        const cachedTime = sessionStorage.getItem(cacheKey + '_time')
        const now = Date.now()

        if (cachedData && cachedTime && (now - parseInt(cachedTime)) < 300000) {
          const response = JSON.parse(cachedData)
          racks.value = response.racks
          rackCount.value = response.count
          tabLoading.value.racks = false
          return
        }
      } catch (cacheError) {
        console.error('Cache parse error:', cacheError)
        sessionStorage.removeItem(cacheKey)
        sessionStorage.removeItem(cacheKey + '_time')
      }
    }

    const response = await assetsApi.getRacks(params)
    racks.value = response.racks
    rackCount.value = response.count

    sessionStorage.setItem(cacheKey, JSON.stringify(response))
    sessionStorage.setItem(cacheKey + '_time', Date.now().toString())
  } catch (error) {
    console.error('Error loading racks:', error)
    racks.value = []
    rackCount.value = 0
  } finally {
    tabLoading.value.racks = false
  }
}

async function loadVLANs() {
  tabLoading.value.vlans = true
  try {
    const params: any = {}
    if (vlanFilters.value.name) params.name = vlanFilters.value.name
    if (vlanFilters.value.site) params.site = vlanFilters.value.site
    if (vlanFilters.value.status) params.status = vlanFilters.value.status

    const cacheKey = `vlans_${JSON.stringify(params)}`

    const hasFilters = vlanFilters.value.name || vlanFilters.value.site || vlanFilters.value.status

    if (!hasFilters) {
      try {
        const cachedData = sessionStorage.getItem(cacheKey)
        const cachedTime = sessionStorage.getItem(cacheKey + '_time')
        const now = Date.now()

        if (cachedData && cachedTime && (now - parseInt(cachedTime)) < 300000) {
          const response = JSON.parse(cachedData)
          vlans.value = response.vlans
          vlanCount.value = response.count
          tabLoading.value.vlans = false
          return
        }
      } catch (cacheError) {
        console.error('Cache parse error:', cacheError)
        sessionStorage.removeItem(cacheKey)
        sessionStorage.removeItem(cacheKey + '_time')
      }
    }

    const response = await assetsApi.getVLANs(params)
    vlans.value = response.vlans
    vlanCount.value = response.count

    sessionStorage.setItem(cacheKey, JSON.stringify(response))
    sessionStorage.setItem(cacheKey + '_time', Date.now().toString())
  } catch (error) {
    console.error('Error loading VLANs:', error)
    vlans.value = []
    vlanCount.value = 0
  } finally {
    tabLoading.value.vlans = false
  }
}

async function loadPrefixes() {
  tabLoading.value.prefixes = true
  try {
    const params: any = {}
    if (prefixFilters.value.prefix) params.prefix = prefixFilters.value.prefix
    if (prefixFilters.value.site) params.site = prefixFilters.value.site
    if (prefixFilters.value.family) params.family = parseInt(prefixFilters.value.family)
    if (prefixFilters.value.status) params.status = prefixFilters.value.status

    const cacheKey = `prefixes_${JSON.stringify(params)}`

    const hasFilters = prefixFilters.value.prefix || prefixFilters.value.site || prefixFilters.value.family || prefixFilters.value.status

    if (!hasFilters) {
      try {
        const cachedData = sessionStorage.getItem(cacheKey)
        const cachedTime = sessionStorage.getItem(cacheKey + '_time')
        const now = Date.now()

        if (cachedData && cachedTime && (now - parseInt(cachedTime)) < 300000) {
          const response = JSON.parse(cachedData)
          prefixes.value = response.prefixes
          prefixCount.value = response.count
          tabLoading.value.prefixes = false
          return
        }
      } catch (cacheError) {
        console.error('Cache parse error:', cacheError)
        sessionStorage.removeItem(cacheKey)
        sessionStorage.removeItem(cacheKey + '_time')
      }
    }

    const response = await assetsApi.getPrefixes(params)
    prefixes.value = response.prefixes
    prefixCount.value = response.count

    sessionStorage.setItem(cacheKey, JSON.stringify(response))
    sessionStorage.setItem(cacheKey + '_time', Date.now().toString())
  } catch (error) {
    console.error('Error loading prefixes:', error)
    prefixes.value = []
    prefixCount.value = 0
  } finally {
    tabLoading.value.prefixes = false
  }
}

async function loadSites() {
  try {
    const cachedSites = sessionStorage.getItem('netbox_sites')
    const cachedTime = sessionStorage.getItem('netbox_sites_time')
    const now = Date.now()

    if (cachedSites && cachedTime && (now - parseInt(cachedTime)) < 300000) {
      sites.value = JSON.parse(cachedSites)
      return
    }

    const response = await assetsApi.getSites()
    sites.value = response.sites

    sessionStorage.setItem('netbox_sites', JSON.stringify(response.sites))
    sessionStorage.setItem('netbox_sites_time', now.toString())
  } catch (error) {
    console.error('Error loading sites:', error)
  }
}

async function loadVendors() {
  try {
    const resp = await assetsApi.getVendors()
    vendors.value = resp.data || []
  } catch (error) {
    console.error('Error loading vendors:', error)
  }
}

function resetDeviceFilters() {
  deviceFilters.value = {
    name: '',
    site: '',
    role: '',
    vendor: ''
  }
  loadDevices()
}

function resetIPFilters() {
  ipFilters.value = {
    address: '',
    status: ''
  }
  loadIPs()
}

function resetRackFilters() {
  rackFilters.value = {
    name: '',
    site: ''
  }
  loadRacks()
}

function resetVLANFilters() {
  vlanFilters.value = {
    name: '',
    site: '',
    status: ''
  }
  loadVLANs()
}

function resetPrefixFilters() {
  prefixFilters.value = {
    prefix: '',
    site: '',
    family: '',
    status: ''
  }
  loadPrefixes()
}

function handleViewDetails(item: any, type: string) {
  selectedItem.value = item
  modalTitle.value = type === 'device' ? '设备详情' : '机柜详情'
}

function closeModal() {
  selectedItem.value = null
}

async function loadRackDevices(rackId: number) {
  loading.value = true
  try {
    const response = await assetsApi.getRackDevices(rackId)
    rackDevices.value = response.devices
  } catch (error) {
    console.error('Error loading rack devices:', error)
  } finally {
    loading.value = false
  }
}

function openRackDetail(rack: Rack) {
  selectedRack.value = rack
  showRackDetail.value = true
  loadRackDevices(rack.id)
}

function closeRackDetail() {
  showRackDetail.value = false
  selectedRack.value = null
  rackDevices.value = []
}

async function openPrefixDetail(prefix: any) {
  selectedPrefix.value = prefix
  showPrefixDetail.value = true
  await loadPrefixIPs(prefix.id)
}

function closePrefixDetail() {
  showPrefixDetail.value = false
  selectedPrefix.value = null
  prefixIPs.value = []
}

async function loadPrefixIPs(prefixId: number) {
  loading.value = true
  try {
    const response = await assetsApi.getPrefixIPs(prefixId)
    prefixIPs.value = response.ips
    
    if (selectedPrefix.value && response.utilization !== undefined) {
      selectedPrefix.value.utilization = response.utilization
      selectedPrefix.value.total_ips = response.total_ips
      selectedPrefix.value.used_ips = response.used_ips
    }
  } catch (error) {
    console.error('Error loading prefix IPs:', error)
  } finally {
    loading.value = false
  }
}

function openDeviceDetail(device: Device) {
  selectedDevice.value = device
  showDeviceDetail.value = true
  deviceConfig.value = null
}

function closeDeviceDetail() {
  showDeviceDetail.value = false
  selectedDevice.value = null
  deviceConfig.value = null
}

async function loadDeviceConfig() {
  if (!selectedDevice.value) return
  
  loadingConfig.value = true
  try {
    const config = await assetsApi.getDeviceConfig(selectedDevice.value.id)
    deviceConfig.value = config
  } catch (error) {
    console.error('Error loading device config:', error)
    deviceConfig.value = { has_config: false }
  } finally {
    loadingConfig.value = false
  }
}

function getTagClass(tag: string): string {
  if (tag === 'stack-master') return 'tag-master'
  if (tag === 'stack-member') return 'tag-member'
  return 'tag-default'
}

function getVendorClass(vendor?: string): string {
  if (!vendor) return 'vendor-default'
  const v = vendor.toLowerCase()
  if (v.includes('huawei')) return 'vendor-huawei'
  if (v.includes('cisco')) return 'vendor-cisco'
  if (v.includes('h3c')) return 'vendor-h3c'
  if (v.includes('juniper')) return 'vendor-juniper'
  return 'vendor-default'
}

function applyDeepLinkFilters() {
  const queryType = String(route.query.type || 'device').toLowerCase()
  const site = route.query.site ? String(route.query.site) : ''
  const role = route.query.role ? String(route.query.role) : ''
  const vendor = route.query.vendor ? String(route.query.vendor) : ''
  const keyword = route.query.keyword ? String(route.query.keyword) : ''

  if (queryType === 'rack') {
    activeTab.value = 'racks'
    rackFilters.value.site = site
    rackFilters.value.name = keyword
    return
  }

  if (queryType === 'ip') {
    activeTab.value = 'ips'
    ipFilters.value.address = keyword
    return
  }

  if (queryType === 'vlan') {
    activeTab.value = 'vlans'
    vlanFilters.value.site = site
    vlanFilters.value.name = keyword
    return
  }

  if (queryType === 'prefix') {
    activeTab.value = 'prefixes'
    prefixFilters.value.site = site
    prefixFilters.value.prefix = keyword
    return
  }

  activeTab.value = 'devices'
  deviceFilters.value.site = site
  deviceFilters.value.role = role
  deviceFilters.value.vendor = vendor
  deviceFilters.value.name = keyword
}

async function handleFetchAndSaveConfig() {
  if (!selectedDevice.value) return
  if (!credentialsForm.value.username || !credentialsForm.value.password) {
    alert('请输入用户名和密码')
    return
  }

  fetchingConfig.value = true
  try {
    const result = await assetsApi.fetchAndSaveDeviceConfig(
      selectedDevice.value.id,
      credentialsForm.value
    )
    
    if (result.success) {
      alert(result.message)
      showCredentialsDialog.value = false
      // 刷新配置显示
      await loadDeviceConfig()
    } else {
      alert('获取配置失败: ' + result.message)
    }
  } catch (error: any) {
    console.error('Error fetching and saving device config:', error)
    alert('获取配置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    fetchingConfig.value = false
  }
}

onMounted(() => {
  loadColumnConfig()
  applyDeepLinkFilters()
  loadSites()
  loadVendors()
  // 只加载当前标签页的数据，避免同时加载多个标签页
  switchTab(activeTab.value)
})
</script>

<style scoped>
.page {
  height: auto;
  min-height: 100%;
}

.page-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: none;
  padding: 0;
  overflow: visible;
}

.page-header {
  margin-bottom: 16px;
}

.content-layout {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
}

/* Sidebar navigation */
.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  color: var(--app-text-inverse);
  background: var(--app-surface-dark);
  border-radius: var(--app-radius-md);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  transition: background var(--app-transition-fast);
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.nav-item.active {
  background: var(--app-primary);
}

.nav-icon {
  flex-shrink: 0;
  color: var(--app-text-muted);
  transition: color var(--app-transition-fast);
}

.nav-item.active .nav-icon {
  color: var(--app-text-inverse);
}

.nav-text {
  flex: 1;
}

.nav-title {
  margin-bottom: 4px;
  font-size: 15px;
  font-weight: 600;
}

.nav-count {
  font-size: 13px;
  opacity: 0.75;
}

/* Main panel */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
}

.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Filters */
.filter-section {
  padding: 20px 24px;
  border-bottom: 1px solid var(--app-border);
}

.filter-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.filter-input-wrapper {
  position: relative;
  min-width: 200px;
}

.filter-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  margin-top: -8px;
  color: var(--app-text-muted);
  pointer-events: none;
}

.filter-text {
  padding-left: 36px;
}

.filter-select {
  width: auto;
  min-width: 150px;
}

/* Table */
.table-section {
  flex: 1;
  overflow-y: auto;
}

.loading,
.empty {
  padding: 80px 20px;
  color: var(--app-text-muted);
}

.empty-config {
  padding: 60px 20px;
  color: var(--app-text-muted);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--app-surface-subtle);
}

.data-table th {
  padding: 16px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-soft);
  border-bottom: 1px solid var(--app-border);
}

.data-table td {
  padding: 14px 16px;
  font-size: 14px;
  border-bottom: 1px solid var(--app-border);
}

.data-table tbody tr {
  transition: background var(--app-transition-fast);
}

.data-table tbody tr:hover {
  background: var(--app-surface-subtle);
}

.btn-table {
  min-height: 32px;
  padding: 4px 10px;
  font-size: 12px;
}

/* Badge semantics layered on .app-badge */
.app-badge.status-active {
  color: var(--app-success);
  background: var(--app-success-soft);
  border-color: var(--app-success);
}

.app-badge.status-offline {
  color: var(--app-danger);
  background: var(--app-danger-soft);
  border-color: var(--app-danger);
}

.app-badge.status-maintenance {
  color: var(--app-warning);
  background: var(--app-warning-soft);
  border-color: var(--app-warning);
}

.vendor-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.app-badge.vendor-huawei {
  color: var(--app-danger);
}

.app-badge.vendor-cisco {
  color: var(--app-primary);
}

.app-badge.vendor-h3c,
.app-badge.vendor-juniper {
  color: var(--app-success);
}

.app-badge.tag-master {
  color: var(--app-warning);
  background: var(--app-warning-soft);
  border-color: var(--app-warning);
}

.app-badge.tag-default {
  color: var(--app-primary);
  background: var(--app-primary-soft);
  border-color: var(--app-primary);
}

.link-text {
  color: var(--app-primary);
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: color var(--app-transition-fast);
}

.link-text:hover {
  color: var(--app-primary-strong);
  text-decoration: underline;
}

/* Detail views */
.rack-detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--app-border);
}

.rack-info-section {
  padding: 24px;
  border-bottom: 1px solid var(--app-border);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  color: var(--app-text-soft);
}

.section-header h3 {
  flex: 1;
  color: var(--app-text);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-muted);
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--app-text);
}

.rack-devices-section,
.device-config-section {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.config-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.config-section {
  margin-bottom: 24px;
}

.config-section:last-child {
  margin-bottom: 0;
}

.config-section h4 {
  margin-bottom: 12px;
}

.config-text {
  max-height: 600px;
  padding: 16px;
  overflow: auto;
  color: var(--app-text);
  background: var(--app-surface-subtle);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.tags-container,
.tags-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

/* Utilization meter */
.utilization-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.utilization-bar {
  flex: 1;
  min-width: 60px;
  height: 8px;
  overflow: hidden;
  background: var(--app-bg-deep);
  border-radius: var(--app-radius-sm);
}

.utilization-fill {
  height: 100%;
  background: var(--app-primary);
  transition: width var(--app-transition-normal);
}

.utilization-text {
  min-width: 50px;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text-soft);
}

/* Modals */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(23, 32, 51, 0.45);
}

.modal-content {
  width: 90%;
  max-width: 550px;
  max-height: 85vh;
  overflow-y: auto;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  box-shadow: var(--app-shadow-lg);
}

.column-settings-modal {
  max-width: 420px;
}

.credentials-modal {
  max-width: 450px;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--app-text);
}

.btn-close {
  display: flex;
  width: 36px;
  height: 36px;
  padding: 0;
  align-items: center;
  justify-content: center;
  color: var(--app-text-muted);
  background: transparent;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  transition: color var(--app-transition-fast), background var(--app-transition-fast),
    border-color var(--app-transition-fast);
}

.btn-close:hover {
  color: var(--app-text);
  background: var(--app-surface-subtle);
  border-color: var(--app-border-strong);
}

.column-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 24px;
}

.column-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--app-surface-subtle);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: move;
  transition: background var(--app-transition-fast), border-color var(--app-transition-fast);
}

.column-item:hover {
  border-color: var(--app-border-strong);
}

.drag-handle {
  flex-shrink: 0;
  color: var(--app-text-muted);
  cursor: move;
}

.column-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--app-primary);
}

.column-label {
  flex: 1;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.column-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.detail-row {
  display: flex;
  padding: 14px 0;
  border-bottom: 1px solid var(--app-border);
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-label {
  min-width: 140px;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text-soft);
}

.detail-value {
  flex: 1;
  font-size: 14px;
  color: var(--app-text);
  word-break: break-word;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--app-border);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
