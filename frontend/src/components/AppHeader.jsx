import { NavLink } from 'react-router-dom';
import './AppHeader.css';

const NAV_ITEMS = [
  { to: '/upload', label: 'Upload' },
  { to: '/processing', label: 'Processing' },
  { to: '/findings', label: 'Findings' },
  { to: '/review', label: 'Review' },
  { to: '/reports', label: 'Reports' },
];

export default function AppHeader() {
  return (
    <header className="app-header">
      <NavLink to="/" className="app-header-brand">
        ScriptClear <span>AI</span>
      </NavLink>
      <nav className="app-header-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => 'app-header-link' + (isActive ? ' is-active' : '')}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
