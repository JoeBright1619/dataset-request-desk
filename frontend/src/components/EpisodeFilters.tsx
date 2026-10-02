import type { EpisodeQuality } from '../api/episodes'

const QUALITY_OPTIONS: Array<{ value: EpisodeQuality | ''; label: string }> = [
  { value: '', label: 'Any' },
  { value: 'good', label: 'Good' },
  { value: 'usable', label: 'Usable' },
  { value: 'bad', label: 'Bad' },
]

interface Props {
  taskName: string
  quality: EpisodeQuality | ''
  robotId: string
  recordedFrom: string
  recordedTo: string
  assigned: 'any' | 'true' | 'false'
  disabled?: boolean
  onChange: (patch: Partial<Omit<Props, 'disabled' | 'onChange'>>) => void
}

export function EpisodeFilters({
  taskName, quality, robotId, recordedFrom, recordedTo, assigned, disabled, onChange,
}: Props) {
  return (
    <div className="filters">
      <label>
        Task name
        <input
          type="text"
          value={taskName}
          onChange={(e) => onChange({ taskName: e.target.value })}
          disabled={disabled}
          placeholder="Search task"
        />
      </label>
      <label>
        Quality
        <select
          value={quality}
          onChange={(e) => onChange({ quality: e.target.value as EpisodeQuality | '' })}
          disabled={disabled}
        >
          {QUALITY_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label>
        Robot
        <input
          type="text"
          value={robotId}
          onChange={(e) => onChange({ robotId: e.target.value })}
          disabled={disabled}
          placeholder="robot id"
        />
      </label>
      <label>
        Recorded from
        <input
          type="datetime-local"
          value={recordedFrom}
          onChange={(e) => onChange({ recordedFrom: e.target.value })}
          disabled={disabled}
        />
      </label>
      <label>
        Recorded to
        <input
          type="datetime-local"
          value={recordedTo}
          onChange={(e) => onChange({ recordedTo: e.target.value })}
          disabled={disabled}
        />
      </label>
      <label>
        Assigned
        <select
          value={assigned}
          onChange={(e) => onChange({ assigned: e.target.value as Props['assigned'] })}
          disabled={disabled}
        >
          <option value="any">Any</option>
          <option value="false">Unassigned only</option>
          <option value="true">Assigned only</option>
        </select>
      </label>
    </div>
  )
}