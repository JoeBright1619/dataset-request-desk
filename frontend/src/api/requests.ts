import { get, post } from './client'
import type { Request, RequestListResponse, RequestStatus } from './types'

export function listRequests() {
  return get<RequestListResponse>('/requests')
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