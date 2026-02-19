import axios from 'axios'

// 使用环境变量配置的 API 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface Device {
  id: number
  name: string
  device_type: string
  site: string
  role: string
  vendor?: string
  status: string
  serial: string
  primary_ip: string
  rack?: string
  position?: number
  face?: string
  tags: string[]
  [key: string]: unknown
}

export interface DeviceQuery {
  name?: string
  site?: string
  role?: string
  vendor?: string
}

export interface DeviceListResponse {
  count: number
  devices: Device[]
}

export interface IP {
  id: number
  address: string
  description: string
  status: string
  assigned_object_type: string
  assigned_object_id: number
  dns_name: string
  [key: string]: unknown
}

export interface IPListResponse {
  count: number
  ips: IP[]
}

export interface PrefixIPsResponse extends IPListResponse {
  utilization?: number
  total_ips?: number
  used_ips?: number
}

export interface Site {
  id: number
  name: string
  slug: string
  description: string
  status: string
}

export interface SiteListResponse {
  count: number
  sites: Site[]
}

export interface Rack {
  id: number
  name: string
  site: string
  location: string
  status: string
  u_height: number
  width: number
  role: string
  serial: string
  asset_tag: string
  [key: string]: unknown
}

export interface RackQuery {
  name?: string
  site?: string
  status?: string
}

export interface RackListResponse {
  count: number
  racks: Rack[]
}

export interface VLAN {
  id: number
  vid: number
  name: string
  site: string
  status: string
  description: string
  tenant: string
  role: string
  [key: string]: unknown
}

export interface VLANQuery {
  name?: string
  site?: string
  vid?: number
  status?: string
}

export interface VLANListResponse {
  count: number
  vlans: VLAN[]
}

export interface Prefix {
  id: number
  prefix: string
  site: string
  status: string
  description: string
  tenant: string
  family: number | string
  vlan: string
  vlan_vid: number
  total_ips: number
  used_ips: number
  utilization: number
  [key: string]: unknown
}

export interface PrefixQuery {
  prefix?: string
  site?: string
  family?: number
  status?: string
}

export interface PrefixListResponse {
  count: number
  prefixes: Prefix[]
}

export const assetsApi = {
  async getDevices(params?: DeviceQuery): Promise<DeviceListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/devices` : `${API_BASE_URL}/assets/devices`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getDeviceDetail(deviceId: number): Promise<Device> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/devices/${deviceId}` : `${API_BASE_URL}/assets/devices/${deviceId}`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async getIPs(address?: string, deviceId?: number, status?: string): Promise<IPListResponse> {
    const params: any = {}
    if (address) params.address = address
    if (deviceId) params.device_id = deviceId
    if (status) params.status = status

    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/ips` : `${API_BASE_URL}/assets/ips`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getSites(): Promise<SiteListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/sites` : `${API_BASE_URL}/assets/sites`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async getRacks(params?: RackQuery): Promise<RackListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/racks` : `${API_BASE_URL}/assets/racks`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getRackDevices(rackId: number): Promise<DeviceListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/racks/${rackId}/devices` : `${API_BASE_URL}/assets/racks/${rackId}/devices`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async getVLANs(params?: VLANQuery): Promise<VLANListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/vlans` : `${API_BASE_URL}/assets/vlans`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getPrefixes(params?: PrefixQuery): Promise<PrefixListResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/prefixes` : `${API_BASE_URL}/assets/prefixes`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getPrefixIPs(prefixId: number): Promise<PrefixIPsResponse> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/prefixes/${prefixId}/ips` : `${API_BASE_URL}/assets/prefixes/${prefixId}/ips`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async getDeviceConfig(deviceId: number): Promise<any> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/devices/${deviceId}/config` : `${API_BASE_URL}/assets/devices/${deviceId}/config`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async fetchAndSaveDeviceConfig(deviceId: number, credentials: any): Promise<any> {
    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/devices/${deviceId}/fetch-config` : `${API_BASE_URL}/assets/devices/${deviceId}/fetch-config`
    const response = await axios.post(apiUrl, credentials)
    return response.data
  },

  async getDevicesWithIP(site?: string, role?: string, status?: string, vendor?: string): Promise<DeviceListResponse> {
    const params: any = {}
    if (site) params.site = site
    if (role) params.role = role
    if (status) params.status = status
    if (vendor) params.vendor = vendor

    // 如果使用VITE_API_BASE_URL环境变量，则API路径应包含/api前缀
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/devices/with-ip` : `${API_BASE_URL}/assets/devices/with-ip`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getVendors(): Promise<{ success: boolean; data: string[] }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/vendors` : `${API_BASE_URL}/assets/vendors`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async syncDevices(site?: string, vendor?: string): Promise<any> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/assets/sync/devices` : `${API_BASE_URL}/assets/sync/devices`
    const response = await axios.post(apiUrl, null, { params: { site, vendor } })
    return response.data
  }
}
