import { useEffect, useMemo, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiClientError, clearTokens, get } from '../api/client'
import type { Request } from '../api/types'
import {
  listAssignments,
  assignEpisodes,
  releaseAssignment,
  type Assignment,
} from '../api/assignments'
import type { EpisodeQuality } from '../api/episodes'
import { useAuth } from '../context/AuthContext'
import { useEpisodeSearch } from '../hooks/useEpisodeSearch'
import { EpisodeFilters } from '../components/EpisodeFilters'
import { EpisodeTable } from '../components/EpisodeTable'
import { AssignmentList } from '../components/AssignmentList'
import './RequestAssignmentsPage.css'

interface Filters {
  taskName: string
  quality: EpisodeQuality | ''
  robotId: string
  recordedFrom: string
  recordedTo: string
  assigned: 'any' | 'true' | 'false'
}

const EMPTY_FILTERS: Filters = {
  taskName: '',
  quality: '',
  robotId: '',
  recordedFrom: '',
  recordedTo: '',
  assigned: 'any',
}

export default function RequestAssignmentsPage() {
  const { id: requestId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()
  const role = user?.role ?? ''
  const canEdit = role === 'operator' || role === 'admin'

  const [request, setRequest] = useState<Request | null>(null)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [releasing, setReleasing] = useState<Record<string, boolean>>({})
  const [assigning, setAssigning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [filtersInput, setFiltersInput] = useState<Filters>(EMPTY_FILTERS)
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)

  // Debounce text-ish filters
  useEffect(() => {
    const id = setTimeout(() => setFilters(filtersInput), 300)
    return () => clearTimeout(id)
  }, [filtersInput])

  const {
    episodes,
    meta,
    next,
    prev,
    canPrev,
    refresh: refreshEpisodes,
  } = useEpisodeSearch({
    taskName: filters.taskName || undefined,
    quality: filters.quality || undefined,
    robotId: filters.robotId || undefined,
    recordedFrom: filters.recordedFrom || undefined,
    recordedTo: filters.recordedTo || undefined,
    assigned: filters.assigned === 'any' ? undefined : filters.assigned === 'true',
  })

  // Load request + initial assignments
  useEffect(() => {
    if (!requestId) return
    let cancelled = false
    ;(async () => {
      try {
        const [req, asg] = await Promise.all([
          get<Request>(`/requests/${requestId}`),
          listAssignments(requestId),
        ])
        if (cancelled) return
        setRequest(req)
        setAssignments(asg.items)
      } catch (err) {
        if (err instanceof ApiClientError && err.code === 'AUTHENTICATION_REQUIRED') {
          clearTokens()
          navigate('/login')
          return
        }
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unexpected error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [requestId, navigate])

  // Drop selections that are no longer on the visible page
  useEffect(() => {
    const visible = new Set(episodes.map((e) => e.episode_id))
    setSelected((prev) => new Set([...prev].filter((id) => visible.has(id))))
  }, [episodes])

  const refreshAssignments = useCallback(async () => {
    if (!requestId) return
    const [asg, req] = await Promise.all([
      listAssignments(requestId),
      get<Request>(`/requests/${requestId}`),
    ])
    setAssignments(asg.items)
    setRequest(req)
    await refreshEpisodes()
  }, [requestId, refreshEpisodes])

  const handleToggle = (episodeId: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(episodeId) ? next.delete(episodeId) : next.add(episodeId)
      return next
    })
  }

  const handleToggleAll = (checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      const assignable = episodes.filter((e) => !e.is_assigned).map((e) => e.episode_id)
      if (checked) assignable.forEach((id) => next.add(id))
      else assignable.forEach((id) => next.delete(id))
      return next
    })
  }

  const handleAssign = async () => {
    if (!requestId || selected.size === 0) return
    setAssigning(true)
    setError(null)
    try {
      const res = await assignEpisodes(requestId, [...selected])
      setSelected(new Set())
      await refreshAssignments()
      if (res.rejected.length > 0) {
        setError(
          `${res.rejected.length} episode(s) could not be assigned: ` +
          res.rejected.map((r) => `${r.episode_id} (${r.reason})`).join(', '),
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setAssigning(false)
    }
  }

  const handleRelease = async (episodeId: string) => {
    if (!requestId) return
    setReleasing((prev) => ({ ...prev, [episodeId]: true }))
    setError(null)
    try {
      await releaseAssignment(requestId, episodeId)
      await refreshAssignments()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setReleasing((prev) => ({ ...prev, [episodeId]: false }))
    }
  }

  const progress = useMemo(() => {
    if (!request) return null
    return { assigned: request.episodes_assigned, requested: request.episodes_requested }
  }, [request])

  if (loading) return <div className="page">Loading…</div>
  if (!request) return <div className="page">Request not found.</div>

  const editable =
    canEdit && (request.status === 'submitted' || request.status === 'in_progress')

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>Assign episodes</h1>
          <p className="muted">
            {request.task_name} · {request.client_name} · status: <strong>{request.status}</strong>
          </p>
          {progress && (
            <p className="muted">
              Assigned: <strong>{progress.assigned} / {progress.requested}</strong>
            </p>
          )}
        </div>
        <button className="btn" onClick={() => navigate(-1)}>Back</button>
      </header>

      {error && <div className="alert">{error}</div>}

      {!editable && (
        <div className="notice">
          This request is <strong>{request.status}</strong>. Assignments can only be
          changed while a request is <em>submitted</em> or <em>in_progress</em>.
        </div>
      )}

      <div className="assign-grid">
        <section className="panel">
          <h2>Assigned episodes ({assignments.length})</h2>
          <AssignmentList
            assignments={assignments}
            releasing={releasing}
            onRelease={handleRelease}
            disabled={!editable || assigning}
          />
        </section>

        <section className="panel">
          <h2>Find episodes</h2>
          <EpisodeFilters
            {...filtersInput}
            disabled={assigning}
            onChange={(patch) => setFiltersInput((f) => ({ ...f, ...patch }))}
          />

          <EpisodeTable
            episodes={episodes}
            selection={{
              selected,
              onToggle: handleToggle,
              onToggleAll: handleToggleAll,
              disabled: !editable || assigning,
            }}
          />

          <div className="pagination">
            <button className="btn" onClick={prev} disabled={!canPrev || assigning}>
              ← Previous
            </button>
            <button className="btn" onClick={next} disabled={!meta.hasMore || assigning}>
              Next →
            </button>
          </div>

          <div className="assign-actions">
            <span className="muted">{selected.size} selected</span>
            <button
              className="btn btn-primary"
              onClick={handleAssign}
              disabled={!editable || selected.size === 0 || assigning}
            >
              {assigning ? 'Assigning…' : `Assign ${selected.size || ''}`.trim()}
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}