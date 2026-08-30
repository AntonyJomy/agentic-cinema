import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function RequireAuth({ children }) {
  const { configured, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (!configured) {
    return children;
  }

  if (loading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Checking sign-in…
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
