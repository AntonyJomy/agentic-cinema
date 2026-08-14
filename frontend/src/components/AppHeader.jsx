import { NavLink } from 'react-router-dom';
import ProjectorProgress from './ProjectorProgress';
import './AppHeader.css';

export default function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header-top">
        <NavLink to="/" className="app-header-brand">
          ScriptClear <span>AI</span>
        </NavLink>
      </div>
      <ProjectorProgress />
    </header>
  );
}
