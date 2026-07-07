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
  const appName = import.meta.env.VITE_APP_NAME || 'Milvus RAG Assistant';

  const initial = user?.email ? user.email.charAt(0).toUpperCase() : 'U';

  return (
    <header className="header">
      <div className="header-left">
        <img src="/favicon.svg" alt="Logo" width="28" height="28" style={{ marginRight: '10px' }} />
        <span className="header-title">{appName}</span>
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
