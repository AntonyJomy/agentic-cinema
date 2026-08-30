import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import './AccountDropdown.css';

export default function AccountDropdown({ tourState }) {
  const { user, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleTakeTour = () => {
    setIsOpen(false);
    if (tourState?.startTour) {
      tourState.startTour();
    }
  };

  if (!user) return null;

  return (
    <div className="account-dropdown" ref={dropdownRef}>
      <button
        type="button"
        className="account-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        {user.photoURL && (
          <img
            className="account-dropdown-avatar"
            src={user.photoURL}
            alt=""
            referrerPolicy="no-referrer"
          />
        )}
        <span className="account-dropdown-name">
          {user.displayName || user.email}
        </span>
        <svg
          className={`account-dropdown-chevron ${isOpen ? 'open' : ''}`}
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4 6L8 10L12 6"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {isOpen && (
        <div className="account-dropdown-menu">
          <Link
            to="/settings"
            className="account-dropdown-item"
            onClick={() => setIsOpen(false)}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M13 8C13 8.55228 12.5523 9 12 9C11.4477 9 11 8.55228 11 8C11 7.44772 11.4477 7 12 7C12.5523 7 13 7.44772 13 8Z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M5 8C5 8.55228 4.55228 9 4 9C3.44772 9 3 8.55228 3 8C3 7.44772 3.44772 7 4 7C4.55228 7 5 7.44772 5 8Z"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
            Settings
          </Link>

          <Link
            to="/dashboard"
            className="account-dropdown-item"
            onClick={() => setIsOpen(false)}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect
                x="2"
                y="2"
                width="5"
                height="5"
                rx="1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <rect
                x="9"
                y="2"
                width="5"
                height="5"
                rx="1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <rect
                x="2"
                y="9"
                width="5"
                height="5"
                rx="1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <rect
                x="9"
                y="9"
                width="5"
                height="5"
                rx="1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
            </svg>
            My Clearance Runs
          </Link>

          {tourState && (
            <button
              type="button"
              className="account-dropdown-item"
              onClick={handleTakeTour}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M8 5V8L10 10"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
              Take the tour
            </button>
          )}

          <div className="account-dropdown-divider" />

          <button
            type="button"
            className="account-dropdown-item account-dropdown-signout"
            onClick={() => {
              setIsOpen(false);
              signOut();
            }}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M6 14H3C2.44772 14 2 13.5523 2 13V3C2 2.44772 2.44772 2 3 2H6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <path
                d="M11 11L14 8L11 5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M14 8H6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
