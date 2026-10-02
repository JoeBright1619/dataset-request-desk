import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearTokens, ApiClientError } from '../api/client'
import { listRequests, updateRequestStatus } from '../api/requests'
import { useAuth } from '../context/AuthContext'
import type { Request} from '../api/types'
import { CreateRequestForm } from '../components/CreateRequestForm'
import { RequestList } from '../components/RequestList'
import "./RequestsPage.css";

function RequestsPage() {
  const [requests, setRequests] = useState<Request[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const navigate = useNavigate()
  const { logout, user } = useAuth()

  const refresh = useCallback(async () => {
    const { items } = await listRequests()
    setRequests(items)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { items } = await listRequests()
        if (!cancelled) setRequests(items)
      } catch (err) {
        if (err instanceof ApiClientError && err.code === 'AUTHENTICATION_REQUIRED') {
          clearTokens()
          navigate('/login')
          return
        }
        if (!cancelled) setError(err instanceof Error ? err.message : 'An unexpected error occurred')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [navigate, user])

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

  const handleAccept = (id: string) =>
    runAction(id, () => updateRequestStatus(id, 'accepted'))

  const handleReject = (id: string) => {
    const reason = window.prompt('Why are you rejecting this delivery?')
    if (reason === null) return
    const trimmed = reason.trim()
    if (!trimmed) return setError('A reason is required to reject a delivery.')
    return runAction(id, () => updateRequestStatus(id, 'rejected', trimmed))
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  if (loading) return <div className="page">Loading…</div>

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>Requests</h1>
          <p className="muted">View and manage your dataset requests</p>
        </div>
        <button className="btn" onClick={handleLogout}>Logout</button>
      </header>

      {error && <div className="alert">{error}</div>}

      <CreateRequestForm onCreated={refresh} />

      <section>
        <h2>Your Requests</h2>
        <RequestList
          requests={requests}
          actionLoading={actionLoading}
          onAccept={handleAccept}
          onReject={handleReject}
        />
      </section>
    </div>
  )
}

export default RequestsPage