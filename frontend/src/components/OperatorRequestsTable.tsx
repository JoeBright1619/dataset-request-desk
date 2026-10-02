import type { Request } from '../api/types'

interface Props {
  requests: Request[]
  onViewDetail: (request: Request) => void
}

export function OperatorRequestsTable({ requests, onViewDetail }: Props) {
  if (requests.length === 0) {
    return <p className="muted">No requests to display.</p>
  }

  return (
    <div className="requests-table">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Client</th>
            <th>Task</th>
            <th>Ep. Requested</th>
            <th>Ep. Assigned</th>
            <th>Status</th>
            <th>Created At</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr
              key={request.id}
              className="requests-table__row"
              onClick={() => onViewDetail(request)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onViewDetail(request)
                }
              }}
              tabIndex={0}
              role="button"
              aria-label={`View request ${request.id} for ${request.client_name}`}
            >
              <td title={request.id}>{request.id.slice(0, 8)}</td>
              <td>{request.client_name}</td>
              <td>{request.task_name}</td>
              <td>{request.episodes_requested}</td>
              <td>{request.episodes_assigned}</td>
              <td>{request.status}</td>
              <td>{new Date(request.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}