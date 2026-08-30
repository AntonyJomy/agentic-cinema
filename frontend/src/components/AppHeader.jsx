import { NavLink } from 'react-router-dom';
import ProjectorProgress from './ProjectorProgress';
import AccountDropdown from './AccountDropdown';
import { useAuth } from '../auth/AuthContext';
import './AppHeader.css';

export default function AppHeader({ tourState }) {
  const { configured } = useAuth();

  return (
    <header className="app-header">
      <div className="app-header-top">
        <NavLink to="/" className="app-header-brand">
          ScriptClear <span>AI</span>
        </NavLink>
        <div className="app-header-actions">
          <nav className="app-header-nav" aria-label="Workspace">
            <NavLink to="/dashboard" className="app-header-link">
              Dashboard
            </NavLink>
            <NavLink to="/upload" className="app-header-link">
              New clearance
            </NavLink>
          </nav>
          {configured && <AccountDropdown tourState={tourState} />}
        </div>
      </div>
      <ProjectorProgress />
    </header>
  );
}
