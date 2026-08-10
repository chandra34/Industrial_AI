import { useState, useEffect, lazy, Suspense } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import DocumentsPanel from './components/DocumentsPanel';
import UploadModal from './components/UploadModal';
import SettingsPanel from './components/SettingsPanel';
import { useAuth } from './context/AuthContext';
import { useChat } from './hooks/useChat';
import { useAgentChat } from './hooks/useAgentChat';
import { useDocuments } from './hooks/useDocuments';

const LandingPage = lazy(() => import('./components/LandingPage'));
const SafetyReviewDashboard = lazy(() => import('./components/SafetyReviewDashboard'));
const AgentChatArea = lazy(() => import('./components/AgentChatArea'));
const TagCatalogPanel = lazy(() => import('./components/TagCatalogPanel'));

/**
 * The main App layout component managing the RAG application lifecycle.
 * Orchestrates views (chat, agent, review, tagCatalog, documents, settings) and coordinates
 * state slices fetched via decoupled custom hooks.
 *
 * @component
 * @returns {React.JSX.Element} The rendered RAG workspace or the LandingPage.
 */
export default function App() {
  const { user } = useAuth();
  
  /** @type {['chat'|'agent'|'review'|'tagCatalog'|'documents'|'settings', function(string): void]} */
  const [activeView, setActiveView] = useState('chat');
  
  /** @type {[boolean, function(boolean): void]} */
  const [showUpload, setShowUpload] = useState(false);

  /** Dark/Light theme state, persisted in localStorage. */
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved === 'dark';
  });

  // Sync body class and localStorage whenever theme changes
  useEffect(() => {
    document.body.classList.toggle('dark-theme', isDarkMode);
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  // Hook-based state slices and actions
  const { 
    messages, 
    isLoading, 
    topK, 
    setTopK, 
    handleSend, 
    clearMessages 
  } = useChat();

  const {
    messages: agentMessages,
    isLoading: agentIsLoading,
    handleSend: handleAgentSend,
    clearMessages: clearAgentMessages,
  } = useAgentChat();

  const { 
    documents, 
    handleDeleteDocument, 
    handleUploaded, 
    clearDocuments 
  } = useDocuments(user);

  // Synchronize component states on user session swaps
  useEffect(() => {
    if (!user) {
      clearMessages();
      clearAgentMessages();
      clearDocuments();
      setShowUpload(false);
      return;
    }
    clearMessages();
    clearAgentMessages();
    setShowUpload(false);
  }, [user, clearMessages, clearAgentMessages, clearDocuments]);

  if (!user) {
    return (
      <Suspense fallback={<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', width: '100vw', background: 'var(--main-bg)', fontSize: '16px', color: 'var(--text-secondary)' }}>Loading Page...</div>}>
        <LandingPage />
      </Suspense>
    );
  }

  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} onViewChange={setActiveView} isDarkMode={isDarkMode} onToggleDarkMode={() => setIsDarkMode(prev => !prev)} />

      <div className="app-main">
        <Header />

        <div className="app-content">
          <Suspense fallback={<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', width: '100%', fontSize: '14px', color: 'var(--text-secondary)' }}>Loading view...</div>}>
            {activeView === 'chat' && (
              <ChatArea
                messages={messages}
                isLoading={isLoading}
                onSend={handleSend}
                onUploadClick={() => setShowUpload(true)}
              />
            )}

            {activeView === 'agent' && (
              <AgentChatArea
                messages={agentMessages}
                isLoading={agentIsLoading}
                onSend={handleAgentSend}
              />
            )}

            {activeView === 'review' && (
              <SafetyReviewDashboard />
            )}

            {activeView === 'tagCatalog' && (
              <TagCatalogPanel />
            )}


            {activeView === 'documents' && (
              <DocumentsPanel
                documents={documents}
                onUploadClick={() => setShowUpload(true)}
                onDelete={handleDeleteDocument}
              />
            )}

            {activeView === 'settings' && (
              <SettingsPanel 
                topK={topK} 
                onTopKChange={setTopK} 
              />
            )}
          </Suspense>
        </div>
      </div>

      <UploadModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onUploaded={handleUploaded}
      />
    </div>
  );
}
