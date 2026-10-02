import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearTokens, ApiClientError } from '../api/client'
import { listRequests, updateRequestStatus } from '../api/requests'
import { useAuth } from '../context/AuthContext'
import type { Request, RequestStatus } from '../api/types'
import { getAllowedTransitions, type UserRole } from '../lib/transitions'
import { CreateRequestForm } from '../components/CreateRequestForm'
import { RequestList } from '../components/RequestList'
import { OperatorRequestsTable } from '../components/OperatorRequestsTable'
import { RequestDetailModal } from '../components/RequestDetailModal'
import './RequestsPage.css'

function RequestsPage() {
  const [requests, setRequests] = useState<Request[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const [detailId, setDetailId] = useState<string | null>(null)
  const [transitioning, setTransitioning] = useState(false)

  // Filters
  const [status, setStatus] = useState<RequestStatus | ''>('')
  const [taskNameInput, setTaskNameInput] = useState('')
  const [taskNameFilter, setTaskNameFilter] = useState('')

  // Pagination
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const [cursorStack, setCursorStack] = useState<string[]>([])   // ← Bug 1 fix
  const [pageMeta, setPageMeta] = useState({
    hasMore: false,
    hasPrev: false,
    nextCursor: null as string | null,
    limit: 50,
  })

  const hasActiveFilters = !!status || !!taskNameFilter

  const navigate = useNavigate()
  const { user } = useAuth()
  const role = (user?.role ?? '') as UserRole | ''
  const isClient = role === 'client'

  // Debounce task-name input
  useEffect(() => {
    const id = setTimeout(() => setTaskNameFilter(taskNameInput), 300)
    return () => clearTimeout(id)
  }, [taskNameInput])

  // Reset cursor whenever filters change (guarded against mount)
  const filtersKey = `${status}|${taskNameFilter}`
  const lastFiltersKey = useRef(filtersKey)
  useEffect(() => {
    if (lastFiltersKey.current !== filtersKey) {
      setCursor(undefined)
      setCursorStack([])
      lastFiltersKey.current = filtersKey
    }
  }, [filtersKey])

  // Fetch
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    ;(async () => {
      try {
        const page = await listRequests({
          status: status || undefined,
          taskName: taskNameFilter || undefined,
          cursor,
          limit: 50,
        })
        if (cancelled) return
        setRequests(page.items)
        setPageMeta({
          hasMore: page.has_more,
          hasPrev: page.has_prev,
          nextCursor: page.next_cursor,   // ← Bug 3 fix
          limit: page.limit,
        })
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
  }, [status, taskNameFilter, cursor, user, navigate])

  const refresh = useCallback(async () => {
    const page = await listRequests({
      status: status || undefined,
      taskName: taskNameFilter || undefined,
      cursor,
      limit: 50,
    })
    setRequests(page.items)
    setPageMeta({                          // ← Bug 2 fix
      hasMore: page.has_more,
      hasPrev: page.has_prev,
      nextCursor: page.next_cursor,
      limit: page.limit,
    })
  }, [status, taskNameFilter, cursor])

  const handleNext = () => {
    if (!pageMeta.hasMore || !pageMeta.nextCursor) return
    setCursorStack((s) => [...s, cursor ?? ''])
    setCursor(pageMeta.nextCursor)
  }

  const handlePrev = () => {
    if (cursorStack.length === 0) return
    const prev = cursorStack[cursorStack.length - 1]
    setCursorStack((s) => s.slice(0, -1))
    setCursor(prev || undefined)
  }

  const runAction = async (id: string, fn: () => Promise<unknown>) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }))
    setError(null)
    try {
      await fn()
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }))
    }
  }

  const handleStatusChange = (next: RequestStatus | '') => {
  setStatus(next)
  setCursor(undefined)
  setCursorStack([])
}
  // Single source of truth for all status transitions
  const handleTransition = async (id: string, status: RequestStatus, reason?: string) => {
    setTransitioning(true)
    setError(null)
    try {
      await updateRequestStatus(id, status, reason)
      await refresh()
      setDetailId(null) // close modal; re-open reflects fresh data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setTransitioning(false)
    }
  }

  // Client helpers — route through the same transition function
  const handleAccept = (id: string) => runAction(id, () => updateRequestStatus(id, 'accepted'))
  const handleReject = (id: string) => {
    const reason = window.prompt('Why are you rejecting this delivery?')
    if (reason === null) return
    const trimmed = reason.trim()
    if (!trimmed) {
      setError('A reason is required to reject a delivery.')
      return
    }
    return runAction(id, () => updateRequestStatus(id, 'rejected', trimmed))
  }
  // Derive the modal's request from the CURRENT list so it never goes stale
  const detailRequest = useMemo(
    () => (detailId ? requests.find((r) => r.id === detailId) ?? null : null),
    [detailId, requests],
  )

  const detailTransitions = useMemo(
    () => (detailRequest ? getAllowedTransitions(detailRequest, role) : []),
    [detailRequest, role],
  )

  if (loading && requests.length === 0) return <div className="page">Loading…</div>

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>{isClient ? 'Requests' : 'All Requests'}</h1>
          <p className="muted">
            {isClient
              ? 'View and manage your dataset requests'
              : 'View and manage all dataset requests'}
          </p>
        </div>
      </header>
      {error && <div className="alert">{error}</div>}

      <div className="filters">
        <label>
          Status
          <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value as RequestStatus | '')}
              disabled={loading}
            >
            <option value="">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="in_progress">In progress</option>
            <option value="delivered">Delivered</option>
            <option value="accepted">Accepted</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
        <label>
          Task name
          <input
            type="text"
            value={taskNameInput}
            onChange={(e) => setTaskNameInput(e.target.value)}
            placeholder="Search by task name"
            disabled={loading}
          />
        </label>
      </div>
      {isClient ? (
        <>
          <CreateRequestForm onCreated={refresh} />
          <section>
            <h2>Your Requests</h2>
            {requests.length === 0
  ? <p className="muted">
      {hasActiveFilters
        ? 'No requests match the current filters.'
        : 'No requests yet. Create one above to get started.'}
    </p>
  : <RequestList
              requests={requests}
              actionLoading={actionLoading}
              onAccept={handleAccept}
              onReject={handleReject}
            />}
          </section>
        </>
      ) : (
        <section>
          <h2>Requests List</h2>
          <OperatorRequestsTable
            requests={requests}
            onViewDetail={(r) => setDetailId(r.id)}
          />
        </section>
      )}
<div className="pagination">
        <button className="btn" onClick={handlePrev} disabled={cursorStack.length === 0 || loading}>
          ← Previous
        </button>
        <button className="btn" onClick={handleNext} disabled={!pageMeta.hasMore || loading}>
          Next →
        </button>
      </div>
      {detailRequest && (
        <RequestDetailModal
          request={detailRequest}
          transitions={detailTransitions}
          submitting={transitioning}
          onClose={() => setDetailId(null)}
          onSubmit={(status, reason) => handleTransition(detailRequest.id, status, reason)}
        />
      )}
    </div>
  )
}

export default RequestsPage