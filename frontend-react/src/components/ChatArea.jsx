import { useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import './ChatArea.css';

/**
 * ChatArea component representing the conversation canvas.
 * Renders user and system messages, a loading animation when retrieving context,
 * and maintains scroll position focus on the latest entries.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {Array<Object>} props.messages - List of chat message structures.
 * @param {boolean} props.isLoading - If true, displays the loading animation.
 * @param {function(string): void} props.onSend - Submit callback for new prompt requests.
 * @param {function(): void} props.onUploadClick - Open upload dialogue modal callback.
 * @returns {React.JSX.Element} The rendered conversation window.
 */
export default function ChatArea({ messages, isLoading, onSend, onUploadClick }) {
  const scrollRef = useRef(null);


  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  return (
    <div className="chat-area">
      <div className="chat-area-scroll" ref={scrollRef}>
        {/* Welcome Message */}
        <div className="chat-welcome">
          <div className="chat-system-badge">
            <span className="chat-badge-icon">📖</span>
            <span>Technical Knowledge Base RAG</span>
          </div>

          <h1 className="chat-welcome-title">Document &amp; SOP Intelligence</h1>
          <p className="chat-welcome-desc">
            Search indexed OEM manuals, SOPs, contracts, and engineering specs with page-precise citations.
          </p>

          <div className="chat-cards-grid">
            <div className="chat-capability-card">
              <div className="chat-card-icon">📘</div>
              <h3 className="chat-card-title">OEM Equipment Manuals</h3>
              <p className="chat-card-desc">Search operating limits, maintenance schedules, and assembly diagrams.</p>
            </div>

            <div className="chat-capability-card">
              <div className="chat-card-icon">📋</div>
              <h3 className="chat-card-title">Standard Operating Procedures</h3>
              <p className="chat-card-desc">Retrieve step-by-step safety steps, lockout/tagout rules, and checklists.</p>
            </div>

            <div className="chat-capability-card">
              <div className="chat-card-icon">📐</div>
              <h3 className="chat-card-title">Engineering Specifications</h3>
              <p className="chat-card-desc">Look up torque limits, pressure thresholds, and electrical ratings.</p>
            </div>

            <div className="chat-capability-card">
              <div className="chat-card-icon">📄</div>
              <h3 className="chat-card-title">Contracts &amp; Safety Audits</h3>
              <p className="chat-card-desc">Search vendor SLA terms, inspection reports, and Permit-to-Work records.</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {messages.map((msg, index) => (
            <ChatMessage key={msg.id || `${msg.role}-${new Date(msg.timestamp).getTime()}-${index}`} message={msg} />
          ))}

          {isLoading && (
            <div className="chat-loading">
              <div className="chat-loading-dots">
                <span></span><span></span><span></span>
              </div>
              <p>Retrieving context and generating answer...</p>
            </div>
          )}
        </div>
      </div>

      <ChatInput onSend={onSend} onUploadClick={onUploadClick} disabled={isLoading} />
    </div>
  );
}
