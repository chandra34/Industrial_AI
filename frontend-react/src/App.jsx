import { useState, useEffect, lazy, Suspense } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import DocumentsPanel from './components/DocumentsPanel';
import UploadModal from './components/UploadModal';
import SettingsPanel from './components/SettingsPanel';
import { useAuth } from './context/AuthContext';
import { useChat } from './hooks/useChat';
import { useDocuments } from './hooks/useDocuments';

const LandingPage = lazy(() => import('./components/LandingPage'));
const SafetyReviewDashboard = lazy(() => import('./components/SafetyReviewDashboard'));

/**
 * The main App layout component managing the RAG application lifecycle.
 * Orchestrates views (chat, documents, settings, safety reviews) and coordinates
 * state slices fetched via decoupled custom hooks.
 *
 * @component
 * @returns {React.JSX.Element} The rendered RAG workspace or the LandingPage.
 */
export default function App() {
  const { user } = useAuth();
  
  /** @type {['chat'|'review'|'documents'|'settings', function(string): void]} */
  const [activeView, setActiveView] = useState('chat');
  
  /** @type {[boolean, function(boolean): void]} */
  const [showUpload, setShowUpload] = useState(false);

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
    documents, 
    handleDeleteDocument, 
    handleUploaded, 
    clearDocuments 
  } = useDocuments(user);

  // Synchronize component states on user session swaps
  useEffect(() => {
    if (!user) {
      clearMessages();
      clearDocuments();
      setShowUpload(false);
      return;
    }
    clearMessages();
    setShowUpload(false);
  }, [user, clearMessages, clearDocuments]);

  if (!user) {
    return (
      <Suspense fallback={<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', width: '100vw', background: 'var(--main-bg)', fontSize: '16px', color: 'var(--text-secondary)' }}>Loading Page...</div>}>
        <LandingPage />
      </Suspense>
    );
  }

  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

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

            {activeView === 'review' && (
              <SafetyReviewDashboard />
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
