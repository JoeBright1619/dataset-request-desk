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
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr key={request.id}>
              <td>{request.id}</td>
              <td>{request.client_name}</td>
              <td>{request.task_name}</td>
              <td>{request.episodes_requested}</td>
              <td>{request.episodes_assigned}</td>
              <td>{request.status}</td>
              <td>{new Date(request.created_at).toLocaleString()}</td>
              <td>
                <button className="btn btn-sm" onClick={() => onViewDetail(request)}>
                  View Detail
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}