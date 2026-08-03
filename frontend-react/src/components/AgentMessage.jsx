import { useState } from 'react';
import './AgentMessage.css';

/**
 * Maps tool names to visual data source labels, icons, and CSS modifier classes.
 *
 * @param {string} toolName - Executed tool function name.
 * @returns {{label: string, icon: string, className: string}} Source display metadata.
 */
function getToolSource(toolName) {
  if (!toolName) return { label: 'SAP ERP', icon: '⚙️', className: 'source-sap' };
  const lowerName = toolName.toLowerCase();
  if (lowerName.includes('opcua') || lowerName.includes('telemetry') || lowerName.includes('alarm')) {
    return { label: 'OPC UA', icon: '⚡', className: 'source-opcua' };
  }
  if (lowerName === 'search_technical_manuals') {
    return { label: 'Vector RAG', icon: '📖', className: 'source-rag' };
  }
  return { label: 'SAP ERP', icon: '⚙️', className: 'source-sap' };
}


/**
 * Formats a Date object or date-string to localized 12-hour AM/PM format.
 *
 * @param {Date|string} dateVal - Date to format.
 * @returns {string} Formatted string.
 */
function formatTime(dateVal) {
  if (!dateVal) return '';
  const parsedDate = dateVal instanceof Date ? dateVal : new Date(dateVal);
  if (isNaN(parsedDate.getTime())) return '';
  return parsedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
}

/**
 * AgentMessage component rendering individual user and assistant agent messages.
 * Includes a collapsible tool execution accordion showing step-by-step tool invocation records.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {Object} props.message - Agent message object.
 * @returns {React.JSX.Element} Rendered message bubble.
 */
export default function AgentMessage({ message }) {
  const [expandedResult, setExpandedResult] = useState(null);
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="agent-msg agent-msg--user">
        <div className="agent-msg-avatar agent-msg-avatar--user">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <div className="agent-msg-body">
          <div className="agent-msg-content">{message.content}</div>
          <span className="agent-msg-time">{formatTime(message.timestamp)}</span>
        </div>
      </div>
    );
  }

  const toolCalls = message.toolCalls || [];

  return (
    <div className="agent-msg agent-msg--bot">
      <div className="agent-msg-avatar agent-msg-avatar--bot">
        🤖
      </div>

      <div className="agent-msg-body">
        {/* Tool Execution Accordion */}
        {toolCalls.length > 0 && (
          <details className="agent-tool-accordion">
            <summary className="agent-tool-summary">
              🛠️ Executed {toolCalls.length} tool{toolCalls.length > 1 ? 's' : ''} in {message.stepsTaken} step{message.stepsTaken > 1 ? 's' : ''} ({message.totalTime}s)
            </summary>
            <div className="agent-tool-list">
              {toolCalls.map((tc, idx) => {
                const source = getToolSource(tc.tool_name);
                return (
                  <div className={`agent-tool-card ${source.className}`} key={idx}>
                    <div className="agent-tool-header">
                      <span className={`agent-tool-badge ${source.className}`}>
                        {source.icon} {source.label}
                      </span>
                      <span className="agent-tool-time">{tc.execution_time_seconds}s</span>
                    </div>
                    <code className="agent-tool-call">
                      {tc.tool_name}({JSON.stringify(tc.tool_args)})
                    </code>
                    <button
                      type="button"
                      className="agent-tool-result-toggle"
                      onClick={() => setExpandedResult(expandedResult === idx ? null : idx)}
                    >
                      {expandedResult === idx ? '▾ Hide Result' : '▸ Show Result'}
                    </button>
                    {expandedResult === idx && (
                      <pre className="agent-tool-result">
                        {JSON.stringify(tc.result, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          </details>
        )}

        {/* Final Synthesized Answer */}
        <div className="agent-msg-content">{message.content}</div>

        {/* Footer Metadata */}
        <div className="agent-msg-footer">
          <span className="agent-msg-footer-label">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--success)" stroke="none">
              <circle cx="12" cy="12" r="10" />
              <path d="M8 12l3 3 5-6" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {message.llmProvider && `${message.llmModel} · `}{message.stepsTaken || 1} step{message.stepsTaken !== 1 ? 's' : ''}
          </span>
          {message.totalTime && (
            <span className="agent-msg-footer-time">Completed in {message.totalTime}s</span>
          )}
        </div>
      </div>
    </div>
  );
}
