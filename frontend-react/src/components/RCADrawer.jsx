import { useState, useEffect } from 'react';
import { getRCAEventDetail, updateRCAStatus } from '../api/dashboardApi';
import './RCADrawer.css';

/**
 * Slide-out Diagnostic Deep-Dive Drawer for Root Cause Analysis reports.
 *
 * @component
 * @param {Object} props
 * @param {string} props.eventId - RCA Event ID to view.
 * @param {Object|null} [props.preloadedData] - Pre-fetched RCA data (e.g. from immediate 1-click trigger).
 * @param {function(): void} props.onClose - Drawer close callback.
 * @param {function(): void} [props.onStatusUpdate] - Callback triggered when status is updated.
 * @returns {React.JSX.Element}
 */
export default function RCADrawer({ eventId, preloadedData, onClose, onStatusUpdate }) {
  const [data, setData] = useState(preloadedData || null);
  const [isLoading, setIsLoading] = useState(!preloadedData);
  const [error, setError] = useState(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [checkedActions, setCheckedActions] = useState({});

  useEffect(() => {
    if (preloadedData) {
      setData(preloadedData);
      setIsLoading(false);
      return;
    }
    if (!eventId) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    getRCAEventDetail(eventId)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => {
        if (isMounted) setError(err.message || 'Failed to fetch diagnostic detail.');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [eventId, preloadedData]);

  async function handleStatusChange(newStatus) {
    if (!data?.id || isUpdating) return;
    setIsUpdating(true);
    try {
      await updateRCAStatus(data.id, newStatus);
      setData((prev) => ({ ...prev, status: newStatus }));
      if (onStatusUpdate) onStatusUpdate();
    } catch (err) {
      console.error('Status update failed:', err);
    } finally {
      setIsUpdating(false);
    }
  }

  function toggleActionCheck(idx) {
    setCheckedActions((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  }

  return (
    <div className="rca-drawer-portal">
      <div className="rca-drawer-backdrop" onClick={onClose} />

      <aside className="rca-drawer-container" aria-label="Root Cause Analysis Diagnostic Drawer">
        {/* Drawer Header */}
        <div className="rca-drawer-header">
          <div className="rca-drawer-title-group">
            <span className="rca-drawer-icon">⚡</span>
            <div>
              <h2 className="rca-drawer-title">Root Cause Analysis</h2>
              <span className="rca-drawer-subtitle">Autonomous 3-Pillar Industrial Diagnostic</span>
            </div>
          </div>
          <button className="rca-drawer-close-btn" onClick={onClose} title="Close Diagnostic Drawer">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Loading / Error States */}
        {isLoading && (
          <div className="rca-drawer-state">
            <div className="rca-spinner" />
            <p>Synthesizing OT telemetry, SAP PM logs, and OEM manual citations...</p>
          </div>
        )}

        {error && (
          <div className="rca-drawer-state rca-drawer-state--error">
            <span className="rca-error-icon">⚠️</span>
            <p>{error}</p>
          </div>
        )}

        {/* Content Body */}
        {data && !isLoading && (
          <div className="rca-drawer-content">
            {/* Asset & Trigger Banner */}
            <div className={`rca-hero-banner rca-hero-banner--${(data.severity || 'warning').toLowerCase()}`}>
              <div className="rca-hero-top">
                <span className="rca-hero-asset">{data.asset_name}</span>
                <span className={`rca-hero-pill rca-hero-pill--${(data.severity || 'warning').toLowerCase()}`}>
                  {data.severity}
                </span>
              </div>
              <div className="rca-hero-trigger">
                <strong>Trigger Event:</strong> {data.alarm_type}
              </div>
              <div className="rca-hero-node">
                <code>{data.node_id}</code>
              </div>
            </div>

            {/* AI Confidence Meter */}
            <div className="rca-card rca-confidence-card">
              <div className="rca-card-header">
                <span className="rca-card-title">🎯 AI Confidence Score</span>
                <span className="rca-confidence-val">{data.confidence_score}%</span>
              </div>
              <div className="rca-meter-track">
                <div
                  className="rca-meter-fill"
                  style={{
                    width: `${data.confidence_score}%`,
                    background: data.confidence_score >= 85 ? 'linear-gradient(90deg, #3b82f6, #10b981)' : '#f59e0b',
                  }}
                />
              </div>
            </div>

            {/* Primary Root Cause */}
            <div className="rca-card rca-cause-card">
              <div className="rca-card-header">
                <span className="rca-card-title">📋 Primary Root Cause</span>
              </div>
              <p className="rca-cause-text">{data.root_cause}</p>
            </div>

            {/* 3-Pillar Evidence Sections */}
            <div className="rca-evidence-grid">
              {/* Pillar 1: OT Telemetry */}
              <div className="rca-card rca-pillar-card">
                <div className="rca-card-header">
                  <span className="rca-pillar-tag rca-pillar--ot">PILLAR 1</span>
                  <span className="rca-card-title">📈 OT Telemetry Analytics</span>
                </div>
                <div className="rca-evidence-body">
                  <p>{data.telemetry_evidence || 'Statistical analysis executed across rolling baseline window.'}</p>
                </div>
              </div>

              {/* Pillar 2: SAP Maintenance History */}
              <div className="rca-card rca-pillar-card">
                <div className="rca-card-header">
                  <span className="rca-pillar-tag rca-pillar--sap">PILLAR 2</span>
                  <span className="rca-card-title">🏭 SAP PM Maintenance Evidence</span>
                </div>
                <div className="rca-evidence-body">
                  <p>{data.sap_evidence || 'No active work orders or overdue lubrication records identified.'}</p>
                </div>
              </div>

              {/* Pillar 3: OEM Manual RAG */}
              <div className="rca-card rca-pillar-card">
                <div className="rca-card-header">
                  <span className="rca-pillar-tag rca-pillar--oem">PILLAR 3</span>
                  <span className="rca-card-title">📖 OEM Manual & SOP Citation</span>
                </div>
                <div className="rca-evidence-body">
                  <p>{data.sop_evidence || 'Standard operating and troubleshooting procedures referenced.'}</p>
                </div>
              </div>
            </div>

            {/* Recommended Corrective Checklist */}
            {Array.isArray(data.recommended_actions) && data.recommended_actions.length > 0 && (
              <div className="rca-card rca-actions-card">
                <div className="rca-card-header">
                  <span className="rca-card-title">🛠️ Recommended Corrective Action Checklist</span>
                  <span className="rca-action-count">
                    {Object.values(checkedActions).filter(Boolean).length} / {data.recommended_actions.length} Done
                  </span>
                </div>
                <div className="rca-checklist">
                  {data.recommended_actions.map((action, idx) => (
                    <label
                      key={idx}
                      className={`rca-checkbox-item ${checkedActions[idx] ? 'rca-checkbox-item--done' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={Boolean(checkedActions[idx])}
                        onChange={() => toggleActionCheck(idx)}
                      />
                      <span className="rca-checkbox-text">
                        <strong>Step {idx + 1}:</strong> {action}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Footer Actions */}
            <div className="rca-drawer-footer">
              {data.status === 'open' && (
                <button
                  className="rca-btn rca-btn--ack"
                  onClick={() => handleStatusChange('acknowledged')}
                  disabled={isUpdating}
                >
                  ⚠️ Acknowledge Alert
                </button>
              )}

              {(data.status === 'open' || data.status === 'acknowledged') && (
                <button
                  className="rca-btn rca-btn--resolve"
                  onClick={() => handleStatusChange('resolved')}
                  disabled={isUpdating}
                >
                  ✓ Mark Issue Resolved
                </button>
              )}

              {data.status === 'resolved' && (
                <div className="rca-resolved-badge">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>Resolved & Closed in Plant Log</span>
                </div>
              )}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
