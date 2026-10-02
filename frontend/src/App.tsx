import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { AppLayout } from './components/AppLayout'
import { RequireAuth } from './components/RequireAuth'
import LoginPage from './pages/LoginPage'
import RequestsPage from './pages/RequestsPage'
import EpisodesPage from './pages/EpisodesPage'
import RequestAssignmentsPage from './pages/RequestAssignmentsPage'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

                    <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/requests" replace />} />
            <Route path="/requests" element={<RequestsPage />} />
            <Route
              path="/episodes"
              element={
                <RequireAuth roles={['operator', 'admin']}>
                  <EpisodesPage />
                </RequireAuth>
              }
            />
            <Route
              path="/requests/:id/assignments"
              element={
                <RequireAuth roles={['operator', 'admin']}>
                  <RequestAssignmentsPage />
                </RequireAuth>
              }
            />
          </Route>

          <Route path="*" element={<Navigate to="/requests" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App