import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { get, clearTokens, ApiClientError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Episode } from '../api/types'

function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchEpisodes = async () => {
      try {
        const response = await get<{ items: Episode[] }>('/episodes')
        setEpisodes(response.items)
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

    fetchEpisodes()
  }, [navigate])

  const handleLogout = () => {
    const { logout } = useAuth();
    logout();
    navigate('/login');
  }

  if (loading) {
    return <div style={{ padding: '20px' }}>Loading...</div>
  }

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h1>Episodes</h1>
        <button onClick={handleLogout} style={{ padding: '8px 16px' }}>
          Logout
        </button>
      </div>
      {error && <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>}
      <div>
        <p>Total episodes: {episodes.length}</p>
        {episodes.length === 0 ? (
          <p>No episodes found.</p>
        ) : (
          <ul style={{ listStyle: 'none' }}>
            {episodes.map((ep) => (
              <li key={ep.episode_id} style={{ marginBottom: '10px', padding: '10px', border: '1px solid #ccc' }}>
                <strong>ID:</strong> {ep.episode_id} | <strong>Task:</strong> {ep.task_name} |{' '}
                <strong>Robot:</strong> {ep.robot_id} | <strong>Quality:</strong> {ep.quality}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default EpisodesPage
