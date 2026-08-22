/**
 * API client functions for the Plant Health Dashboard.
 * Interacts with telemetry anomaly analytics and Root Cause Analysis (RCA) backend endpoints.
 */

import { auth } from './firebase';

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
 * Private helper to perform authenticated requests against backend REST routes.
 *
 * @private
 * @async
 * @param {'GET'|'POST'|'PATCH'|'DELETE'} method - HTTP method.
 * @param {string} path - API endpoint path.
 * @param {RequestInit} [options={}] - Additional fetch configurations.
 * @returns {Promise<any>}
 */
async function request(method, path, options = {}) {
  const url = `${API_BASE}${path}`;
  const authHeaders = await getAuthHeaders();
  const config = {
    method,
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `Request failed (${response.status})`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      /* ignore parse error */
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

/**
 * Runs statistical anomaly detection (Z-Score, MAD, EWMA drift, ISO vibration) on a sensor node.
 *
 * @async
 * @param {string} nodeId - OPC UA Node ID (e.g. 'ns=2;s=Line1.Pump02.Vibration').
 * @param {number} [lookbackHours=24] - Historical lookback duration in hours.
 * @param {string} [sensorType='general'] - Sensor type hint ('general', 'vibration', 'temperature', 'pressure', etc.).
 * @returns {Promise<Object>} Formatted anomaly detection payload with method scores and overall_severity.
 */
export async function getNodeAnomalies(nodeId, lookbackHours = 24, sensorType = 'general') {
  const encodedId = encodeURIComponent(nodeId);
  return request('GET', `/opcua/telemetry/anomalies/${encodedId}?lookback_hours=${lookbackHours}&sensor_type=${sensorType}`);
}

/**
 * Fetches recent Root Cause Analysis reports for Dashboard Zone 3.
 *
 * @async
 * @param {Object} [params={}] - Filter parameters.
 * @param {number} [params.limit=20] - Maximum records to retrieve.
 * @param {string|null} [params.status=null] - Filter by status ('open', 'acknowledged', 'resolved').
 * @param {string|null} [params.assetName=null] - Search by asset name substring.
 * @returns {Promise<Array>} List of RCA event summaries.
 */
export async function getRCAEvents({ limit = 20, status = null, assetName = null } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set('status', status);
  if (assetName) params.set('asset_name', assetName);
  return request('GET', `/rca/events?${params.toString()}`);
}

/**
 * Fetches full diagnostic detail for an RCA Event (for slide-out drawer).
 *
 * @async
 * @param {string} eventId - Unique RCA event ID (e.g. 'rca_...').
 * @returns {Promise<Object>} Full diagnostic report including 3-pillar evidence and corrective steps.
 */
export async function getRCAEventDetail(eventId) {
  return request('GET', `/rca/events/${encodeURIComponent(eventId)}`);
}

/**
 * Triggers an on-demand Root Cause Analysis mission for a machine.
 *
 * @async
 * @param {Object} payload - Trigger arguments.
 * @param {string} payload.node_id - OPC UA Node ID.
 * @param {string} payload.asset_name - Machine display name.
 * @param {string} [payload.alarm_type='Manual Diagnostic Request'] - Description of event/outlier.
 * @param {string} [payload.severity='WARNING'] - 'WARNING' or 'CRITICAL'.
 * @param {string} [payload.extra_context=''] - Optional sensor reading context.
 * @returns {Promise<Object>} Completed RCA diagnostic record.
 */
export async function triggerManualRCA(payload) {
  return request('POST', '/rca/trigger', {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * Updates status of an RCA event (acknowledge alert or mark resolved).
 *
 * @async
 * @param {string} eventId - Unique RCA event ID.
 * @param {'open'|'acknowledged'|'resolved'} status - New status string.
 * @returns {Promise<Object>} Update confirmation.
 */
export async function updateRCAStatus(eventId, status) {
  return request('PATCH', `/rca/events/${encodeURIComponent(eventId)}/status?status=${status}`);
}
