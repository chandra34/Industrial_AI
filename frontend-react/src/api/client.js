import { auth } from './firebase';

const API_BASE = '/api/v1';

async function request(method, path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = { method, ...options };

  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      config.headers = {
        ...config.headers,
        'Authorization': `Bearer ${token}`
      };
    } catch (e) {
      console.error('Failed to get Firebase Auth ID token:', e);
    }
  }

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

export async function checkHealth() {
  return request('GET', '/health');
}

export async function uploadPDF(file) {
  const formData = new FormData();
  formData.append('file', file);

  return request('POST', '/upload', { body: formData });
}

export async function queryDocuments(question, topK = 5) {
  return request('POST', '/query', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK }),
  });
}

export async function getDocuments() {
  return request('GET', '/documents');
}

export async function deleteDocument(documentId) {
  return request('DELETE', `/documents/${documentId}`);
}

export async function downloadDocument(documentId, filename) {
  const url = `${API_BASE}/documents/${documentId}/download`;
  const config = { method: 'GET' };

  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      config.headers = {
        'Authorization': `Bearer ${token}`
      };
    } catch (e) {
      console.error('Failed to get Firebase Auth ID token:', e);
    }
  }

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


