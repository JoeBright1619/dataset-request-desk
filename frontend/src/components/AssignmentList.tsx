import type { Assignment } from '../api/assignments'

interface Props {
  assignments: Assignment[]
  releasing: Record<string, boolean>
  onRelease: (episodeId: string) => void
  disabled?: boolean
}

export function AssignmentList({ assignments, releasing, onRelease, disabled }: Props) {
  if (assignments.length === 0) {
    return <p className="muted">No episodes assigned to this request yet.</p>
  }

  return (
    <ul className="assignment-list">
      {assignments.map((a) => {
        const busy = !!releasing[a.episode_id]
        return (
          <li key={a.episode_id} className="assignment-item">
            <div>
              <strong>{a.episode_id}</strong>{' '}
              <span className="muted">
                · {a.task_name} · {a.robot_id} · {a.quality}
              </span>
              <div className="muted small">
                Assigned {new Date(a.assigned_at).toLocaleString()}
              </div>
            </div>
            <button
              className="btn btn-sm btn-danger"
              onClick={() => onRelease(a.episode_id)}
              disabled={busy || disabled}
            >
              {busy ? '…' : 'Release'}
            </button>
          </li>
        )
      })}
    </ul>
  )
}