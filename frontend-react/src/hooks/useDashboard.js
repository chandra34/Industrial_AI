import { useState, useEffect, useCallback, useRef } from 'react';
import { getOpcuaTags } from '../api/client';
import { getNodeAnomalies, getRCAEvents, triggerManualRCA } from '../api/dashboardApi';

/**
 * Detect sensor type heuristic from tag path or name.
 *
 * @param {string} name - Tag display or browse name.
 * @param {string} fullPath - Full OPC UA hierarchical path.
 * @returns {'temperature'|'pressure'|'vibration'|'speed'|'current'|'flow'|'general'}
 */
function detectSensorType(name = '', fullPath = '') {
  const combined = `${name} ${fullPath}`.toLowerCase();
  if (combined.includes('vib') || combined.includes('vibration') || combined.includes('accel') || combined.includes('mm_s') || combined.includes('velocity')) {
    return 'vibration';
  }
  if (combined.includes('temp') || combined.includes('degc') || combined.includes('celsius') || combined.includes('fahrenheit')) {
    return 'temperature';
  }
  if (combined.includes('press') || combined.includes('psi') || combined.includes('bar') || combined.includes('kpa')) {
    return 'pressure';
  }
  if (combined.includes('rpm') || combined.includes('speed') || combined.includes('velocity')) {
    return 'speed';
  }
  if (combined.includes('amp') || combined.includes('curr') || combined.includes('current')) {
    return 'current';
  }
  if (combined.includes('flow') || combined.includes('gpm') || combined.includes('m3_h')) {
    return 'flow';
  }
  return 'general';
}

/**
 * Extracts a plant area/unit name from the OPC UA full path string.
 *
 * @param {string} fullPath - e.g. "Root > Objects > Boiler_House > Feed_Pump_02 > Vibration"
 * @returns {string} Plant Area (e.g. "Boiler_House")
 */
function extractArea(fullPath = '') {
  if (!fullPath) return 'General Area';
  const parts = fullPath.split('>').map((s) => s.trim()).filter(Boolean);
  if (parts.length >= 3) {
    return parts[2].replace(/_/g, ' ');
  }
  if (parts.length >= 2) {
    return parts[1].replace(/_/g, ' ');
  }
  return 'Main Plant';
}

/**
 * Custom React hook for the Plant Health Dashboard.
 * Coordinates real-time anomaly scores, asset severity, RCA feeds, and 1-click diagnostics.
 *
 * @returns {Object} Dashboard state slices, asset lists, KPIs, and trigger handlers.
 */
export function useDashboard() {
  const [assets, setAssets] = useState([]);
  const [rcaEvents, setRCAEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArea, setSelectedArea] = useState('All');
  const [activeFilter, setActiveFilter] = useState('attention'); // 'attention' | 'all' | 'healthy' | 'critical'
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [rcaTriggeringId, setRcaTriggeringId] = useState(null);
  const intervalRef = useRef(null);

  /**
   * Fetches OPC UA tags, evaluates anomaly statistics, and retrieves RCA event history.
   */
  const fetchDashboardData = useCallback(async (showLoader = true) => {
    try {
      if (showLoader) setIsLoading(true);
      else setIsRefreshing(true);
      setError(null);

      // 1. Fetch Variable-type tags from OPC UA Catalog (up to 100 sensors)
      const tagResult = await getOpcuaTags({ nodeClass: 'Variable', pageSize: 100 });
      const rawTags = tagResult?.tags || [];

      // 2. Concurrently evaluate statistical anomalies for up to 30 key sensor tags
      const sampleTags = rawTags.slice(0, 30);
      const anomalySettled = await Promise.allSettled(
        sampleTags.map((tag) => {
          const sType = detectSensorType(tag.display_name || tag.browse_name, tag.full_path);
          return getNodeAnomalies(tag.node_id, 24, sType);
        })
      );

      // 3. Merge telemetry analytics into rich asset models
      const enrichedAssets = sampleTags.map((tag, idx) => {
        const result = anomalySettled[idx];
        const anomalyData = result.status === 'fulfilled' ? result.value : null;

        const severity = anomalyData?.overall_severity || 'HEALTHY';
        let healthScore = 98;
        if (severity === 'CRITICAL') healthScore = 32;
        else if (severity === 'WARNING') healthScore = 64;
        else if (severity === 'DRIFTING') healthScore = 79;
        else if (severity === 'FLAT_SIGNAL' || severity === 'INSUFFICIENT_DATA') healthScore = 90;

        return {
          nodeId: tag.node_id,
          displayName: tag.display_name || tag.browse_name || tag.node_id,
          browseName: tag.browse_name,
          fullPath: tag.full_path,
          unit: tag.unit || '',
          dataType: tag.data_type,
          area: extractArea(tag.full_path),
          severity,
          healthScore,
          currentValue: anomalyData?.current_value,
          anomaly: anomalyData,
          methods: anomalyData?.methods || {},
        };
      });

      // 4. Sort: CRITICAL and WARNING assets float to top (Management by Exception)
      const severityRank = { CRITICAL: 0, WARNING: 1, DRIFTING: 2, FLAT_SIGNAL: 3, INSUFFICIENT_DATA: 4, HEALTHY: 5 };
      enrichedAssets.sort((a, b) => (severityRank[a.severity] ?? 5) - (severityRank[b.severity] ?? 5));

      setAssets(enrichedAssets);

      // 5. Fetch RCA Event history
      const events = await getRCAEvents({ limit: 25 });
      setRCAEvents(Array.isArray(events) ? events : []);
    } catch (err) {
      console.error('Failed to load Plant Health Dashboard data:', err);
      setError(err.message || 'Failed to communicate with Industrial telemetry services.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchDashboardData(true);
  }, [fetchDashboardData]);

  // Auto-refresh interval (every 20s if enabled)
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        fetchDashboardData(false);
      }, 20000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh, fetchDashboardData]);

  /**
   * Dispatches an on-demand AI Root Cause Analysis mission for an asset card.
   *
   * @param {Object} asset - Asset model from card.
   * @returns {Promise<Object>} Completed RCA diagnostic report.
   */
  const handleTriggerRCA = useCallback(async (asset) => {
    setRcaTriggeringId(asset.nodeId);
    try {
      const payload = {
        node_id: asset.nodeId,
        asset_name: asset.displayName,
        alarm_type: asset.severity !== 'HEALTHY' ? `${asset.severity} Telemetry Outlier` : 'Manual Health Audit',
        severity: asset.severity === 'CRITICAL' ? 'CRITICAL' : 'WARNING',
        extra_context: `Current telemetry reading: ${asset.currentValue ?? 'N/A'} ${asset.unit}`,
      };
      const rcaResult = await triggerManualRCA(payload);

      // Refresh event list
      const refreshedEvents = await getRCAEvents({ limit: 25 });
      setRCAEvents(Array.isArray(refreshedEvents) ? refreshedEvents : []);

      return rcaResult;
    } catch (err) {
      console.error('Manual RCA trigger failed:', err);
      throw err;
    } finally {
      setRcaTriggeringId(null);
    }
  }, []);

  // Unique list of plant areas for dropdown filter
  const areaList = ['All', ...new Set(assets.map((a) => a.area).filter(Boolean))];

  // Filtered asset view
  const filteredAssets = assets.filter((asset) => {
    // Area filter
    if (selectedArea !== 'All' && asset.area !== selectedArea) {
      return false;
    }

    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = asset.displayName.toLowerCase().includes(q);
      const matchNode = asset.nodeId.toLowerCase().includes(q);
      const matchPath = (asset.fullPath || '').toLowerCase().includes(q);
      if (!matchName && !matchNode && !matchPath) return false;
    }

    // Status filter chips
    if (activeFilter === 'attention') {
      return asset.severity !== 'HEALTHY';
    }
    if (activeFilter === 'critical') {
      return asset.severity === 'CRITICAL';
    }
    if (activeFilter === 'healthy') {
      return asset.severity === 'HEALTHY';
    }
    return true; // 'all'
  });

  // Aggregated Plant KPIs for Zone 1
  const totalMonitored = assets.length;
  const criticalCount = assets.filter((a) => a.severity === 'CRITICAL').length;
  const warningCount = assets.filter((a) => a.severity === 'WARNING' || a.severity === 'DRIFTING').length;
  const healthyCount = assets.filter((a) => a.severity === 'HEALTHY').length;

  const plantHealth = totalMonitored > 0
    ? Math.round(assets.reduce((acc, curr) => acc + curr.healthScore, 0) / totalMonitored)
    : 100;

  const openRCACount = rcaEvents.filter((e) => e.status === 'open').length;

  const kpis = {
    totalMonitored,
    criticalCount,
    warningCount,
    healthyCount,
    plantHealth,
    openRCACount,
  };

  return {
    assets: filteredAssets,
    allAssetsCount: assets.length,
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
    refreshDashboard: () => fetchDashboardData(false),
  };
}
