import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface LocalTicketItem {
  id: number
  ticket_code: string
  provider: string
  event_id?: number
  title: string
  description?: string
  priority: string
  requester: string
  status: string
  metadata: Record<string, any>
  created_at?: string
  updated_at?: string
}

export const ticketsApi = {
  async listTickets(params?: { status?: string; event_id?: number; skip?: number; limit?: number }) {
    const apiUrl = API_BASE_URL.startsWith('http') ? `${API_BASE_URL}/api/tickets` : `${API_BASE_URL}/tickets`
    const response = await axios.get(apiUrl, { params })
    return response.data as {
      page: {
        total: number
        skip: number
        limit: number
        returned: number
        has_more: boolean
      }
      tickets: LocalTicketItem[]
    }
  },

  async updateStatus(ticketCode: string, status: string, comment?: string, operator = 'ui-operator') {
    const apiUrl = API_BASE_URL.startsWith('http')
      ? `${API_BASE_URL}/api/tickets/${ticketCode}`
      : `${API_BASE_URL}/tickets/${ticketCode}`
    const response = await axios.patch(apiUrl, { status, comment, operator })
    return response.data as { success: boolean; message: string; ticket?: LocalTicketItem }
  }
}
