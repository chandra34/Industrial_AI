import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import DocumentsPanel from './components/DocumentsPanel';
import UploadModal from './components/UploadModal';
import { queryDocuments, getDocuments, deleteDocument } from './api/client';
import { useAuth } from './context/AuthContext';
import Login from './components/Login';

export default function App() {
  const { user } = useAuth();
  const [activeView, setActiveView] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [topK, setTopK] = useState(5);

  useEffect(() => {
    if (!user) {
      setMessages([]);
      setDocuments([]);
      setIsLoading(false);
      setShowUpload(false);
      return;
    }

    // Reset session states on user login / switch
    setMessages([]);
    setIsLoading(false);
    setShowUpload(false);

    async function loadDocuments() {
      try {
        const response = await getDocuments();
        setDocuments(response.documents || []);
      } catch (err) {
        console.error('Failed to load documents:', err);
      }
    }
    loadDocuments();
  }, [user]);

  if (!user) {
    return <Login />;
  }

  async function handleSend(question) {
    const userMessage = {
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    const startTime = Date.now();
    try {
      const response = await queryDocuments(question, topK);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      const botMessage = {
        role: 'assistant',
        content: response.answer,
        sources: response.source_chunks,
        retrievalTime: elapsed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const botMessage = {
        role: 'assistant',
        content: `Error: ${err.message}`,
        sources: [],
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleUploaded(result) {
    setDocuments((prev) => [...prev, result]);
  }

  async function handleDeleteDocument(documentId) {
    if (!window.confirm("Are you sure you want to delete this document? This will remove its indexed vectors and raw file.")) {
      return;
    }
    try {
      await deleteDocument(documentId);
      setDocuments((prev) => prev.filter((doc) => doc.document_id !== documentId));
    } catch (err) {
      alert(`Failed to delete document: ${err.message}`);
    }
  }

  return (
    <div className="app-layout">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

      <div className="app-main">
        <Header />

        <div className="app-content">
          {activeView === 'chat' && (
            <ChatArea
              messages={messages}
              isLoading={isLoading}
              onSend={handleSend}
              onUploadClick={() => setShowUpload(true)}
            />
          )}

          {activeView === 'documents' && (
            <DocumentsPanel
              documents={documents}
              onUploadClick={() => setShowUpload(true)}
              onDelete={handleDeleteDocument}
            />
          )}

          {activeView === 'settings' && (
            <div style={{ padding: '32px 24px', maxWidth: 'var(--content-max-width)', margin: '0 auto', width: '100%' }}>
              <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: 20 }}>Settings</h2>
              
              <div style={{ 
                background: '#ffffff', 
                padding: '24px', 
                borderRadius: 'var(--radius-md)', 
                boxShadow: 'var(--bot-bubble-shadow)',
                border: '1px solid var(--border-light)'
              }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>Retrieval Settings</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 20 }}>
                  Adjust the retrieval parameters used during query execution.
                </p>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                      Top-K Retrieval Depth:
                    </label>
                    <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--accent)', background: '#eae6ff', padding: '2px 8px', borderRadius: '4px' }}>
                      {topK} chunks
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                    style={{ 
                      width: '100%', 
                      accentColor: 'var(--accent)',
                      cursor: 'pointer',
                      height: '6px',
                      borderRadius: '3px',
                      background: '#e5e7eb',
                      outline: 'none',
                      marginTop: '8px',
                      marginBottom: '8px'
                    }}
                  />
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', lineHeight: '1.5' }}>
                    Select how many highly relevant context chunks from your PDF documents are fetched and supplied to the language model. Higher values provide more context but use more tokens.
                  </p>
                </div>
              </div>
            </div>
          )}
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

