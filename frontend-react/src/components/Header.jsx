import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import styles from './Header.module.css';
import { getOpcuaProfiles } from '../api/client';

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
  const [activeOpcua, setActiveOpcua] = useState(null);

  useEffect(() => {
    if (!user) return;
    
    const fetchActiveProfile = async () => {
      try {
        const profiles = await getOpcuaProfiles();
        const active = profiles.find(p => p.is_active);
        setActiveOpcua(active || null);
      } catch (err) {
        // Fail silently during initial server setup
      }
    };

    fetchActiveProfile();
    const interval = setInterval(fetchActiveProfile, 5000);
    return () => clearInterval(interval);
  }, [user]);

  const initial = user?.email ? user.email.charAt(0).toUpperCase() : 'U';

  return (
    <header className={styles.header}>
      <div className={styles.headerLeft}>
        <span className={styles.headerTitle}>{appName}</span>
        {user && (
          <div className={styles.opcuaPill} title={activeOpcua ? `Connected to ${activeOpcua.endpoint_url}` : 'No active PLC connection'}>
            <span className={`${styles.opcuaDot} ${activeOpcua ? styles.opcuaDotActive : styles.opcuaDotInactive}`} />
            <span className={styles.opcuaLabel}>
              {activeOpcua ? activeOpcua.name : 'OPC UA Offline'}
            </span>
          </div>
        )}
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
