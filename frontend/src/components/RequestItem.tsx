import type { Request, RequestStatus } from '../api/types'

const STATUS_LABEL: Record<RequestStatus, string> = {
  submitted: 'Submitted',
  in_progress: 'In progress',
  delivered: 'Delivered — awaiting your review',
  accepted: 'Accepted',
  rejected: 'Rejected',
}

interface Props {
  request: Request
  busy: boolean
  onAccept: (id: string) => void
  onReject: (id: string) => void
}

export function RequestItem({ request: req, busy, onAccept, onReject }: Props) {
  const showActions = req.status === 'delivered'

  return (
    <li className="request-item">
      <div className="request-item__main">
        <h3>{req.task_name}</h3>
        <p className="request-item__meta">
          Episodes: {req.episodes_requested}
          {req.deadline && <> · Deadline: {new Date(req.deadline).toLocaleString()}</>}
        </p>

        {req.status === 'delivered' && (
          <p className="request-item__meta">
            Delivered: {req.episodes_assigned} of {req.episodes_requested} episodes
          </p>
        )}

        {req.notes && <p className="request-item__notes">{req.notes}</p>}

        <p className="request-item__status">
          <strong>{STATUS_LABEL[req.status]}</strong>
        </p>
      </div>

      {showActions && (
        <div className="request-item__actions">
          <button
            className="btn btn--accept"
            onClick={() => onAccept(req.id)}
            disabled={busy}
          >
            {busy ? '…' : 'Accept'}
          </button>
          <button
            className="btn btn--reject"
            onClick={() => onReject(req.id)}
            disabled={busy}
          >
            {busy ? '…' : 'Reject'}
          </button>
        </div>
      )}
    </li>
  )
}