import { useState } from 'react';
import { reviewPermit } from '../api/client';
import './SafetyReviewDashboard.css';

const SAMPLE_PERMIT = `Task: Startup of positive displacement pump for lime dosing system

Steps:
1. Check that pump motor is available and free to run.
2. Open suction valve from lime tank.
3. Start pump from local push button.
4. Check for abnormal noise or vibration.
5. Record pump operating parameters.`;

/**
 * Determines the CSS class suffix for a given audit status string.
 * @param {string} status
 * @returns {'safe'|'needs-review'|'unsafe'}
 */
function statusClass(status) {
  if (status === 'Safe') return 'safe';
  if (status === 'Needs Review') return 'needs-review';
  return 'unsafe';
}

/**
 * Returns a human-readable label for the audit status.
 * @param {string} status
 * @returns {string}
 */
function statusLabel(status) {
  if (status === 'Safe') return 'APPROVED — SAFE';
  if (status === 'Needs Review') return 'WARNING — NEEDS REVIEW';
  return 'REJECTED — UNSAFE';
}

/**
 * SafetyReviewDashboard component provides a two-column layout for submitting
 * Permit-to-Work text and viewing the structured safety audit report.
 *
 * @component
 * @returns {React.JSX.Element}
 */
export default function SafetyReviewDashboard() {
  const [permitText, setPermitText] = useState('');
  const [equipment, setEquipment] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  async function handleAudit() {
    if (!permitText.trim()) return;
    setIsLoading(true);
    setReport(null);
    setError(null);

    try {
      const result = await reviewPermit(
        permitText,
        equipment.trim() || null,
        manufacturer.trim() || null
      );
      setReport(result);
    } catch (err) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleLoadSample() {
    setPermitText(SAMPLE_PERMIT);
    setEquipment('positive displacement pump');
    setManufacturer('');
    setReport(null);
    setError(null);
  }

  return (
    <div className="review-dashboard">
      {/* ===== Left Column: Form ===== */}
      <div className="review-form-panel">
        <h2>Permit-to-Work Safety Audit</h2>
        <p className="form-desc">
          Paste the task steps from your work permit below. The system will compare them against indexed safety SOPs and manuals to identify gaps and hazards.
        </p>

        <div className="review-card">
          <textarea
            className="permit-textarea"
            placeholder="Paste the permit-to-work steps here..."
            value={permitText}
            onChange={(e) => setPermitText(e.target.value)}
          />

          <div className="filter-row">
            <div className="filter-group">
              <label>Equipment (optional)</label>
              <input
                className="filter-input"
                type="text"
                placeholder="e.g. centrifugal pump"
                value={equipment}
                onChange={(e) => setEquipment(e.target.value)}
              />
            </div>
            <div className="filter-group">
              <label>Manufacturer (optional)</label>
              <input
                className="filter-input"
                type="text"
                placeholder="e.g. grundfos"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
              />
            </div>
          </div>

          <div className="review-actions">
            <button className="btn-sample" onClick={handleLoadSample} type="button">
              Load Sample
            </button>
            <button
              className="btn-audit"
              onClick={handleAudit}
              disabled={isLoading || !permitText.trim()}
              type="button"
            >
              {isLoading ? (
                'Scanning...'
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  Run Safety Audit
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ===== Right Column: Results ===== */}
      <div className="review-results-panel">
        {/* Ready state */}
        {!isLoading && !report && !error && (
          <div className="review-ready">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <h3>Ready for Safety Scan</h3>
            <p>Paste your permit-to-work steps on the left and click "Run Safety Audit" to begin the verification process.</p>
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="review-scanning">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <div className="scan-bar" />
            <p>Analyzing permit steps against safety standards...</p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="review-ready">
            <h3 style={{ color: '#dc2626' }}>Audit Failed</h3>
            <p style={{ color: '#dc2626' }}>{error}</p>
          </div>
        )}

        {/* Report output */}
        {report && (
          <>
            {/* Status banner */}
            <div className={`status-banner ${statusClass(report.status)}`}>
              <span className={`status-badge ${statusClass(report.status)}`}>
                {statusLabel(report.status)}
              </span>
              <div className={`status-info ${statusClass(report.status)}`}>
                <h3>{report.status === 'Safe' ? 'Permit Approved' : report.status === 'Needs Review' ? 'Review Recommended' : 'Permit Rejected'}</h3>
                <p>{report.summary}</p>
              </div>
            </div>

            {/* Findings */}
            {report.findings && report.findings.length > 0 ? (
              <>
                <h4 className="findings-header">
                  Safety Findings <span className="findings-count">({report.findings.length})</span>
                </h4>

                {report.findings.map((finding, idx) => (
                  <div key={idx} className={`finding-card ${finding.severity.toLowerCase()}`}>
                    <div className="finding-badges">
                      <span className={`severity-badge ${finding.severity.toLowerCase()}`}>
                        {finding.severity}
                      </span>
                      <span className="type-badge">{finding.finding_type}</span>
                    </div>

                    <div className="finding-section">
                      <strong>Gap / Hazard</strong>
                      <p>{finding.description}</p>
                    </div>

                    <div className="finding-section">
                      <strong>Recommendation</strong>
                      <p>{finding.recommendation}</p>
                    </div>

                    {finding.reference_source && (
                      <span className="finding-ref">
                        📄 {finding.reference_source}
                      </span>
                    )}
                  </div>
                ))}
              </>
            ) : (
              <div className="no-findings">
                <p>No specific safety findings were identified. The permit steps align with the indexed safety standards.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
