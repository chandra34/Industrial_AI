import { useState } from 'react';
import { downloadDocument } from '../api/client';
import './DocumentsPanel.css';

export default function DocumentsPanel({ documents, onUploadClick, onDelete }) {
  const [downloadingIds, setDownloadingIds] = useState(new Set());

  async function handleDownload(doc) {
    if (downloadingIds.has(doc.document_id)) return;

    setDownloadingIds((prev) => {
      const next = new Set(prev);
      next.add(doc.document_id);
      return next;
    });

    try {
      await downloadDocument(doc.document_id, doc.filename);
    } catch (err) {
      alert(`Download failed: ${err.message}`);
    } finally {
      setDownloadingIds((prev) => {
        const next = new Set(prev);
        next.delete(doc.document_id);
        return next;
      });
    }
  }

  return (
    <div className="documents-panel">
      <div className="documents-header">
        <h2 className="documents-title">Indexed Documents</h2>
        <button className="documents-upload-btn" onClick={onUploadClick}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Upload PDF
        </button>
      </div>

      {documents.length === 0 ? (
        <div className="documents-empty">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="documents-empty-icon">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <p>No documents indexed yet.</p>
          <p className="documents-empty-hint">Upload a PDF to get started.</p>
        </div>
      ) : (
        <div className="documents-list">
          {documents.map((doc, index) => (
            <div key={index} className="document-card">
              <div className="document-card-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <div className="document-card-info">
                <span className="document-card-name">{doc.filename}</span>
                <span className="document-card-meta">
                  {doc.page_count} pages · {doc.chunk_count} chunks
                </span>
              </div>
              <div className="document-card-actions">
                <button
                  onClick={() => handleDownload(doc)}
                  className="document-action-btn"
                  title="Download original PDF"
                  disabled={downloadingIds.has(doc.document_id)}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                </button>
                <button
                  onClick={() => onDelete?.(doc.document_id)}
                  className="document-action-btn document-action-btn--delete"
                  title="Delete document"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

