import { useState } from 'react';
import SourceBadges from './SourceBadges';
import './ChatMessage.css';

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
}

export default function ChatMessage({ message }) {
  const [expandedSource, setExpandedSource] = useState(null);
  const isUser = message.role === 'user';

  return (
    <div className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--bot'}`}>
      <div className="chat-message-avatar">
        {isUser ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M8 12l3 3 5-6" />
          </svg>
        )}
      </div>

      <div className="chat-message-body">
        <div className="chat-message-content">{message.content}</div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <>
            <div className="chat-message-meta-row">
              <SourceBadges
                sources={message.sources}
                onSourceClick={(src) =>
                  setExpandedSource(expandedSource === src ? null : src)
                }
              />
              <span className="chat-message-time">{formatTime(message.timestamp)}</span>
            </div>

            {expandedSource && (
              <div className="chat-message-source-detail">
                <strong>{expandedSource.source_filename}</strong> — page {expandedSource.page_number} | score {expandedSource.score.toFixed(4)}
                <p>{expandedSource.chunk_text}</p>
              </div>
            )}

            <div className="chat-message-footer">
              <span className="chat-message-footer-label">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--success)" stroke="none">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M8 12l3 3 5-6" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Answer generated from {message.sources.length} source{message.sources.length > 1 ? 's' : ''}
              </span>
              {message.retrievalTime && (
                <span className="chat-message-footer-time">Retrieved in {message.retrievalTime}s</span>
              )}
            </div>
          </>
        )}

        {isUser && (
          <span className="chat-message-time">{formatTime(message.timestamp)}</span>
        )}
      </div>
    </div>
  );
}
