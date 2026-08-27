import { NavLink } from 'react-router-dom';
import ProjectorProgress from './ProjectorProgress';
import { useAuth } from '../auth/AuthContext';
import './AppHeader.css';

export default function AppHeader() {
  const { configured, user, signOut } = useAuth();

  return (
    <header className="app-header">
      <div className="app-header-top">
        <NavLink to="/" className="app-header-brand">
          ScriptClear <span>AI</span>
        </NavLink>
        {configured && user ? (
          <div className="app-header-user">
            {user.photoURL ? (
              <img
                className="app-header-avatar"
                src={user.photoURL}
                alt=""
                referrerPolicy="no-referrer"
              />
            ) : null}
            <span className="app-header-email">
              {user.displayName || user.email}
            </span>
            <button
              type="button"
              className="app-header-signout"
              onClick={() => signOut()}
            >
              Sign out
            </button>
          </div>
        ) : null}
      </div>
      <ProjectorProgress />
    </header>
  );
}
