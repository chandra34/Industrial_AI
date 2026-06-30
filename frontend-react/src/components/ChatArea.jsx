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
          <h1 className="chat-welcome-title">Hello! 👋</h1>
          <h2 className="chat-welcome-subtitle">Ask anything about your documents</h2>
          <p className="chat-welcome-desc">
            I'll search your knowledge base and provide accurate, cited answers.
          </p>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {messages.map((msg, index) => (
            <ChatMessage key={index} message={msg} />
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
