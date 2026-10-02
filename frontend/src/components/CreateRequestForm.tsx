import { useState } from 'react'
import { createRequest } from '../api/requests'

interface Props {
  onCreated: () => void | Promise<void>
}

export function CreateRequestForm({ onCreated }: Props) {
  const [taskName, setTaskName] = useState('')
  const [episodesRequested, setEpisodesRequested] = useState('')
  const [deadline, setDeadline] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await createRequest({
        task_name: taskName,
        episodes_requested: parseInt(episodesRequested, 10),
        deadline,
        notes: notes || undefined,
      })
      setTaskName('')
      setEpisodesRequested('')
      setDeadline('')
      setNotes('')
      await onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Create New Request</h2>
      {error && <div className="alert">{error}</div>}
      <form onSubmit={handleSubmit} className="create-form">
        <div>
          <label htmlFor="taskName">Task Name</label>
          <input id="taskName" value={taskName} onChange={(e) => setTaskName(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="episodesRequested">Episodes Requested</label>
          <input id="episodesRequested" type="number" min="1" value={episodesRequested} onChange={(e) => setEpisodesRequested(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="deadline">Deadline</label>
          <input id="deadline" type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        </div>
        <div>
          <label htmlFor="notes">Notes</label>
          <textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="create-form__actions">
          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading ? 'Creating…' : 'Create Request'}
          </button>
        </div>
      </form>
    </div>
  )
}