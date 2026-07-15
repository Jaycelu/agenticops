import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface EventRecord {
  id: number
  source_event_id?: number
  source: string
  source_label?: string
  source_category?: string
  event_type?: string
  signal_key?: string
  disposition?: string
  disposition_reason?: string
  decision_confidence?: number
  cluster_key?: string
  correlation_key?: string
  signal_family?: string
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
  case_id?: number
  case_code?: string
  created_at?: string
  updated_at?: string
}

export type EventItem = EventRecord

export interface EventListResponse {
  page: {
    total: number
    skip: number
    limit: number
    returned: number
    has_more: boolean
  }
  events: EventRecord[]
}

export interface EventClusterItem {
  cluster_key: string
  correlation_key: string
  title: string
  event_count: number
  source_categories: string[]
  dispositions: Record<string, number>
  case_count: number
  ticket_count: number
  highest_severity: string
  host?: string
  site_id?: number
  netbox_device_id?: number
  latest_occurred_at?: string
  signal_family?: string
  device_name?: string
  device_role?: string
  site_name?: string
  topology_hint?: string
  root_cause_candidate?: string
  adjacent_devices: string[]
  link_count: number
  impact_scope?: string
}

export interface RootCauseCandidateItem {
  candidate_key: string
  title: string
  root_cause_candidate: string
  site_name?: string
  signal_family?: string
  score: number
  ranking_reason: string
  merged_cluster_count: number
  event_count: number
  case_count: number
  ticket_count: number
  source_categories: string[]
  adjacent_devices: string[]
  representative_device?: string
  impact_scope?: string
  recommended_actions: Array<{
    priority_order: number
    action_type: string
    title: string
    reason: string
    mode: string
  }>
}

export interface EventRelationsResponse {
  event_id: number
  ticket: Record<string, any>
  linked_case?: {
    case_id: number
    case_code: string
    created_at?: string
  } | null
  linked_tasks: Array<{
    task_id: number
    task_code: string
    status: string
    source_model?: string
    case_id?: number | null
    recommended_skill_code?: string
    created_at?: string
  }>
}

export interface PlaybookDraftCheckResponse {
  success: boolean
  message: string
  event_id: number
  playbook_check: {
    passed?: boolean
    errors?: string[]
    warnings?: string[]
  }
  playbook_yaml?: string
}

export const eventsApi = {
  async listEvents(params?: {
    status?: string
    severity?: string
    source?: string
    event_type?: string
    source_category?: string
    disposition?: string
    site_id?: number
    netbox_device_id?: number
    skip?: number
    limit?: number
  }): Promise<EventListResponse> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events` : `${API_BASE_URL}/events`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async listClusters(params?: {
    status?: string
    severity?: string
    source?: string
    disposition?: string
    limit?: number
  }): Promise<{ clusters: EventClusterItem[] }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/clusters` : `${API_BASE_URL}/events/clusters`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async listRootCauses(params?: {
    status?: string
    severity?: string
    source?: string
    disposition?: string
    limit?: number
  }): Promise<{ items: RootCauseCandidateItem[] }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/root-causes` : `${API_BASE_URL}/events/root-causes`
    const response = await axios.get(apiUrl, { params })
    return response.data
  },

  async getMode(): Promise<{ message: string }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/mode` : `${API_BASE_URL}/events/mode`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async dispatchReadonly(
    eventId: number
  ): Promise<{ success: boolean; message: string; task_id?: number | null; case_id?: number | null; case_code?: string | null; playbook_check?: Record<string, any> }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/dispatch-readonly` : `${API_BASE_URL}/events/${eventId}/dispatch-readonly`
    const response = await axios.post(apiUrl, {})
    return response.data
  },

  async createTicket(eventId: number, payload?: { title?: string; description?: string; priority?: string }): Promise<{ success: boolean; message: string; ticket_id?: string; provider?: string }> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/ticket` : `${API_BASE_URL}/events/${eventId}/ticket`
    const response = await axios.post(apiUrl, payload || {})
    return response.data
  },

  async getRelations(eventId: number): Promise<EventRelationsResponse> {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/events/${eventId}/relations` : `${API_BASE_URL}/events/${eventId}/relations`
    const response = await axios.get(apiUrl)
    return response.data
  },

  async generatePlaybookDraft(eventId: number, includePlaybook: boolean = true): Promise<PlaybookDraftCheckResponse> {
    const apiUrl = API_BASE_URL.startsWith('http')
      ? `${API_BASE_URL}/api/events/${eventId}/playbook-draft-check`
      : `${API_BASE_URL}/events/${eventId}/playbook-draft-check`
    const response = await axios.post(apiUrl, { include_playbook: includePlaybook })
    return response.data
  },

  async updateDisposition(eventId: number, disposition: 'noise' | 'ticket_only' | 'case_required', reason?: string): Promise<{ message: string }> {
    const apiUrl = API_BASE_URL.startsWith('http')
      ? `${API_BASE_URL}/api/events/${eventId}/disposition`
      : `${API_BASE_URL}/events/${eventId}/disposition`
    const response = await axios.post(apiUrl, { disposition, reason })
    return response.data
  }
}
