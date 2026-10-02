import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './AppLayout.css'

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const role = user?.role ?? ''
  const isOperatorOrAdmin = role === 'operator' || role === 'admin'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav__brand">
          <Link to="/requests">Dataset Request Desk</Link>
        </div>

        <ul className="app-nav__links">
          <li>
            <NavLink
              to="/requests"
              className={({ isActive }) => isActive ? 'app-nav__link is-active' : 'app-nav__link'}
            >
              Requests
            </NavLink>
          </li>

          {isOperatorOrAdmin && (
            <li>
              <NavLink
                to="/episodes"
                className={({ isActive }) => isActive ? 'app-nav__link is-active' : 'app-nav__link'}
              >
                Episodes
              </NavLink>
            </li>
          )}
        </ul>

        <div className="app-nav__user">
          {user && (
            <>
              <span className="app-nav__user-name">
                {user.username} <span className="muted">({role})</span>
              </span>
              <button className="btn btn-sm" onClick={handleLogout}>Logout</button>
            </>
          )}
        </div>
      </nav>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}