import type { RequestStatus } from '../api/types'

const STATUS_OPTIONS: Array<{ value: RequestStatus | ''; label: string }> = [
  { value: '', label: 'All statuses' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
]

interface Props {
  status: RequestStatus | ''
  taskName: string
  onChangeStatus: (v: RequestStatus | '') => void
  onChangeTaskName: (v: string) => void
}

export function RequestFilters({ status, taskName, onChangeStatus, onChangeTaskName }: Props) {
  return (
    <div className="filters">
      <label>
        Status
        <select value={status} onChange={(e) => onChangeStatus(e.target.value as RequestStatus | '')}>
          {STATUS_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label>
        Task name
        <input
          type="text"
          value={taskName}
          onChange={(e) => onChangeTaskName(e.target.value)}
          placeholder="Search by task name"
        />
      </label>
    </div>
  )
}