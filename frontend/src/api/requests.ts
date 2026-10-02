import { get, post } from './client'
import type {
  Request,
  RequestListResponse,
  RequestStatus,
} from '../api/types'

export interface ListRequestsParams {
  status?: RequestStatus
  clientId?: string          // operator/admin only; ignored by backend for clients
  taskName?: string
  cursor?: string
  limit?: number
}

export function listRequests(params: ListRequestsParams = {}) {
  const qs = new URLSearchParams()
  if (params.status) qs.set('status', params.status)
  if (params.clientId) qs.set('client_id', params.clientId)
  if (params.taskName) qs.set('task_name', params.taskName)
  if (params.cursor) qs.set('cursor', params.cursor)
  if (params.limit != null) qs.set('limit', String(params.limit))

  const suffix = qs.toString() ? `?${qs}` : ''
  return get<RequestListResponse>(`/requests${suffix}`)
}

export interface CreateRequestInput {
  task_name: string
  episodes_requested: number
  deadline: string
  notes?: string
}

export function createRequest(input: CreateRequestInput) {
  return post<Request>('/requests', input)
}

export function updateRequestStatus(
  id: string,
  status: RequestStatus,
  reason?: string,
) {
  return post<Request>(`/requests/${id}/status`, { status, reason })
}