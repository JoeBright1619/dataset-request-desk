// Error envelope structure per docs/API.md §0.4
export interface ApiError {
  code: string
  message: string
  field?: string
}

// Success responses
export interface ApiResponse<T> {
  data: T
}

// Auth types
export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface RefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: number
  username: string
  role: 'client' | 'operator' | 'admin'
  is_active: boolean
  created_at: string
}

// Request types
// Matches backend RequestStatus Literal
export type RequestStatus =
  | 'submitted'
  | 'in_progress'
  | 'delivered'
  | 'accepted'
  | 'rejected'

// Matches backend RequestResponse
export interface Request {
  id: string                 // UUID serialized as string
  client_id: string          // UUID
  client_name: string
  task_name: string
  episodes_requested: number
  episodes_assigned: number
  deadline: string           // ISO 8601 datetime
  notes: string | null
  status: RequestStatus
  created_at: string         // ISO 8601
  updated_at: string         // ISO 8601
  delivered_at: string | null
}

// Matches backend RequestListResponse
export interface RequestListResponse {
  items: Request[]
  next_cursor: string | null
  prev_cursor: string | null
  has_more: boolean
  has_prev: boolean
  limit: number
}

// Episode types
export interface Episode {
  episode_id: string
  task_name: string
  robot_id: string
  quality: 'good' | 'acceptable' | 'bad'
  recorded_at: string
}
