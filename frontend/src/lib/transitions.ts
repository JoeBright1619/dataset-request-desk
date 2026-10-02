import type { Request, RequestStatus } from '../api/types'

export type UserRole = 'client' | 'operator' | 'admin'

export interface AllowedTransition {
  status: RequestStatus
  requiresReason: boolean
  label: string
}

export function getAllowedTransitions(
  request: Request,
  role: UserRole | '' | undefined,
): AllowedTransition[] {
  const isOperatorOrAdmin = role === 'operator' || role === 'admin'
  const isClient = role === 'client'

  if (isOperatorOrAdmin) {
  if (request.status === 'submitted' || request.status === 'rejected') {
    return [{ status: 'in_progress', requiresReason: false, label: 'Start work' }]
  }
  if (
    request.status === 'in_progress' &&
    request.episodes_assigned >= request.episodes_requested
  ) {
    return [{ status: 'delivered', requiresReason: false, label: 'Mark delivered' }]
  }
  return []
}
  if (isClient && request.status === 'delivered') {
    return [
      { status: 'accepted', requiresReason: false, label: 'Accept delivery' },
      { status: 'rejected', requiresReason: true, label: 'Reject delivery' },
    ]
  }

  return []
}