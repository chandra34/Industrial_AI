import './Sidebar.css';

/**
 * Sidebar component containing application navigation buttons.
 * Allows switching between Chat, Document Index, and Settings views.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {'chat'|'documents'|'settings'} props.activeView - Currently active application view.
 * @param {function('chat'|'documents'|'settings'): void} props.onViewChange - Handler to navigate to a new view.
 * @returns {React.JSX.Element} The rendered navigation sidebar.
 */
export default function Sidebar({ activeView, onViewChange }) {

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img src="/favicon.svg" alt="Logo" width="24" height="24" />
      </div>

      <nav className="sidebar-nav">
        <button
          className={`sidebar-btn ${activeView === 'chat' ? 'active' : ''}`}
          onClick={() => onViewChange('chat')}
          title="Chat"
          aria-label="Chat View"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>

        <button
          className={`sidebar-btn ${activeView === 'review' ? 'active' : ''}`}
          onClick={() => onViewChange('review')}
          title="Safety Audit"
          aria-label="Safety Audit Dashboard"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </button>

        <button
          className={`sidebar-btn ${activeView === 'documents' ? 'active' : ''}`}
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
          className={`sidebar-btn ${activeView === 'settings' ? 'active' : ''}`}
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
    </aside>
  );
}
