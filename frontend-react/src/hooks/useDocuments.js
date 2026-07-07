import { useState, useEffect, useCallback } from 'react';
import { getDocuments, deleteDocument } from '../api/client';

/**
 * Custom React hook to manage document indexing operations, list states, and deletion queries.
 *
 * @param {Object|null} user - The active authenticated user state config.
 * @returns {Object} Documents catalog state, actions, and re-fetch trigger routines.
 */
export function useDocuments(user) {
  const [documents, setDocuments] = useState([]);

  /**
   * Refetches metadata records of indexed documents from SQLite.
   *
   * @async
   */
  const loadDocuments = useCallback(async () => {
    if (!user) {
      setDocuments([]);
      return;
    }
    try {
      const response = await getDocuments();
      setDocuments(response.documents || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    }
  }, [user]);

  // Load documents automatically when the authenticated session switches
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  /**
   * Triggers deletion of document metadata, file storage, and Milvus collections.
   *
   * @async
   * @param {string} documentId - Database unique identifier of target file.
   */
  const handleDeleteDocument = useCallback(async (documentId) => {
    if (!window.confirm("Are you sure you want to delete this document? This will remove its indexed vectors and raw file.")) {
      return;
    }
    try {
      await deleteDocument(documentId);
      setDocuments((prev) => prev.filter((doc) => doc.document_id !== documentId));
    } catch (err) {
      alert(`Failed to delete document: ${err.message}`);
    }
  }, []);

  /**
   * Callback to append newly indexed files directly to local state list.
   *
   * @param {Object} result - Success payload metadata.
   */
  const handleUploaded = useCallback((result) => {
    setDocuments((prev) => [...prev, result]);
  }, []);

  /**
   * Resets internal document catalog state variables.
   */
  const clearDocuments = useCallback(() => {
    setDocuments([]);
  }, []);

  return {
    documents,
    setDocuments,
    loadDocuments,
    handleDeleteDocument,
    handleUploaded,
    clearDocuments,
  };
}
