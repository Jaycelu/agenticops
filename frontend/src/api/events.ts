import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface EventItem {
  id: number
  source: string
  external_event_id?: string
  dedup_key: string
  site_id?: number
  netbox_device_id?: number
  host?: string
  name: string
  severity: string
  severity_level: number
  status: string
  acknowledged: boolean
  occurred_at?: string
  resolved_at?: string
  last_seen_at?: string
  payload: Record<string, any>
  recommended_skill_code?: string
  created_at?: string
  updated_at?: string
}

export interface EventListResponse {
  page: {
    total: number
    skip: number
    limit: number
    returned: number
    has_more: boolean
  }
  events: EventItem[]
}

export interface EventRelationsResponse {
  event_id: number
  ticket: Record<string, any>
  linked_tasks: Array<{
    task_id: number
    task_code: string
    status: string
    recommended_skill_code?: string
    created_at?: string
  }>
}

export const eventsApi = {
  async listEvents(params?: {
    status?: string
    severity?: string
    source?: string
    site_id?: number
    netbox_device_id?: number
    skip?: number
    limit?: number
  }): Promise<EventListResponse> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events` : `${API_BASE_URL}/events`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getMode(): Promise<{ message: string }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/mode` : `${API_BASE_URL}/events/mode`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async dispatchReadonly(eventId: number, reviewer: string = 'operator'): Promise<{ success: boolean; message: string; task_id?: number }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/dispatch-readonly` : `${API_BASE_URL}/events/${eventId}/dispatch-readonly`
    const response = await axios.post(apiUrl, { reviewer })
    return response.data
  },

  async createTicket(eventId: number, payload?: { title?: string; description?: string; priority?: string; requester?: string }): Promise<{ success: boolean; message: string; ticket_id?: string; provider?: string }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/ticket` : `${API_BASE_URL}/events/${eventId}/ticket`
    const response = await axios.post(apiUrl, payload || {})
    return response.data
  },

  async getRelations(eventId: number): Promise<EventRelationsResponse> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/relations` : `${API_BASE_URL}/events/${eventId}/relations`
    const response = await axios.get(apiUrl)
    return response.data
  }
}
