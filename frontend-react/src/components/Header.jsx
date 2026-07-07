import { useAuth } from '../context/AuthContext';
import styles from './Header.module.css';

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
    <header className={styles.header}>
      <div className={styles.headerLeft}>
        <img src="/favicon.svg" alt="Logo" width="28" height="28" style={{ marginRight: '10px' }} />
        <span className={styles.headerTitle}>{appName}</span>
      </div>
      <div className={styles.headerRight}>
        {user && <span className="header-user-email" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{user.email}</span>}
        {user && (
          <button className={styles.headerLogoutBtn} onClick={logout} title="Sign Out">
            Sign Out
          </button>
        )}
        <div className={styles.headerAvatar} title={user?.email || 'User'}>{initial}</div>
      </div>
    </header>
  );
}
