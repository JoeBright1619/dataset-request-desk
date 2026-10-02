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
export interface Request {
  id: number
  client_id: number
  task_name: string
  quality: 'good' | 'acceptable'
  episodes_requested: number
  episodes_assigned: number
  status: string
  created_at: string
  updated_at: string
}

// Episode types
export interface Episode {
  episode_id: string
  task_name: string
  robot_id: string
  quality: 'good' | 'acceptable' | 'bad'
  recorded_at: string
}
