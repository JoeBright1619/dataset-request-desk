import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, clearTokens, ApiClientError } from '../api/client'
import { Request } from '../api/types'

function RequestsPage() {
  const [requests, setRequests] = useState<Request[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchRequests = async () => {
      try {
        const response = await get<{ items: Request[] }>('/requests')
        setRequests(response.items)
      } catch (err) {
        if (err instanceof ApiClientError) {
          if (err.code === 'AUTHENTICATION_REQUIRED') {
            clearTokens()
            navigate('/login')
            return
          }
          setError(`${err.code}: ${err.message}`)
        } else {
          setError('An unexpected error occurred')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchRequests()
  }, [navigate])

  const handleLogout = () => {
    clearTokens()
    navigate('/login')
  }

  if (loading) {
    return <div style={{ padding: '20px' }}>Loading...</div>
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h1>Requests</h1>
        <button onClick={handleLogout} style={{ padding: '8px 16px' }}>
          Logout
        </button>
      </div>
      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}
      <div>
        <p>Total requests: {requests.length}</p>
        {requests.length === 0 ? (
          <p>No requests found.</p>
        ) : (
          <ul style={{ listStyle: 'none' }}>
            {requests.map((req) => (
              <li key={req.id} style={{ marginBottom: '10px', padding: '10px', border: '1px solid #ccc' }}>
                <strong>ID:</strong> {req.id} | <strong>Task:</strong> {req.task_name} |{' '}
                <strong>Status:</strong> {req.status} | <strong>Episodes:</strong> {req.episodes_assigned}/
                {req.episodes_requested}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default RequestsPage
