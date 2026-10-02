import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { RequireAuth } from './components/RequireAuth'
import LoginPage from './pages/LoginPage'
import RequestsPage from './pages/RequestsPage'
import EpisodesPage from './pages/EpisodesPage'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route 
            path="/requests" 
            element={
              <RequireAuth roles={['client', 'operator', 'admin']}>
                <RequestsPage />
              </RequireAuth>
            }
          />
          <Route 
            path="/episodes" 
            element={
              <RequireAuth roles={['operator', 'admin']}>
                <EpisodesPage />
              </RequireAuth>
            }
          />
          <Route path="/" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
