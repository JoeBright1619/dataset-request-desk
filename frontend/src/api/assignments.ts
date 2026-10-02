import { get, post, del } from './client'

export interface Assignment {
  episode_id: string          // domain id — this is what you release
  robot_id: string
  task_name: string
  quality: string
  recorded_at: string
  assigned_at: string
  assigned_by: string
}

export interface AssignmentListResponse {
  items: Assignment[]
  next_cursor: string | null
  prev_cursor: string | null
  has_more: boolean
  has_prev: boolean
  limit: number
}

export interface RejectedAssignment {
  episode_id: string
  reason: string
}

export interface AssignmentBatchResponse {
  request_id: string
  assigned: string[]          // domain episode_ids
  rejected: RejectedAssignment[]
  episodes_requested: number
  episodes_assigned: number
}

export function listAssignments(requestId: string, cursor?: string, limit = 50) {
  const qs = new URLSearchParams()
  if (cursor) qs.set('cursor', cursor)
  qs.set('limit', String(limit))
  return get<AssignmentListResponse>(`/requests/${requestId}/assignments?${qs}`)
}

// episodeIds here MUST be domain episode_ids (Episode.episode_id), not internal ids
export function assignEpisodes(requestId: string, episodeIds: string[]) {
  return post<AssignmentBatchResponse>(`/requests/${requestId}/assignments`, {
    episode_ids: episodeIds,
  })
}

export function releaseAssignment(requestId: string, episodeId: string) {
  return del<void>(`/requests/${requestId}/assignments/${episodeId}`)
}