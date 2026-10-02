import { get } from './client'

// Mirrors app.schemas.episode.EpisodeQuality
export type EpisodeQuality = 'good' | 'usable' | 'bad'

export interface Episode {
  id: string                       // UUID — internal, use for React keys
  episode_id: string               // domain id — use for assign/release
  robot_id: string
  task_name: string
  recorded_at: string              // ISO 8601 datetime
  duration_seconds: string         // Pydantic serializes Decimal as string
  operator_name: string | null
  quality: EpisodeQuality
  is_assigned: boolean
  created_at: string               // ISO 8601 datetime
}

export interface EpisodeListResponse {
  items: Episode[]
  next_cursor: string | null
  prev_cursor: string | null
  has_more: boolean
  has_prev: boolean
  limit: number
}

export interface EpisodeSearchParams {
  taskName?: string
  quality?: EpisodeQuality
  robotId?: string
  recordedFrom?: string
  recordedTo?: string
  assigned?: boolean
  cursor?: string
  limit?: number
}

export function searchEpisodes(params: EpisodeSearchParams = {}) {
  const qs = new URLSearchParams()
  if (params.taskName) qs.set('task_name', params.taskName)
  if (params.quality) qs.set('quality', params.quality)
  if (params.robotId) qs.set('robot_id', params.robotId)
  if (params.recordedFrom) qs.set('recorded_from', params.recordedFrom)
  if (params.recordedTo) qs.set('recorded_to', params.recordedTo)
  if (params.assigned !== undefined) qs.set('assigned', String(params.assigned))
  if (params.cursor) qs.set('cursor', params.cursor)
  if (params.limit != null) qs.set('limit', String(params.limit))

  const suffix = qs.toString() ? `?${qs}` : ''
  return get<EpisodeListResponse>(`/episodes${suffix}`)
}