import styles from './Sidebar.module.css';

/**
 * Sidebar component containing application navigation buttons.
 * Allows switching between Chat, Document Index, and Settings views.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {'chat'|'documents'|'settings'} props.activeView - Currently active application view.
 * @param {function('chat'|'documents'|'settings'): void} props.onViewChange - Handler to navigate to a new view.
 * @param {boolean} props.isDarkMode - Whether dark mode is currently active.
 * @param {function(): void} props.onToggleDarkMode - Handler to toggle between dark and light mode.
 * @returns {React.JSX.Element} The rendered navigation sidebar.
 */
export default function Sidebar({ activeView, onViewChange, isDarkMode, onToggleDarkMode }) {

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarLogo}>
        <img src="/favicon.svg" alt="Logo" width="24" height="24" />
      </div>

      <nav className={styles.sidebarNav}>
        <button
          className={`${styles.sidebarBtn} ${activeView === 'agent' ? styles.active : ''}`}
          onClick={() => onViewChange('agent')}
          title="AI Agent"
          aria-label="Industrial AI Agent"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
            <rect x="9" y="9" width="6" height="6" />
            <line x1="9" y1="1" x2="9" y2="4" />
            <line x1="15" y1="1" x2="15" y2="4" />
            <line x1="9" y1="20" x2="9" y2="23" />
            <line x1="15" y1="20" x2="15" y2="23" />
            <line x1="20" y1="9" x2="23" y2="9" />
            <line x1="20" y1="14" x2="23" y2="14" />
            <line x1="1" y1="9" x2="4" y2="9" />
            <line x1="1" y1="14" x2="4" y2="14" />
          </svg>
        </button>

        <button
          className={`${styles.sidebarBtn} ${activeView === 'chat' ? styles.active : ''}`}
          onClick={() => onViewChange('chat')}
          title="Chat"
          aria-label="Chat View"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>


        <button
          className={`${styles.sidebarBtn} ${activeView === 'review' ? styles.active : ''}`}
          onClick={() => onViewChange('review')}
          title="Safety Audit"
          aria-label="Safety Audit Dashboard"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </button>

        <button
          className={`${styles.sidebarBtn} ${activeView === 'tagCatalog' ? styles.active : ''}`}
          onClick={() => onViewChange('tagCatalog')}
          title="Tag Catalog"
          aria-label="Plant Tag Catalog & Asset Explorer"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
            <line x1="7" y1="7" x2="7.01" y2="7" />
          </svg>
        </button>

        <button
          className={`${styles.sidebarBtn} ${activeView === 'documents' ? styles.active : ''}`}
          onClick={() => onViewChange('documents')}
          title="Documents"
          aria-label="Indexed Documents Library"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
        </button>

        <button
          className={`${styles.sidebarBtn} ${activeView === 'settings' ? 'active' : ''}`}
          onClick={() => onViewChange('settings')}
          title="Settings"
          aria-label="Retrieval Settings"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
        </button>
      </nav>

      {/* Theme toggle button pinned to bottom */}
      <button
        className={styles.themeToggle}
        onClick={onToggleDarkMode}
        title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        aria-label="Toggle theme"
      >
        {isDarkMode ? (
          /* Sun icon — shown in dark mode, click to go light */
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="5" />
            <line x1="12" y1="1" x2="12" y2="3" />
            <line x1="12" y1="21" x2="12" y2="23" />
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
            <line x1="1" y1="12" x2="3" y2="12" />
            <line x1="21" y1="12" x2="23" y2="12" />
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
          </svg>
        ) : (
          /* Moon icon — shown in light mode, click to go dark */
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        )}
      </button>
    </aside>
  );
}
