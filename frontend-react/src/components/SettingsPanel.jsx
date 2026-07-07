import React from 'react';
import styles from './SettingsPanel.module.css';

/**
 * SettingsPanel component allowing configuration of retrieval parameters.
 * Provides controls for setting Top-K depth during document chunk retrieval.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {number} props.topK - Current Top-K retrieval depth.
 * @param {function(number): void} props.onTopKChange - Callback invoked when the user updates Top-K.
 * @returns {React.JSX.Element} The rendered settings interface.
 */
export default function SettingsPanel({ topK, onTopKChange }) {
  return (
    <div className={styles.settingsContainer}>
      <h2 className={styles.settingsTitle}>Settings</h2>
      
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
    </div>
  );
}
