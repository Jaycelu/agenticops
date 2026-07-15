import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const buildUrl = (path: string) => API_BASE_URL.startsWith('http') ? `${API_BASE_URL}${path}` : `${API_BASE_URL}${path.replace('/api', '')}`

export const webhooksApi = {
  async endpoints() { return (await axios.get(buildUrl('/api/webhooks/endpoints'))).data },
  async save(endpointId: number, payload: any) {
    return (await axios.put(buildUrl(`/api/webhooks/endpoints/${endpointId}`), payload)).data
  },
  async test(endpointId: number) {
    return (await axios.post(buildUrl(`/api/webhooks/endpoints/${endpointId}/test`))).data
  },
  async deliveries(status?: string) {
    return (await axios.get(buildUrl('/api/webhooks/deliveries'), { params: { status } })).data
  },
  async redeliver(deliveryId: number) {
    return (await axios.post(buildUrl(`/api/webhooks/deliveries/${deliveryId}/redeliver`))).data
  }
}
