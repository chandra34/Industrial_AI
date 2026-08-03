import React, { useState, useEffect, useCallback } from 'react';
import styles from './SettingsPanel.module.css';
import { reindexOpcuaCatalog, getOpcuaCatalogStatus } from '../api/client';

/**
 * SettingsPanel component for retrieval parameters and industrial connector management.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {number} props.topK - Current Top-K retrieval depth.
 * @param {function(number): void} props.onTopKChange - Callback invoked when the user updates Top-K.
 * @returns {React.JSX.Element} The rendered settings interface.
 */
export default function SettingsPanel({ topK, onTopKChange }) {
  const [catalogStatus, setCatalogStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);

  /** Fetch current catalog status on mount. */
  const fetchStatus = useCallback(async () => {
    try {
      const status = await getOpcuaCatalogStatus();
      setCatalogStatus(status);
    } catch (err) {
      console.error('Failed to fetch OPC UA catalog status:', err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  /** Trigger re-index and poll for completion. */
  const handleSync = async () => {
    setIsSyncing(true);
    setSyncError(null);
    try {
      await reindexOpcuaCatalog();
      // Poll status every 2 seconds until tag count changes or 30s timeout
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const status = await getOpcuaCatalogStatus();
          setCatalogStatus(status);
          if (status.total_tags > 0 || attempts >= 15) {
            clearInterval(poll);
            setIsSyncing(false);
          }
        } catch {
          clearInterval(poll);
          setIsSyncing(false);
        }
      }, 2000);
    } catch (err) {
      setSyncError(err.message || 'Sync failed. Please try again.');
      setIsSyncing(false);
    }
  };

  /** Format the last_updated timestamp for display. */
  const formatLastSynced = (timestamp) => {
    if (!timestamp) return null;
    try {
      const date = new Date(timestamp);
      return date.toLocaleString(undefined, {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return timestamp;
    }
  };

  return (
    <div className={styles.settingsContainer}>
      <h2 className={styles.settingsTitle}>Settings</h2>

      {/* ── Retrieval Settings Card ── */}
      <div className={styles.settingsCard}>
        <h3 className={styles.settingsSubtitle}>Retrieval Settings</h3>
        <p className={styles.settingsDescription}>
          Adjust the retrieval parameters used during query execution.
        </p>

        <div className={styles.settingsGroup}>
          <div className={styles.settingsRow}>
            <label className={styles.settingsLabel} htmlFor="topk-slider">
              Top-K Retrieval Depth:
            </label>
            <span className={styles.settingsValue}>
              {topK} chunks
            </span>
          </div>
          <input
            id="topk-slider"
            className={styles.settingsSlider}
            type="range"
            min="1"
            max="20"
            value={topK}
            onChange={(e) => onTopKChange(parseInt(e.target.value, 10) || 5)}
          />
          <p className={styles.settingsHint}>
            Select how many highly relevant context chunks from your PDF documents are fetched and supplied to the language model. Higher values provide more context but use more tokens.
          </p>
        </div>
      </div>

      {/* ── OPC UA Industrial Connector Card ── */}
      <div className={styles.settingsCard} style={{ marginTop: '16px' }}>
        <h3 className={styles.settingsSubtitle}>🔌 OPC UA Industrial Connector</h3>
        <p className={styles.settingsDescription}>
          Synchronize the physical PLC address space with the local AI tag catalog for instant machine and sensor lookups.
        </p>

        {/* Status Badge */}
        <div className={styles.connectorStatus}>
          {catalogStatus ? (
            <>
              <span className={`${styles.statusDot} ${catalogStatus.total_tags > 0 ? styles.statusDotActive : styles.statusDotInactive}`} />
              <span className={styles.statusText}>
                {catalogStatus.total_tags > 0
                  ? `${catalogStatus.total_tags} tags indexed`
                  : 'Catalog not synced'}
              </span>
              {catalogStatus.last_updated && (
                <span className={styles.statusTimestamp}>
                  · Last synced {formatLastSynced(catalogStatus.last_updated)}
                </span>
              )}
            </>
          ) : (
            <span className={styles.statusText}>Loading status...</span>
          )}
        </div>

        {/* Error Message */}
        {syncError && (
          <p className={styles.syncError}>{syncError}</p>
        )}

        {/* Sync Button */}
        <button
          id="sync-opcua-catalog-btn"
          className={styles.syncButton}
          onClick={handleSync}
          disabled={isSyncing}
        >
          {isSyncing ? (
            <>
              <span className={styles.spinner} />
              Syncing PLC tags…
            </>
          ) : (
            <>⚡ Sync OPC UA Catalog</>
          )}
        </button>
      </div>
    </div>
  );
}
