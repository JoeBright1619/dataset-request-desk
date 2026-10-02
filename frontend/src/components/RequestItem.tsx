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
  onViewDetail: (request: Request) => void
}

export function RequestItem({
  request: req,
  busy,
  onAccept,
  onReject,
  onViewDetail,
}: Props) {
  const showActions = req.status === 'delivered'

  return (
    <li className="request-item">
      <button
        type="button"
        className="request-item__main"
        onClick={() => onViewDetail(req)}
        aria-label={`View details for request ${req.task_name}`}
      >
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
      </button>

      
    </li>
  )
}