import { auth } from './firebase';

/**
 * Base URL path prefix for all backend REST API routes.
 * @type {string}
 */
const API_BASE = '/api/v1';

/**
 * Resolves Firebase ID token and returns an Authorization header object if logged in.
 *
 * @private
 * @async
 * @returns {Promise<Record<string, string>>} Headers object.
 */
async function getAuthHeaders() {
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      return { 'Authorization': `Bearer ${token}` };
    } catch (e) {
      console.error('Failed to get Firebase Auth ID token:', e);
    }
  }
  return {};
}

/**
 * Private helper function to perform authenticated HTTP requests to the backend server.
 * Appends Firebase Auth ID tokens automatically to the 'Authorization' headers if a user is logged in.
 *
 * @private
 * @async
 * @param {'GET'|'POST'|'PUT'|'DELETE'} method - The HTTP method to execute.
 * @param {string} path - Endpoint path (e.g. '/health' or '/upload').
 * @param {RequestInit} [options={}] - Additional fetch configurations (headers, body, etc.).
 * @returns {Promise<any>} The parsed JSON response body.
 * @throws {Error} If the network request fails or returns a non-2xx status code.
 */
async function request(method, path, options = {}) {
  const url = `${API_BASE}${path}`;
  const authHeaders = await getAuthHeaders();
  const config = {
    method,
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers
    }
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `Request failed (${response.status})`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Verifies backend API server availability and state.
 *
 * @async
 * @returns {Promise<{status: string, message?: string}>} Health check status object.
 */
export async function checkHealth() {
  return request('GET', '/health');
}

/**
 * Uploads a local PDF file to the backend to chunk, embed, and index into Milvus DB.
 *
 * @async
 * @param {File} file - The file object to upload.
 * @param {Object} [metadata={}] - Optional metadata object (document_type, manufacturer, equipment).
 * @returns {Promise<{document_id: string, filename: string, page_count: number, chunk_count: number}>} Metadata of the successfully indexed document.
 */
export async function uploadPDF(file, metadata = {}) {
  const formData = new FormData();
  formData.append('file', file);

  if (metadata.document_type) formData.append('document_type', metadata.document_type);
  if (metadata.manufacturer) formData.append('manufacturer', metadata.manufacturer);
  if (metadata.equipment) formData.append('equipment', metadata.equipment);

  return request('POST', '/upload', { body: formData });
}

/**
 * Submits a query/question to the RAG system to retrieve top context and synthesize an answer.
 *
 * @async
 * @param {string} question - The search prompt or question to ask.
 * @param {number} [topK=5] - Number of high-similarity document text chunks to retrieve.
 * @returns {Promise<{answer: string, source_chunks: Array<{chunk_id: string, source_filename: string, page_number: number, chunk_text: string, score: number}>}>} The generated answer and matched chunk citations.
 */
export async function queryDocuments(question, topK = 5) {
  return request('POST', '/query', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK }),
  });
}

/**
 * Fetches the metadata list of all indexed documents in the user's RAG workspace.
 *
 * @async
 * @returns {Promise<{documents: Array<{document_id: string, filename: string, page_count: number, chunk_count: number, created_at: string}>}>} The list of indexed document definitions.
 */
export async function getDocuments() {
  return request('GET', '/documents');
}

/**
 * Deletes a previously indexed document from backend storage and drops its Milvus vector collections.
 *
 * @async
 * @param {string} documentId - The unique ID of the document to delete.
 * @returns {Promise<{message: string, document_id: string}>} Response confirmation of successful deletion.
 */
export async function deleteDocument(documentId) {
  return request('DELETE', `/documents/${documentId}`);
}

/**
 * Downloads the original uploaded PDF document from backend storage and triggers browser file save.
 *
 * @async
 * @param {string} documentId - Unique ID of the document to download.
 * @param {string} filename - Expected save filename.
 * @returns {Promise<void>} Resolves when download is initiated.
 * @throws {Error} If the download endpoint is unreachable or unauthorized.
 */
export async function downloadDocument(documentId, filename) {
  const url = `${API_BASE}/documents/${documentId}/download`;
  const authHeaders = await getAuthHeaders();
  const config = {
    method: 'GET',
    headers: authHeaders
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `Download failed (${response.status})`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(errorMessage);
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename || 'document.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

/**
 * Fetches the status and results of a background ingestion job.
 *
 * @async
 * @param {string} jobId - The unique ID of the background job.
 * @returns {Promise<{job_id: string, status: 'pending'|'processing'|'completed'|'failed', result?: any, error?: string}>} The job status object.
 */
export async function getJobStatus(jobId) {
  return request('GET', `/jobs/${jobId}`);
}

/**
 * Submits a Permit-to-Work (PTW) for safety review against indexed SOPs and manuals.
 *
 * @async
 * @param {string} permitText - The raw permit text or task steps to be reviewed.
 * @param {string|null} [equipment=null] - Optional equipment name filter.
 * @param {string|null} [manufacturer=null] - Optional manufacturer name filter.
 * @returns {Promise<{status: string, summary: string, findings: Array<{severity: string, finding_type: string, description: string, recommendation: string, reference_source: string|null}>}>} The structured safety review report.
 */
export async function reviewPermit(permitText, equipment = null, manufacturer = null) {
  return request('POST', '/review', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      permit_text: permitText,
      equipment: equipment || null,
      manufacturer: manufacturer || null,
    }),
  });
}

/**
 * Submits a natural language query to the multi-agent orchestrator.
 *
 * @async
 * @param {string} query - The user's question.
 * @param {string} [userRole='operator'] - User authorization role.
 * @param {string|null} [plantId=null] - Optional default plant ID context.
 * @param {number} [maxSteps=5] - Max tool execution iterations (1–10).
 * @returns {Promise<{query: string, answer: string, steps_taken: number, tool_calls: Array, llm_provider_used: string, llm_model_used: string}>} The agent response payload.
 */
export async function queryAgent(query, userRole = 'operator', plantId = null, maxSteps = 10) {
  return request('POST', '/agent/query', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      user_role: userRole,
      plant_id: plantId,
      max_steps: maxSteps,
    }),
  });
}

/**
 * Triggers an on-demand OPC UA address space crawl in the backend.
 * The crawl runs as a background task and the API responds immediately.
 *
 * @async
 * @returns {Promise<{status: string, message: string}>} Confirmation that sync has started.
 */
export async function reindexOpcuaCatalog() {
  return request('POST', '/opcua/reindex');
}

/**
 * Fetches the current OPC UA tag catalog status (total indexed tags and last sync time).
 *
 * @async
 * @returns {Promise<{total_tags: number, last_updated: string|null}>} Catalog status object.
 */
export async function getOpcuaCatalogStatus() {
  return request('GET', '/opcua/status');
}

/**
 * Fetches all saved OPC UA connection profiles.
 *
 * @async
 * @returns {Promise<Array>} List of connection profiles.
 */
export async function getOpcuaProfiles() {
  return request('GET', '/opcua/profiles');
}

/**
 * Saves a new OPC UA connection profile to the database.
 *
 * @async
 * @param {Object} profileData - Profile details to save.
 * @returns {Promise<Object>} Created profile details.
 */
export async function createOpcuaProfile(profileData) {
  return request('POST', '/opcua/profiles', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profileData),
  });
}

/**
 * Deletes a previously saved connection profile.
 *
 * @async
 * @param {string} profileId - Unique ID of the profile.
 * @returns {Promise<Object>} Status response.
 */
export async function deleteOpcuaProfile(profileId) {
  return request('DELETE', `/opcua/profiles/${profileId}`);
}

/**
 * Tests connection credentials and endpoint without saving.
 *
 * @async
 * @param {Object} connectionData - Server credentials to test.
 * @returns {Promise<Object>} Connection test result.
 */
export async function testOpcuaConnection(connectionData) {
  return request('POST', '/opcua/test', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(connectionData),
  });
}

/**
 * Connects to a saved connection profile, making it active and triggering tag index.
 *
 * @async
 * @param {Object} connectionData - Contains profile_id of saved server profile.
 * @returns {Promise<Object>} Connection result and status.
 */
export async function connectOpcuaServer(connectionData) {
  return request('POST', '/opcua/connect', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(connectionData),
  });
}



