import { useAuth } from '../context/AuthContext';
import './Header.css';

/**
 * Header component displaying the application title, current authenticated user email,
 * logout option, and a user initials avatar.
 *
 * @component
 * @returns {React.JSX.Element} The rendered header bar.
 */
export default function Header() {
  const { user, logout } = useAuth();

  const initial = user?.email ? user.email.charAt(0).toUpperCase() : 'U';

  return (
    <header className="header">
      <div className="header-left">
        <svg className="header-icon" width="28" height="28" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="#6C63FF" strokeWidth="2" />
          <path d="M8 12l3 3 5-6" stroke="#6C63FF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="header-title">Milvus RAG Assistant</span>
      </div>
      <div className="header-right">
        {user && <span className="header-user-email" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{user.email}</span>}
        {user && (
          <button className="header-logout-btn" onClick={logout} title="Sign Out" style={{ fontSize: '13px', color: 'var(--accent)', fontWeight: 600, padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', transition: 'background 0.2s' }}>
            Sign Out
          </button>
        )}
        <div className="header-avatar" title={user?.email || 'User'}>{initial}</div>
      </div>
    </header>
  );
}
