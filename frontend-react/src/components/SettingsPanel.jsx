import React, { useState, useEffect, useCallback } from 'react';
import styles from './SettingsPanel.module.css';
import { 
  reindexOpcuaCatalog, 
  getOpcuaCatalogStatus,
  getOpcuaProfiles,
  createOpcuaProfile,
  deleteOpcuaProfile,
  testOpcuaConnection,
  connectOpcuaServer,
  getSapProfiles,
  createSapProfile,
  deleteSapProfile,
  testSapConnection,
  connectSapServer
} from '../api/client';

/**
 * SettingsPanel component for retrieval parameters and industrial connector management.
 * Provides dynamic server switching, profile configuration, and catalog sync controls.
 *
 * @component
 * @param {Object} props - Component props.
 * @param {number} props.topK - Current Top-K retrieval depth.
 * @param {function(number): void} props.onTopKChange - Callback invoked when the user updates Top-K.
 * @returns {React.JSX.Element} The rendered settings interface.
 */
export default function SettingsPanel({ topK, onTopKChange }) {
  // Catalog Status State
  const [catalogStatus, setCatalogStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);

  // Profiles and Connection Form State
  const [profiles, setProfiles] = useState([]);
  const [activeProfile, setActiveProfile] = useState(null);
  const [newProfileName, setNewProfileName] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [authMode, setAuthMode] = useState('anonymous');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [securityPolicy, setSecurityPolicy] = useState('');
  
  // Action Feedback States
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  /** Fetch current catalog status on mount. */
  const fetchStatus = useCallback(async () => {
    try {
      const status = await getOpcuaCatalogStatus();
      setCatalogStatus(status);
    } catch (err) {
      console.error('Failed to fetch OPC UA catalog status:', err);
    }
  }, []);

  /** Fetch all saved connection profiles. */
  const fetchProfiles = useCallback(async () => {
    try {
      const data = await getOpcuaProfiles();
      setProfiles(data);
      // Find currently active profile
      const active = data.find(p => p.is_active);
      setActiveProfile(active || null);
    } catch (err) {
      console.error('Failed to fetch OPC UA profiles:', err);
    }
  }, []);

  // SAP ERP Profiles and Connection State
  const [sapProfiles, setSapProfiles] = useState([]);
  const [activeSapProfile, setActiveSapProfile] = useState(null);
  const [sapProfileName, setSapProfileName] = useState('');
  const [sapBaseUrl, setSapBaseUrl] = useState('');
  const [sapAuthType, setSapAuthType] = useState('basic');
  const [sapClientNum, setSapClientNum] = useState('100');
  const [sapUsername, setSapUsername] = useState('');
  const [sapPassword, setSapPassword] = useState('');
  const [sapApiKey, setSapApiKey] = useState('');
  const [sapClientId, setSapClientId] = useState('');
  const [sapClientSecret, setSapClientSecret] = useState('');
  const [sapTokenUrl, setSapTokenUrl] = useState('');

  const [isSapTesting, setIsSapTesting] = useState(false);
  const [sapTestResult, setSapTestResult] = useState(null);
  const [isSapConnecting, setIsSapConnecting] = useState(false);
  const [sapErrorMessage, setSapErrorMessage] = useState(null);

  /** Fetch all saved SAP connection profiles. */
  const fetchSapProfiles = useCallback(async () => {
    try {
      const data = await getSapProfiles();
      setSapProfiles(data);
      const active = data.find(p => p.is_active);
      setActiveSapProfile(active || null);
    } catch (err) {
      console.error('Failed to fetch SAP profiles:', err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchProfiles();
    fetchSapProfiles();
  }, [fetchStatus, fetchProfiles, fetchSapProfiles]);

  /** Test current SAP connection form parameters without saving. */
  const handleSapTestConnection = async (e) => {
    e.preventDefault();
    if (!sapBaseUrl) {
      setSapTestResult({ status: 'failed', message: 'SAP Base URL is required.' });
      return;
    }
    setIsSapTesting(true);
    setSapTestResult(null);
    try {
      const res = await testSapConnection({
        name: sapProfileName || 'Test SAP Profile',
        base_url: sapBaseUrl,
        auth_type: sapAuthType,
        sap_client: sapClientNum || '100',
        username: sapAuthType === 'basic' ? sapUsername : null,
        password: sapAuthType === 'basic' ? sapPassword : null,
        api_key: sapAuthType === 'apikey' ? sapApiKey : null,
        client_id: sapAuthType === 'oauth2' ? sapClientId : null,
        client_secret: sapAuthType === 'oauth2' ? sapClientSecret : null,
        token_url: sapAuthType === 'oauth2' ? sapTokenUrl : null,
      });
      setSapTestResult(res);
    } catch (err) {
      setSapTestResult({ status: 'failed', message: err.message || 'Connection handshake failed.' });
    } finally {
      setIsSapTesting(false);
    }
  };

  /** Save new SAP profile and activate connection. */
  const handleSapSaveAndConnect = async (e) => {
    e.preventDefault();
    if (!sapProfileName || !sapBaseUrl) {
      setSapErrorMessage('Profile Name and Base URL are required.');
      return;
    }
    setIsSapConnecting(true);
    setSapErrorMessage(null);
    setSapTestResult(null);
    try {
      const profile = await createSapProfile({
        name: sapProfileName,
        base_url: sapBaseUrl,
        auth_type: sapAuthType,
        sap_client: sapClientNum || '100',
        username: sapAuthType === 'basic' ? sapUsername : null,
        password: sapAuthType === 'basic' ? sapPassword : null,
        api_key: sapAuthType === 'apikey' ? sapApiKey : null,
        client_id: sapAuthType === 'oauth2' ? sapClientId : null,
        client_secret: sapAuthType === 'oauth2' ? sapClientSecret : null,
        token_url: sapAuthType === 'oauth2' ? sapTokenUrl : null,
      });

      await connectSapServer({ profile_id: profile.id });

      setSapProfileName('');
      setSapBaseUrl('');
      setSapUsername('');
      setSapPassword('');
      setSapApiKey('');
      setSapClientId('');
      setSapClientSecret('');
      setSapTokenUrl('');
      setSapAuthType('basic');
      setSapClientNum('100');

      await fetchSapProfiles();
    } catch (err) {
      setSapErrorMessage(err.message || 'Failed to save and connect to SAP profile.');
    } finally {
      setIsSapConnecting(false);
    }
  };

  /** Connect to an existing saved SAP profile. */
  const handleSapConnectProfile = async (profileId) => {
    setIsSapConnecting(true);
    setSapErrorMessage(null);
    try {
      await connectSapServer({ profile_id: profileId });
      await fetchSapProfiles();
    } catch (err) {
      setSapErrorMessage(err.message || 'Failed to connect to selected SAP profile.');
    } finally {
      setIsSapConnecting(false);
    }
  };

  /** Delete a saved SAP profile. */
  const handleSapDeleteProfile = async (profileId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this SAP connection profile?')) {
      return;
    }
    try {
      await deleteSapProfile(profileId);
      await fetchSapProfiles();
    } catch (err) {
      setSapErrorMessage(err.message || 'Failed to delete SAP profile.');
    }
  };

  /** Trigger catalog re-index and poll for completion. */
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

  /** Test current connection form parameters without saving. */
  const handleTestConnection = async (e) => {
    e.preventDefault();
    if (!endpointUrl) {
      setTestResult({ status: 'failed', message: 'Endpoint URL is required.' });
      return;
    }
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await testOpcuaConnection({
        endpoint_url: endpointUrl,
        username: authMode === 'username_password' ? username : null,
        password: authMode === 'username_password' ? password : null,
        security_policy: securityPolicy || null
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({ status: 'failed', message: err.message || 'Connection handshake failed.' });
    } finally {
      setIsTesting(false);
    }
  };

  /** Save new profile and activate connection. */
  const handleSaveAndConnect = async (e) => {
    e.preventDefault();
    if (!newProfileName || !endpointUrl) {
      setErrorMessage('Profile Name and Endpoint URL are required.');
      return;
    }
    setIsConnecting(true);
    setErrorMessage(null);
    setTestResult(null);
    try {
      // 1. Create the connection profile in DB
      const profile = await createOpcuaProfile({
        name: newProfileName,
        endpoint_url: endpointUrl,
        auth_mode: authMode,
        username: authMode === 'username_password' ? username : null,
        password: authMode === 'username_password' ? password : null,
        security_policy: securityPolicy || null
      });

      // 2. Connect to the newly created profile
      await connectOpcuaServer({ profile_id: profile.id });

      // 3. Reset form and refresh profiles/status
      setNewProfileName('');
      setEndpointUrl('');
      setUsername('');
      setPassword('');
      setSecurityPolicy('');
      setAuthMode('anonymous');
      
      await fetchProfiles();
      await fetchStatus();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to save and connect to profile.');
    } finally {
      setIsConnecting(false);
    }
  };

  /** Connect to an existing saved profile. */
  const handleConnectProfile = async (profileId) => {
    setIsConnecting(true);
    setErrorMessage(null);
    try {
      await connectOpcuaServer({ profile_id: profileId });
      await fetchProfiles();
      await fetchStatus();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to connect to the selected profile.');
    } finally {
      setIsConnecting(false);
    }
  };

  /** Delete a saved profile. */
  const handleDeleteProfile = async (profileId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this connection profile?')) {
      return;
    }
    try {
      await deleteOpcuaProfile(profileId);
      await fetchProfiles();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete profile.');
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
          Connect and synchronize dynamic PLC address spaces with the local AI tag catalog for instant machine lookups.
        </p>

        {/* Dynamic Connection Status Indicator */}
        <div className={styles.activeConnectionBlock}>
          <h4 className={styles.sectionHeader}>Active Server Connection</h4>
          <div className={styles.connectorStatus}>
            <span className={`${styles.statusDot} ${activeProfile ? styles.statusDotActive : styles.statusDotInactive}`} />
            <span className={styles.statusText}>
              {activeProfile ? `${activeProfile.name}` : 'Disconnected (Using .env default)'}
            </span>
            {activeProfile && (
              <span className={styles.activeEndpoint}>
                ({activeProfile.endpoint_url})
              </span>
            )}
          </div>
          
          <div className={styles.catalogSyncStatus}>
            <span>Tag Catalog Status: </span>
            <span className={styles.catalogTagCount}>
              {catalogStatus && catalogStatus.total_tags > 0 
                ? `${catalogStatus.total_tags} tags indexed` 
                : 'No tags indexed'}
            </span>
            {catalogStatus?.last_updated && (
              <span className={styles.statusTimestamp}>
                · Synced {formatLastSynced(catalogStatus.last_updated)}
              </span>
            )}
          </div>

          {/* Sync Button */}
          {syncError && <p className={styles.syncError}>{syncError}</p>}
          <button
            id="sync-opcua-catalog-btn"
            className={styles.syncButton}
            onClick={handleSync}
            disabled={isSyncing}
            style={{ marginTop: '8px' }}
          >
            {isSyncing ? (
              <>
                <span className={styles.spinner} />
                Syncing PLC tags…
              </>
            ) : (
              <>⚡ Sync Active Server Tags</>
            )}
          </button>
        </div>

        {/* Connection Profiles Selection Grid */}
        <div className={styles.profilesSection}>
          <h4 className={styles.sectionHeader}>Saved Machine Connection Profiles</h4>
          {profiles.length === 0 ? (
            <p className={styles.noProfilesText}>No connection profiles saved. Use the form below to add a machine connection.</p>
          ) : (
            <div className={styles.profilesGrid}>
              {profiles.map((profile) => (
                <div 
                  key={profile.id} 
                  className={`${styles.profileCard} ${profile.is_active ? styles.profileCardActive : ''}`}
                >
                  <div className={styles.profileMeta}>
                    <span className={styles.profileName}>{profile.name}</span>
                    <span className={styles.profileUrl}>{profile.endpoint_url}</span>
                    {profile.username && (
                      <span className={styles.profileUser}>User: {profile.username}</span>
                    )}
                  </div>
                  <div className={styles.profileCardActions}>
                    {profile.is_active ? (
                      <span className={styles.activeBadge}>Active 🟢</span>
                    ) : (
                      <button 
                        className={styles.connectProfileBtn}
                        onClick={() => handleConnectProfile(profile.id)}
                        disabled={isConnecting}
                      >
                        Connect
                      </button>
                    )}
                    {!profile.is_active && (
                      <button 
                        className={styles.deleteProfileBtn}
                        onClick={(e) => handleDeleteProfile(profile.id, e)}
                        title="Delete Profile"
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Connection Form */}
        <div className={styles.addProfileSection}>
          <h4 className={styles.sectionHeader}>Add New Machine Connection</h4>
          <form className={styles.connectionForm} onSubmit={handleSaveAndConnect}>
            {errorMessage && <p className={styles.syncError}>{errorMessage}</p>}
            
            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Profile / Machine Name</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  placeholder="e.g. Satake Sorter Line 1"
                  value={newProfileName}
                  onChange={(e) => setNewProfileName(e.target.value)}
                  required
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Server Endpoint URL</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  placeholder="opc.tcp://192.168.1.50:4840"
                  value={endpointUrl}
                  onChange={(e) => setEndpointUrl(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Security Policy Mode</label>
                <select 
                  className={styles.formSelect}
                  value={securityPolicy}
                  onChange={(e) => setSecurityPolicy(e.target.value)}
                >
                  <option value="">None (Insecure)</option>
                  <option value="Basic256Sha256,SignAndEncrypt">Basic256Sha256, Sign & Encrypt</option>
                  <option value="Basic256,Sign">Basic256, Sign</option>
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Authentication Mode</label>
                <div className={styles.authRadioGroup}>
                  <label className={styles.radioLabel}>
                    <input 
                      type="radio" 
                      name="auth_mode"
                      value="anonymous"
                      checked={authMode === 'anonymous'}
                      onChange={() => setAuthMode('anonymous')}
                    />
                    Anonymous
                  </label>
                  <label className={styles.radioLabel}>
                    <input 
                      type="radio" 
                      name="auth_mode"
                      value="username_password"
                      checked={authMode === 'username_password'}
                      onChange={() => setAuthMode('username_password')}
                    />
                    Credentials
                  </label>
                </div>
              </div>
            </div>

            {authMode === 'username_password' && (
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Username</label>
                  <input 
                    type="text" 
                    className={styles.formInput} 
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Password</label>
                  <input 
                    type="password" 
                    className={styles.formInput} 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            {testResult && (
              <div className={`${styles.testFeedback} ${testResult.status === 'connected' ? styles.testSuccess : styles.testError}`}>
                {testResult.message} {testResult.latency_ms > 0 && `(Ping: ${testResult.latency_ms}ms)`}
              </div>
            )}

            <div className={styles.formActions}>
              <button 
                type="button" 
                className={styles.testButton}
                onClick={handleTestConnection}
                disabled={isTesting || isConnecting}
              >
                {isTesting ? 'Testing Handshake...' : '🔌 Test Connection'}
              </button>
              
              <button 
                type="submit" 
                className={styles.saveButton}
                disabled={isConnecting || isTesting}
              >
                {isConnecting ? 'Establishing Connection...' : '💾 Save & Connect'}
              </button>
            </div>
          </form>
        </div>

      </div>

      {/* ── SAP S/4HANA ERP Connector Card ── */}
      <div className={styles.settingsCard} style={{ marginTop: '16px' }}>
        <h3 className={styles.settingsSubtitle}>💼 SAP S/4HANA ERP Connector</h3>
        <p className={styles.settingsDescription}>
          Connect and switch SAP S/4HANA or SAP ECC enterprise environments dynamically for live Equipment, Maintenance Order, and BOM queries.
        </p>

        {/* Dynamic Connection Status Indicator */}
        <div className={styles.activeConnectionBlock}>
          <h4 className={styles.sectionHeader}>Active SAP Server Connection</h4>
          <div className={styles.connectorStatus}>
            <span className={`${styles.statusDot} ${activeSapProfile ? styles.statusDotActive : styles.statusDotInactive}`} />
            <span className={styles.statusText}>
              {activeSapProfile ? `${activeSapProfile.name}` : 'Disconnected (Using .env default)'}
            </span>
            {activeSapProfile && (
              <span className={styles.activeEndpoint}>
                ({activeSapProfile.base_url} · Auth: {activeSapProfile.auth_type.toUpperCase()} · Client: {activeSapProfile.sap_client})
              </span>
            )}
          </div>
        </div>

        {/* Connection Profiles Selection Grid */}
        <div className={styles.profilesSection}>
          <h4 className={styles.sectionHeader}>Saved SAP Environment Profiles</h4>
          {sapProfiles.length === 0 ? (
            <p className={styles.noProfilesText}>No SAP connection profiles saved. Use the form below to add an SAP environment.</p>
          ) : (
            <div className={styles.profilesGrid}>
              {sapProfiles.map((profile) => (
                <div 
                  key={profile.id} 
                  className={`${styles.profileCard} ${profile.is_active ? styles.profileCardActive : ''}`}
                >
                  <div className={styles.profileMeta}>
                    <span className={styles.profileName}>{profile.name}</span>
                    <span className={styles.profileUrl}>{profile.base_url}</span>
                    <span className={styles.profileUser}>
                      Auth: {profile.auth_type.toUpperCase()} | Client: {profile.sap_client}
                      {profile.username && ` | User: ${profile.username}`}
                    </span>
                  </div>
                  <div className={styles.profileCardActions}>
                    {profile.is_active ? (
                      <span className={styles.activeBadge}>Active 🟢</span>
                    ) : (
                      <button 
                        className={styles.connectProfileBtn}
                        onClick={() => handleSapConnectProfile(profile.id)}
                        disabled={isSapConnecting}
                      >
                        Connect
                      </button>
                    )}
                    {!profile.is_active && (
                      <button 
                        className={styles.deleteProfileBtn}
                        onClick={(e) => handleSapDeleteProfile(profile.id, e)}
                        title="Delete Profile"
                      >
                        🗑️
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Connection Form */}
        <div className={styles.addProfileSection}>
          <h4 className={styles.sectionHeader}>Add New SAP Environment</h4>
          <form className={styles.connectionForm} onSubmit={handleSapSaveAndConnect}>
            {sapErrorMessage && <p className={styles.syncError}>{sapErrorMessage}</p>}
            
            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Profile / System Name</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  placeholder="e.g. SAP S/4HANA Production"
                  value={sapProfileName}
                  onChange={(e) => setSapProfileName(e.target.value)}
                  required
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>SAP Base URL</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  placeholder="https://my-s4hana.company.com"
                  value={sapBaseUrl}
                  onChange={(e) => setSapBaseUrl(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Authentication Mode</label>
                <div className={styles.authRadioGroup}>
                  <label className={styles.radioLabel}>
                    <input 
                      type="radio" 
                      name="sap_auth_type"
                      value="basic"
                      checked={sapAuthType === 'basic'}
                      onChange={() => setSapAuthType('basic')}
                    />
                    Basic Auth
                  </label>
                  <label className={styles.radioLabel}>
                    <input 
                      type="radio" 
                      name="sap_auth_type"
                      value="apikey"
                      checked={sapAuthType === 'apikey'}
                      onChange={() => setSapAuthType('apikey')}
                    />
                    API Key (Sandbox)
                  </label>
                  <label className={styles.radioLabel}>
                    <input 
                      type="radio" 
                      name="sap_auth_type"
                      value="oauth2"
                      checked={sapAuthType === 'oauth2'}
                      onChange={() => setSapAuthType('oauth2')}
                    />
                    OAuth 2.0
                  </label>
                </div>
              </div>
              
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>SAP Client Number (Mandant)</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  placeholder="100"
                  value={sapClientNum}
                  onChange={(e) => setSapClientNum(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Basic Auth Form Fields */}
            {sapAuthType === 'basic' && (
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>SAP Service Username</label>
                  <input 
                    type="text" 
                    className={styles.formInput} 
                    value={sapUsername}
                    onChange={(e) => setSapUsername(e.target.value)}
                    required
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Password</label>
                  <input 
                    type="password" 
                    className={styles.formInput} 
                    value={sapPassword}
                    onChange={(e) => setSapPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            {/* API Key Form Field */}
            {sapAuthType === 'apikey' && (
              <div className={styles.formRow}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>API Key</label>
                  <input 
                    type="password" 
                    className={styles.formInput} 
                    placeholder="Enter SAP API Key"
                    value={sapApiKey}
                    onChange={(e) => setSapApiKey(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            {/* OAuth 2.0 Form Fields */}
            {sapAuthType === 'oauth2' && (
              <>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>OAuth Token Endpoint URL</label>
                    <input 
                      type="text" 
                      className={styles.formInput} 
                      placeholder="https://<subdomain>.authentication.eu10.hana.ondemand.com/oauth/token"
                      value={sapTokenUrl}
                      onChange={(e) => setSapTokenUrl(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Client ID</label>
                    <input 
                      type="text" 
                      className={styles.formInput} 
                      value={sapClientId}
                      onChange={(e) => setSapClientId(e.target.value)}
                      required
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Client Secret</label>
                    <input 
                      type="password" 
                      className={styles.formInput} 
                      value={sapClientSecret}
                      onChange={(e) => setSapClientSecret(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </>
            )}

            {sapTestResult && (
              <div className={`${styles.testFeedback} ${sapTestResult.status === 'connected' ? styles.testSuccess : styles.testError}`}>
                {sapTestResult.message} {sapTestResult.latency_ms > 0 && `(Ping: ${sapTestResult.latency_ms}ms)`}
              </div>
            )}

            <div className={styles.formActions}>
              <button 
                type="button" 
                className={styles.testButton}
                onClick={handleSapTestConnection}
                disabled={isSapTesting || isSapConnecting}
              >
                {isSapTesting ? 'Testing Handshake...' : '🔌 Test SAP Connection'}
              </button>
              
              <button 
                type="submit" 
                className={styles.saveButton}
                disabled={isSapConnecting || isSapTesting}
              >
                {isSapConnecting ? 'Establishing Connection...' : '💾 Save & Connect SAP'}
              </button>
            </div>
          </form>
        </div>

      </div>
    </div>
  );
}
