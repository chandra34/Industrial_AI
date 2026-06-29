import { useRef, useEffect } from 'react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import './ChatArea.css';

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
