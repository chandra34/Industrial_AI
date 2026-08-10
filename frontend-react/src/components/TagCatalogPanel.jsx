import { useState, useEffect, useCallback } from 'react';
import { getOpcuaTags, getOpcuaCatalogStatus } from '../api/client';
import './TagCatalogPanel.css';

/**
 * TagCatalogPanel — Dedicated Plant Tag Catalog & Asset Explorer view.
 * Displays all crawled OPC UA tags in a searchable, paginated data table
 * with copy-to-clipboard Node ID support.
 *
 * @component
 * @returns {React.JSX.Element}
 */
export default function TagCatalogPanel() {
  const [tags, setTags] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [nodeClassFilter, setNodeClassFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [catalogStatus, setCatalogStatus] = useState(null);

  const PAGE_SIZE = 50;

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1); // Reset to page 1 on new search
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Fetch catalog status on mount
  useEffect(() => {
    getOpcuaCatalogStatus()
      .then(setCatalogStatus)
      .catch(() => {});
  }, []);

  // Fetch tags whenever search/page/filter changes
  const fetchTags = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getOpcuaTags({
        search: debouncedSearch,
        page,
        pageSize: PAGE_SIZE,
        nodeClass: nodeClassFilter || null,
      });
      setTags(data.tags);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err.message);
      setTags([]);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedSearch, page, nodeClassFilter]);

  useEffect(() => {
    fetchTags();
  }, [fetchTags]);

  // Copy node ID to clipboard
  const handleCopyNodeId = async (nodeId) => {
    try {
      await navigator.clipboard.writeText(nodeId);
      setCopiedId(nodeId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      /* fallback for older browsers */
      const textarea = document.createElement('textarea');
      textarea.value = nodeId;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopiedId(nodeId);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  // Format last updated timestamp
  const formatLastUpdated = (ts) => {
    if (!ts) return 'Never';
    const d = new Date(ts);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <div className="tag-catalog-panel">
      {/* Header */}
      <div className="tag-catalog-header">
        <div className="tag-catalog-header-info">
          <h2 className="tag-catalog-title">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
              <line x1="7" y1="7" x2="7.01" y2="7" />
            </svg>
            Plant Tag Catalog
          </h2>
          <span className="tag-catalog-subtitle">
            Browse and search OPC UA machine tags cached for instant AI lookups.
          </span>
        </div>
        {catalogStatus && (
          <div className="tag-catalog-status-badges">
            <span className="tag-catalog-badge tag-catalog-badge--count">
              {catalogStatus.total_tags.toLocaleString()} tags indexed
            </span>
            <span className="tag-catalog-badge tag-catalog-badge--time">
              Last sync: {formatLastUpdated(catalogStatus.last_updated)}
            </span>
          </div>
        )}
      </div>

      {/* Search & Filter Bar */}
      <div className="tag-catalog-toolbar">
        <div className="tag-catalog-search-wrapper">
          <svg className="tag-catalog-search-icon" width="16" height="16" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            id="tag-catalog-search"
            type="text"
            className="tag-catalog-search-input"
            placeholder="Search by tag name, node ID, or plant path..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="tag-catalog-search-clear" onClick={() => setSearch('')}
              title="Clear search" aria-label="Clear search">
              ×
            </button>
          )}
        </div>
        <select
          id="tag-catalog-filter-class"
          className="tag-catalog-filter-select"
          value={nodeClassFilter}
          onChange={(e) => { setNodeClassFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Types</option>
          <option value="Variable">Variables (Sensors)</option>
          <option value="Object">Objects (Folders)</option>
        </select>
      </div>

      {/* Error State */}
      {error && (
        <div className="tag-catalog-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Data Table */}
      <div className="tag-catalog-table-container">
        <table className="tag-catalog-table">
          <thead>
            <tr>
              <th className="tag-catalog-th tag-catalog-th--name">Tag Name</th>
              <th className="tag-catalog-th tag-catalog-th--symbol">Symbol</th>
              <th className="tag-catalog-th tag-catalog-th--type">Type</th>
              <th className="tag-catalog-th tag-catalog-th--nodeid">Node ID</th>
              <th className="tag-catalog-th tag-catalog-th--actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan="5" className="tag-catalog-loading-cell">
                  <div className="tag-catalog-spinner" />
                  Loading tags...
                </td>
              </tr>
            ) : tags.length === 0 ? (
              <tr>
                <td colSpan="5" className="tag-catalog-empty-cell">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                  <p>{debouncedSearch ? `No tags match "${debouncedSearch}"` : 'No tags indexed yet. Sync your OPC UA server in Settings.'}</p>
                </td>
              </tr>
            ) : (
              tags.map((tag) => (
                <tr key={tag.node_id} className="tag-catalog-row">
                  {/* Tag Name + Path */}
                  <td className="tag-catalog-td tag-catalog-td--name">
                    <span className="tag-catalog-display-name">{tag.display_name || tag.browse_name}</span>
                    <span className="tag-catalog-full-path">{tag.full_path}</span>
                  </td>
                  {/* Symbol (browse_name) */}
                  <td className="tag-catalog-td tag-catalog-td--symbol">
                    <span className="tag-catalog-symbol-badge">{tag.browse_name}</span>
                  </td>
                  {/* Type (data_type badge) */}
                  <td className="tag-catalog-td tag-catalog-td--type">
                    <span className={`tag-catalog-type-badge tag-catalog-type-badge--${(tag.node_class || '').toLowerCase()}`}>
                      {tag.data_type || tag.node_class}
                    </span>
                    {tag.unit && <span className="tag-catalog-unit">{tag.unit}</span>}
                  </td>
                  {/* Node ID */}
                  <td className="tag-catalog-td tag-catalog-td--nodeid">
                    <code className="tag-catalog-node-id">{tag.node_id}</code>
                  </td>
                  {/* Copy Action */}
                  <td className="tag-catalog-td tag-catalog-td--actions">
                    <button
                      className={`tag-catalog-copy-btn ${copiedId === tag.node_id ? 'tag-catalog-copy-btn--copied' : ''}`}
                      onClick={() => handleCopyNodeId(tag.node_id)}
                      title="Copy Node ID to clipboard"
                      aria-label={`Copy ${tag.node_id}`}
                    >
                      {copiedId === tag.node_id ? (
                        <>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          Copied!
                        </>
                      ) : (
                        <>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                          Copy ID
                        </>
                      )}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="tag-catalog-pagination">
          <span className="tag-catalog-pagination-info">
            Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, total)} of {total.toLocaleString()} tags
          </span>
          <div className="tag-catalog-pagination-controls">
            <button
              className="tag-catalog-page-btn"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Prev
            </button>
            <span className="tag-catalog-page-indicator">
              Page {page} of {totalPages}
            </span>
            <button
              className="tag-catalog-page-btn"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
