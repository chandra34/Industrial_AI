import { useState, useCallback } from 'react';
import { queryDocuments } from '../api/client';

/**
 * Custom React hook to manage conversational state and RAG backend search queries.
 *
 * @returns {Object} Chat state parameters, actions, and loader statuses.
 */
export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [topK, setTopK] = useState(5);

  /**
   * Dispatches queries to the RAG backend, records search latencies, and appends responses.
   *
   * @async
   * @param {string} question - The user's input prompt.
   */
  const handleSend = useCallback(async (question) => {
    if (!question.trim()) return;

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
  }, [topK]);

  /**
   * Resets active conversation history state and pending indicators.
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsLoading(false);
  }, []);

  return {
    messages,
    isLoading,
    topK,
    setTopK,
    handleSend,
    clearMessages,
  };
}
