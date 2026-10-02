import type { Episode } from '../api/episodes'

interface SelectionConfig {
  selected: Set<string>
  onToggle: (episodeId: string) => void
  onToggleAll: (checked: boolean) => void
  disabled?: boolean
}

interface Props {
  episodes: Episode[]
  selection?: SelectionConfig
}

export function EpisodeTable({ episodes, selection }: Props) {
  if (episodes.length === 0) {
    return <p className="muted">No episodes match the current filters.</p>
  }

  const selectable = !!selection
  const assignable = episodes.filter((e) => !e.is_assigned)
  const allChecked =
    selectable &&
    assignable.length > 0 &&
    assignable.every((e) => selection.selected.has(e.episode_id))

  return (
    <table className="episode-table">
      <thead>
        <tr>
          {selectable && (
            <th>
              <input
                type="checkbox"
                checked={allChecked}
                onChange={(e) => selection.onToggleAll(e.target.checked)}
                disabled={selection.disabled || assignable.length === 0}
                aria-label="Select all unassigned on this page"
              />
            </th>
          )}
          <th>Episode</th>
          <th>Robot</th>
          <th>Task</th>
          <th>Quality</th>
          <th>Duration</th>
          <th>Operator</th>
          <th>Recorded</th>
          <th>Assigned</th>
        </tr>
      </thead>
      <tbody>
        {episodes.map((ep) => (
          <tr key={ep.id}>
            {selectable && (
              <td>
                <input
                  type="checkbox"
                  checked={selection.selected.has(ep.episode_id)}
                  onChange={() => selection.onToggle(ep.episode_id)}
                  disabled={selection.disabled || ep.is_assigned}
                  aria-label={`Select episode ${ep.episode_id}`}
                />
              </td>
            )}
            <td>{ep.episode_id}</td>
            <td>{ep.robot_id}</td>
            <td>{ep.task_name}</td>
            <td>{ep.quality}</td>
            <td>{formatDuration(ep.duration_seconds)}</td>
            <td>{ep.operator_name ?? '—'}</td>
            <td>{new Date(ep.recorded_at).toLocaleString()}</td>
            <td>{ep.is_assigned ? 'yes' : 'no'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function formatDuration(raw: string): string {
  const seconds = Number(raw)
  if (!Number.isFinite(seconds)) return raw
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}