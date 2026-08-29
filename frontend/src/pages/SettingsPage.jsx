import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import './SettingsPage.css';

export default function SettingsPage() {
  const { user, signOut, getIdToken } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchProfile() {
      try {
        const token = await getIdToken();
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          throw new Error('Failed to load profile');
        }

        const data = await response.json();
        setProfile(data);
      } catch (err) {
        console.error('Profile fetch error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchProfile();
  }, [getIdToken]);

  const getRoleBadge = (role) => {
    if (role === 'legal_reviewer') {
      return { text: 'Legal Reviewer', className: 'settings-role-badge-legal' };
    }
    return { text: 'Standard User', className: 'settings-role-badge-standard' };
  };

  return (
    <div className="settings-page">
      <div className="settings-container">
        <header className="settings-header">
          <h1 className="settings-title">Settings</h1>
          <p className="settings-subtitle">
            Manage your account and clearance preferences
          </p>
        </header>

        {loading && (
          <div className="settings-loading">Loading profile...</div>
        )}

        {error && (
          <div className="settings-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!loading && !error && profile && (
          <>
            {/* Profile Section */}
            <section className="settings-section">
              <h2 className="settings-section-title">Profile</h2>
              <div className="settings-card">
                <div className="settings-profile-header">
                  {user?.photoURL && (
                    <img
                      className="settings-avatar"
                      src={user.photoURL}
                      alt=""
                      referrerPolicy="no-referrer"
                    />
                  )}
                  <div className="settings-profile-info">
                    <div className="settings-field">
                      <label className="settings-label">Name</label>
                      <div className="settings-value">{profile.name}</div>
                    </div>
                    <div className="settings-field">
                      <label className="settings-label">Email</label>
                      <div className="settings-value">{profile.email}</div>
                    </div>
                    <div className="settings-field">
                      <label className="settings-label">Role</label>
                      <span
                        className={`settings-role-badge ${
                          getRoleBadge(profile.role).className
                        }`}
                      >
                        {getRoleBadge(profile.role).text}
                      </span>
                    </div>
                  </div>
                </div>
                <p className="settings-notice">
                  Profile information is managed through your Google account
                  and cannot be edited here.
                </p>
              </div>
            </section>

            {/* Quick Actions */}
            <section className="settings-section">
              <h2 className="settings-section-title">Quick Actions</h2>
              <div className="settings-card">
                <Link to="/dashboard" className="settings-action-link">
                  <span className="settings-action-icon">📋</span>
                  <div>
                    <div className="settings-action-title">
                      My Clearance Runs
                    </div>
                    <div className="settings-action-description">
                      View all your script clearance history
                    </div>
                  </div>
                  <span className="settings-action-arrow">→</span>
                </Link>
              </div>
            </section>

            {/* Account Management */}
            <section className="settings-section">
              <h2 className="settings-section-title">Account</h2>
              <div className="settings-card">
                <button
                  type="button"
                  className="settings-signout-btn"
                  onClick={() => signOut()}
                >
                  Sign Out
                </button>
                <p className="settings-signout-note">
                  You will be redirected to the login page
                </p>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
