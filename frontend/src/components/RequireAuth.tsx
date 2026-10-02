import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface RequireAuthProps {
  children: React.ReactNode;
  roles?: ('client' | 'operator' | 'admin')[];
}

export function RequireAuth({ children, roles }: RequireAuthProps) {
  const { user, isAuthenticated } = useAuth();

  // If not authenticated, redirect to login
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  // If roles are specified, check if user has required role
  if (roles && roles.length > 0) {
    if (!user.role || !roles.includes(user.role as 'client' | 'operator' | 'admin')) {
      // Show error instead of redirecting to login
      return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
          <h2>Access Denied</h2>
          <p>You do not have permission to access this page.</p>
          <p>Your role: {user.role}</p>
          <p>Required roles: {roles.join(', ')}</p>
        </div>
      );
    }
  }

  return <>{children}</>;
}