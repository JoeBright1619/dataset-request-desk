import type { Request } from '../api/types'
import { RequestItem } from './RequestItem'

interface Props {
  requests: Request[]
  actionLoading: Record<string, boolean>
  onAccept: (id: string) => void
  onReject: (id: string) => void
}

export function RequestList({ requests, actionLoading, onAccept, onReject }: Props) {
  if (requests.length === 0) {
    return <p className="muted">No requests yet. Create one above to get started.</p>
  }

  return (
    <ul className="request-list">
      {requests.map((req) => (
        <RequestItem
          key={req.id}
          request={req}
          busy={!!actionLoading[req.id]}
          onAccept={onAccept}
          onReject={onReject}
        />
      ))}
    </ul>
  )
}