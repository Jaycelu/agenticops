# Local Ticket Module & External Integration Guide

## 1. Current Strategy

The platform now uses a **local ticket module by default**.

- Ticket creation entry: `POST /api/events/{event_id}/ticket`
- When `TICKET_MODE=local` (current default):
  - Create a row in `local_ticket`
  - Return local ticket id like `LOCAL-<timestamp_ms>`
  - Link ticket summary back to `alert_event.payload.ticket`

This keeps event-to-task-to-ticket traceability fully inside the system before go-live.

## 2. Local Ticket APIs

- `GET /api/tickets`
  - Filters: `status`, `event_id`, `skip`, `limit`
- `GET /api/tickets/{ticket_code}`
- `PATCH /api/tickets/{ticket_code}`
  - Body: `{ "status": "open|in_progress|resolved|closed", "comment": "optional" }`

## 3. Data Model

Table: `local_ticket`

Core fields:
- `ticket_code` (unique)
- `provider` (`local|external`)
- `event_id` (linked to `alert_event.id`)
- `title`, `description`, `priority`, `requester`, `status`
- `metadata` (JSON)
- `closed_at`, `created_at`, `updated_at`

## 4. External System Cutover

When you need to connect your self-built ticket system:

1. Configure:
- `TICKET_MODE=external`
- `TICKET_SYSTEM_BASE_URL`
- `TICKET_SYSTEM_API_KEY`
- `TICKET_SYSTEM_TIMEOUT_SECONDS`

2. Keep existing API unchanged:
- Event side still calls `POST /api/events/{event_id}/ticket`
- `ticket_adapter` switches provider to external only when `TICKET_MODE=external`

3. Recommended external API contract:
- Create ticket: `POST /tickets`
  - Input includes `title`, `description`, `priority`, `requester`, `metadata`
  - Output includes `ticket_id`, `status`
- Update ticket: `PATCH /tickets/{ticket_id}`
  - Output includes `status`

4. Migration recommendation:
- Keep writing local tickets for audit (`provider=external`, plus external id in metadata)
- Or keep current lightweight mode (only store ticket summary in event payload)

## 5. Mapping Example

Incoming event payload metadata:
- `event_id`
- `external_event_id`
- `site_id`
- `netbox_device_id`
- `severity`
- `status`

Suggested external fields:
- `source_event_id` <= `event_id`
- `cmdb_device_id` <= `netbox_device_id`
- `alarm_severity` <= `severity`
- `alarm_status` <= `status`
