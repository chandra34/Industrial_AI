import { useState } from 'react';
import { useDashboard } from '../hooks/useDashboard';
import RCADrawer from './RCADrawer';
import './PlantHealthDashboard.css';

/**
 * Plant Health Dashboard component.
 * Renders the 3-zone industrial plant health management interface.
 *
 * @component
 * @param {Object} props
 * @param {function(string, string): void} [props.onOpenCopilot] - Optional handler to launch Copilot with preloaded prompt.
 * @returns {React.JSX.Element}
 */
export default function PlantHealthDashboard({ onOpenCopilot }) {
  const {
    assets,
    allAssetsCount,
    areaList,
    selectedArea,
    setSelectedArea,
    rcaEvents,
    kpis,
    isLoading,
    isRefreshing,
    error,
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    autoRefresh,
    setAutoRefresh,
    rcaTriggeringId,
    handleTriggerRCA,
    refreshDashboard,
  } = useDashboard();

  const [drawerEventId, setDrawerEventId] = useState(null);
  const [drawerPreloaded, setDrawerPreloaded] = useState(null);

  async function handleRunRCA(asset) {
    try {
      const result = await handleTriggerRCA(asset);
      if (result) {
        setDrawerPreloaded(result);
        setDrawerEventId(result.id);
      }
    } catch (err) {
      alert(`RCA Mission execution failed: ${err.message}`);
    }
  }

  function handleOpenEventDetail(eventId) {
    setDrawerPreloaded(null);
    setDrawerEventId(eventId);
  }

  if (isLoading) {
    return (
      <div className="phd-state-wrapper">
        <div className="phd-state-card">
          <div className="phd-loader-spinner" />
          <h3>Initializing Plant Health Stream</h3>
          <p>Connecting to OPC UA Tag Catalog & evaluating real-time statistical anomaly models...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="phd-state-wrapper">
        <div className="phd-state-card phd-state-card--error">
          <span className="phd-state-icon">⚠️</span>
          <h3>Telemetry Service Unavailable</h3>
          <p>{error}</p>
          <button className="phd-retry-btn" onClick={refreshDashboard}>
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const attentionCount = kpis.criticalCount + kpis.warningCount;

  return (
    <div className="phd-root">
      {/* ========================================================================= */}
      {/* ZONE 1: Plant-Wide Summary Bar                                            */}
      {/* ========================================================================= */}
      <section className="phd-zone1-bar" aria-label="Plant-Wide Health Summary Bar">
        {/* Plant Health Gauge Card */}
        <div className="phd-health-score-card">
          <div className={`phd-score-ring ${kpis.plantHealth >= 90 ? 'phd-score--good' : kpis.plantHealth >= 70 ? 'phd-score--warn' : 'phd-score--crit'}`}>
            <span className="phd-score-num">{kpis.plantHealth}%</span>
          </div>
          <div className="phd-score-meta">
            <h1 className="phd-score-title">Plant Health Index</h1>
            <span className="phd-score-sub">{allAssetsCount} Monitored Sensors</span>
          </div>
        </div>

        {/* Aggregate KPI Badges */}
        <div className="phd-kpi-group">
          <div className="phd-kpi-pill phd-kpi-pill--healthy" title="Operating within 3-sigma control limits">
            <span className="phd-kpi-dot" />
            <span className="phd-kpi-count">{kpis.healthyCount}</span>
            <span className="phd-kpi-name">Healthy</span>
          </div>

          <div className="phd-kpi-pill phd-kpi-pill--warning" title="Elevated Z-Score or EWMA drift detected">
            <span className="phd-kpi-dot" />
            <span className="phd-kpi-count">{kpis.warningCount}</span>
            <span className="phd-kpi-name">Warning</span>
          </div>

          <div className="phd-kpi-pill phd-kpi-pill--critical" title="Trip threshold exceeded / ISO Zone D">
            <span className="phd-kpi-dot" />
            <span className="phd-kpi-count">{kpis.criticalCount}</span>
            <span className="phd-kpi-name">Critical</span>
          </div>

          <div className="phd-kpi-pill phd-kpi-pill--rca" title="Active open Root Cause Analysis investigations">
            <span className="phd-kpi-dot" />
            <span className="phd-kpi-count">{kpis.openRCACount}</span>
            <span className="phd-kpi-name">Active RCA</span>
          </div>
        </div>

        {/* Live Controls */}
        <div className="phd-live-controls">
          <label className="phd-toggle-live" title="Auto-refresh anomaly telemetry every 20 seconds">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span className="phd-live-text">
              <span className={`phd-live-indicator ${autoRefresh ? 'active' : ''}`} />
              Live Stream
            </span>
          </label>

          <button
            className="phd-btn-refresh"
            onClick={refreshDashboard}
            disabled={isRefreshing}
            title="Refresh plant telemetry now"
          >
            <svg className={isRefreshing ? 'phd-spin' : ''} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            <span>{isRefreshing ? 'Syncing...' : 'Sync'}</span>
          </button>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* ZONE 2: Asset Health Cards Grid (Management by Exception)                 */}
      {/* ========================================================================= */}
      <section className="phd-zone2-section" aria-label="Asset Health Matrix">
        {/* Controls Toolbar */}
        <div className="phd-toolbar">
          <div className="phd-filter-chips">
            <button
              className={`phd-filter-chip ${activeFilter === 'attention' ? 'active' : ''}`}
              onClick={() => setActiveFilter('attention')}
            >
              🚨 Needs Attention ({attentionCount})
            </button>
            <button
              className={`phd-filter-chip ${activeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setActiveFilter('all')}
            >
              📊 All Assets ({allAssetsCount})
            </button>
            <button
              className={`phd-filter-chip ${activeFilter === 'critical' ? 'active' : ''}`}
              onClick={() => setActiveFilter('critical')}
            >
              ⚡ Critical Only ({kpis.criticalCount})
            </button>
            <button
              className={`phd-filter-chip ${activeFilter === 'healthy' ? 'active' : ''}`}
              onClick={() => setActiveFilter('healthy')}
            >
              🟢 Normal ({kpis.healthyCount})
            </button>
          </div>

          <div className="phd-toolbar-right">
            {/* Area Dropdown */}
            <div className="phd-select-wrapper">
              <label htmlFor="phd-area-select" className="phd-select-label">Area:</label>
              <select
                id="phd-area-select"
                className="phd-area-select"
                value={selectedArea}
                onChange={(e) => setSelectedArea(e.target.value)}
              >
                {areaList.map((area) => (
                  <option key={area} value={area}>
                    {area}
                  </option>
                ))}
              </select>
            </div>

            {/* Keyword Search */}
            <div className="phd-search-box">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                placeholder="Search machine, node, sensor..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button className="phd-search-clear" onClick={() => setSearchQuery('')}>✕</button>
              )}
            </div>
          </div>
        </div>

        {/* Cards Grid */}
        <div className="phd-grid">
          {assets.length === 0 && (
            <div className="phd-no-assets">
              <p>No machines match your active filter criteria.</p>
            </div>
          )}

          {assets.map((asset) => {
            const zScore = asset.methods?.rolling_zscore?.z_score;
            const madScore = asset.methods?.modified_zscore_mad?.modified_z_score;
            const ewmaSlope = asset.methods?.ewma_drift?.slope_per_hour;
            const isoZone = asset.methods?.iso_vibration?.iso_zone;

            const isTrip = asset.severity === 'CRITICAL';
            const isWarn = asset.severity === 'WARNING' || asset.severity === 'DRIFTING';

            return (
              <div
                key={asset.nodeId}
                className={`phd-asset-card phd-asset-card--${asset.severity.toLowerCase()}`}
              >
                {/* Card Top */}
                <div className="phd-card-header">
                  <div className="phd-card-title-group">
                    <span className={`phd-status-indicator phd-status-indicator--${asset.severity.toLowerCase()}`} />
                    <span className="phd-asset-name" title={asset.fullPath}>
                      {asset.displayName}
                    </span>
                  </div>
                  <span className="phd-area-tag">{asset.area}</span>
                </div>

                {/* Primary Metric & Health */}
                <div className="phd-card-metric-row">
                  <div className="phd-metric-block">
                    <span className="phd-metric-val">
                      {asset.currentValue !== undefined && asset.currentValue !== null
                        ? Number(asset.currentValue).toFixed(2)
                        : 'Live'}
                    </span>
                    <span className="phd-metric-unit">{asset.unit || ''}</span>
                  </div>

                  <div className="phd-card-score-block">
                    <span className="phd-card-score-pct">{asset.healthScore}%</span>
                    <span className={`phd-pill phd-pill--${asset.severity.toLowerCase()}`}>
                      {asset.severity}
                    </span>
                  </div>
                </div>

                {/* Statistical Badges (Verified Anomaly Engine Keys) */}
                <div className="phd-stats-badges">
                  {zScore !== undefined && (
                    <span
                      className={`phd-stat-badge ${Math.abs(zScore) >= 2.0 ? 'phd-stat-badge--alert' : ''}`}
                      title={`Rolling Z-Score (ISO 7870): ${zScore > 0 ? '+' : ''}${zScore.toFixed(2)}σ`}
                    >
                      Z: {zScore > 0 ? '+' : ''}{zScore.toFixed(1)}σ
                    </span>
                  )}

                  {madScore !== undefined && (
                    <span
                      className={`phd-stat-badge ${Math.abs(madScore) >= 2.5 ? 'phd-stat-badge--alert' : ''}`}
                      title={`Modified Z-Score / MAD (ASTM E178): ${madScore.toFixed(2)}`}
                    >
                      MAD: {madScore.toFixed(1)}
                    </span>
                  )}

                  {ewmaSlope !== undefined && (
                    <span
                      className={`phd-stat-badge ${Math.abs(ewmaSlope) > 0.05 ? 'phd-stat-badge--alert' : ''}`}
                      title={`EWMA Linear Drift Rate (ISO 11462): ${ewmaSlope.toFixed(3)}/hr`}
                    >
                      Drift: {ewmaSlope > 0 ? '+' : ''}{ewmaSlope.toFixed(2)}/h
                    </span>
                  )}

                  {isoZone && (
                    <span
                      className={`phd-stat-badge ${isoZone === 'C' || isoZone === 'D' ? 'phd-stat-badge--alert' : ''}`}
                      title={`ISO 10816-1 Vibration Severity Zone: ${isoZone}`}
                    >
                      ISO: Zone {isoZone}
                    </span>
                  )}
                </div>

                {/* SVG Mini Sparkline */}
                <div className="phd-card-sparkline" title="Telemetry trajectory baseline">
                  <svg viewBox="0 0 100 22" preserveAspectRatio="none">
                    <path
                      d={
                        isTrip
                          ? 'M 0 16 Q 25 18, 50 12 T 80 8 L 100 2'
                          : isWarn
                          ? 'M 0 14 Q 30 15, 60 10 T 100 5'
                          : 'M 0 11 Q 25 10, 50 12 T 75 10 L 100 11'
                      }
                      fill="none"
                      stroke={isTrip ? '#ef4444' : isWarn ? '#f59e0b' : '#10b981'}
                      strokeWidth="2.2"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>

                {/* Card Action Footer */}
                <div className="phd-card-actions">
                  <button
                    className={`phd-btn-rca ${isTrip ? 'phd-btn-rca--urgent' : ''}`}
                    onClick={() => handleRunRCA(asset)}
                    disabled={rcaTriggeringId === asset.nodeId}
                    title="Launch 3-Pillar Autonomous Root Cause Analysis"
                  >
                    {rcaTriggeringId === asset.nodeId ? (
                      <>
                        <span className="phd-btn-spin" />
                        <span>Diagnosing...</span>
                      </>
                    ) : (
                      <>
                        <span>🔍 Run AI RCA</span>
                      </>
                    )}
                  </button>

                  {onOpenCopilot && (
                    <button
                      className="phd-btn-copilot"
                      onClick={() =>
                        onOpenCopilot(
                          `Investigate operating status and recent telemetry drift for ${asset.displayName} (Node ID: ${asset.nodeId}).`
                        )
                      }
                      title="Open in Copilot Chat"
                    >
                      💬
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ========================================================================= */}
      {/* ZONE 3: Live Alarms & Autonomous RCA Feed                                 */}
      {/* ========================================================================= */}
      <section className="phd-zone3-section" aria-label="Recent Alarms & RCA Feed">
        <div className="phd-zone3-header">
          <div className="phd-zone3-title-wrap">
            <h2 className="phd-zone3-title">Live Alarms & Autonomous Root Cause Feed</h2>
            <span className="phd-feed-badge">{rcaEvents.length} Reports Logged</span>
          </div>
        </div>

        {rcaEvents.length === 0 ? (
          <div className="phd-feed-empty">
            <p>No trip alarms or autonomous RCA missions triggered yet.</p>
          </div>
        ) : (
          <div className="phd-table-container">
            <table className="phd-feed-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Machine / Asset</th>
                  <th>Trigger / Alarm</th>
                  <th>Synthesized Root Cause</th>
                  <th>AI Confidence</th>
                  <th>Status</th>
                  <th className="phd-th-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rcaEvents.map((evt) => (
                  <tr key={evt.id} className={`phd-row phd-row--${(evt.severity || 'warning').toLowerCase()}`}>
                    <td className="phd-cell-time">
                      {new Date(evt.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td className="phd-cell-asset">
                      <strong>{evt.asset_name}</strong>
                    </td>
                    <td className="phd-cell-alarm">
                      <span className={`phd-alarm-tag phd-alarm-tag--${(evt.severity || 'warning').toLowerCase()}`}>
                        {evt.alarm_type}
                      </span>
                    </td>
                    <td className="phd-cell-cause" title={evt.root_cause}>
                      {evt.root_cause}
                    </td>
                    <td className="phd-cell-confidence">
                      <span className={`phd-conf-pill ${evt.confidence_score >= 85 ? 'high' : 'medium'}`}>
                        {evt.confidence_score}%
                      </span>
                    </td>
                    <td className="phd-cell-status">
                      <span className={`phd-status-badge phd-status-badge--${evt.status}`}>
                        {evt.status}
                      </span>
                    </td>
                    <td className="phd-cell-actions">
                      <button
                        className="phd-view-report-btn"
                        onClick={() => handleOpenEventDetail(evt.id)}
                      >
                        View RCA Report →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Slide-out Diagnostic Drawer Modal */}
      {drawerEventId && (
        <RCADrawer
          eventId={drawerEventId}
          preloadedData={drawerPreloaded}
          onClose={() => {
            setDrawerEventId(null);
            setDrawerPreloaded(null);
          }}
          onStatusUpdate={refreshDashboard}
        />
      )}
    </div>
  );
}
