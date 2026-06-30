import { useState, useRef, useEffect } from 'react';
import './UploadModal.css';
import { uploadPDF } from '../api/client';

// SVG Icons
const FileUploadIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6C63FF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="header-upload-icon">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="12" y1="18" x2="12" y2="12" />
    <polyline points="9 15 12 12 15 15" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '4px' }}>
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

const CheckIcon = ({ size = 14, color = "#22c55e", strokeWidth = 2.5 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const CheckCircleFilledIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" fill="#f0fdf4" />
    <polyline points="9 11 11 13 15 9" />
  </svg>
);

const LayersIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </svg>
);

const PageIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

const UploadIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const ChatIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const PDFFileIcon = () => (
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
  </svg>
);

/**
 * UploadModal component managing PDF uploads and vector DB indexing pipelines.
 * Renders file drag-and-drop state, uploads selected files, and displays processing metadata.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {boolean} props.isOpen - Modal visibility flag.
 * @param {function(): void} props.onClose - Modal close event handler.
 * @param {function(Object): void} props.onUploaded - Success callback to register indexed file metadata with App layout.
 * @returns {React.JSX.Element|null} The modal overlay markup or null.
 */
export default function UploadModal({ isOpen, onClose, onUploaded }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [elapsedTime, setElapsedTime] = useState('0.0');
  
  const fileInputRef = useRef(null);

  // Reset modal state when opened/closed
  useEffect(() => {
    if (!isOpen) {
      handleReset();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  /**
   * Dispatches PDF file upload and triggers parsing, chunking, and Milvus insertion.
   * Logs execution timing metrics.
   *
   * @async
   */
  async function handleUpload() {
    if (!file) return;
    setError('');
    setUploading(true);
    const startTime = Date.now();

    try {
      const result = await uploadPDF(file);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      
      setElapsedTime(elapsed);
      setUploadResult(result);
      setIsSuccess(true);
      
      // Update parent list
      onUploaded(result);
    } catch (err) {
      setError(err.message || 'Upload failed');
      setUploading(false);
    }
  }

  /**
   * Resets local file upload inputs and status indicators.
   */
  function handleReset() {
    setFile(null);
    setUploading(false);
    setError('');
    setIsSuccess(false);
    setUploadResult(null);
    setElapsedTime('0.0');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }


  return (
    <div className="upload-overlay" onClick={onClose}>
      <div className={`upload-modal ${isSuccess ? 'success' : ''}`} onClick={(e) => e.stopPropagation()}>
        
        {/* Header */}
        <div className="upload-modal-header">
          <div className="upload-modal-title">
            <FileUploadIcon />
            <h3>Upload PDF</h3>
          </div>
          {isSuccess ? (
            <div className="header-status-area">
              <div className="indexed-badge">
                <CheckIcon size={12} color="#16a34a" strokeWidth={3} />
                <span>Indexed successfully</span>
              </div>
              <button className="upload-dropdown-btn" onClick={onClose}>
                <ChevronDownIcon />
              </button>
            </div>
          ) : (
            <button className="upload-close-btn" onClick={onClose}>✕</button>
          )}
        </div>

        {/* Body */}
        {isSuccess && uploadResult ? (
          <div className="upload-modal-body success-state">
            <div className="success-layout">
              {/* Left Column: PDF Card */}
              <div className="pdf-card">
                <div className="pdf-card-icon-wrapper">
                  <PDFFileIcon />
                  <span className="pdf-label-badge">PDF</span>
                </div>
                <span className="pdf-card-filename" title={uploadResult.filename}>
                  {uploadResult.filename}
                </span>
              </div>

              {/* Right Column: Processing details */}
              <div className="processing-info">
                <h4 className="info-title" title={uploadResult.filename}>
                  {uploadResult.filename}
                </h4>
                
                <div className="metadata-row">
                  <div className="meta-item">
                    <LayersIcon />
                    <span>{uploadResult.chunk_count} chunks</span>
                  </div>
                  <span className="divider">|</span>
                  <div className="meta-item text-green">
                    <CheckIcon size={12} color="#16a34a" strokeWidth={2.5} />
                    <span>Indexed in {elapsedTime}s</span>
                  </div>
                  <span className="divider">|</span>
                  <div className="meta-item">
                    <PageIcon />
                    <span>{uploadResult.page_count} pages</span>
                  </div>
                </div>

                <div className="progress-bar-container">
                  <div className="progress-bar-track">
                    <div className="progress-bar-fill" style={{ width: '100%' }}></div>
                  </div>
                  <span className="progress-percentage">100%</span>
                </div>
              </div>
            </div>

            {/* Ready Status Banner */}
            <div className="status-banner">
              <CheckCircleFilledIcon />
              <div className="status-banner-content">
                <h5>Your document is ready!</h5>
                <p>You can now ask questions about your document.</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="upload-modal-body">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={(e) => { setFile(e.target.files[0]); setError(''); }}
              className="upload-file-input"
            />

            {file && (
              <p className="upload-file-name">
                <strong>Selected:</strong> {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}

            {error && <p className="upload-error">{error}</p>}
          </div>
        )}

        {/* Footer */}
        {isSuccess ? (
          <div className="upload-modal-footer success-state">
            <button className="upload-another-btn" onClick={handleReset}>
              <UploadIcon />
              <span>Upload Another</span>
            </button>
            <button className="go-to-chat-btn" onClick={onClose}>
              <ChatIcon />
              <span>Go to Chat</span>
            </button>
          </div>
        ) : (
          <div className="upload-modal-footer">
            <button className="upload-cancel-btn" onClick={onClose} disabled={uploading}>Cancel</button>
            <button
              className="upload-submit-btn"
              onClick={handleUpload}
              disabled={!file || uploading}
            >
              {uploading ? 'Uploading...' : 'Upload & Index'}
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
