import React, { useState, useEffect, useMemo } from 'react'
import './App.css'

const API_BASE = '/api'

const REASON_CONFIG = {
  VALUE_MISMATCH: {
    label: 'Value Mismatch',
    badgeClass: 'badge-value-mismatch',
    icon: '⚡',
    color: '#d97706',
    desc: 'System B value differs from System A total',
  },
  MISSING_IN_B: {
    label: 'Missing in System B',
    badgeClass: 'badge-missing',
    icon: '🚫',
    color: '#dc2626',
    desc: 'Record in System A with no counterpart in B',
  },
  ORPHAN_IN_B: {
    label: 'Orphan in System B',
    badgeClass: 'badge-orphan',
    icon: '👻',
    color: '#6366f1',
    desc: 'System B entry references non-existent A record',
  },
  DUPLICATE_IN_B: {
    label: 'Duplicate in System B',
    badgeClass: 'badge-duplicate',
    icon: '📑',
    color: '#ea580c',
    desc: 'Multiple entries in B not summing to total',
  },
  LOCATION_MISMATCH: {
    label: 'Location Mismatch',
    badgeClass: 'badge-location',
    icon: '📍',
    color: '#8b5cf6',
    desc: 'Branch code discrepancy between ledgers',
  },
  DATE_MISMATCH: {
    label: 'Date Mismatch',
    badgeClass: 'badge-date',
    icon: '📅',
    color: '#0284c7',
    desc: 'Event date differs from recorded date',
  },
  VOIDED_RECORD_HAS_ENTRY: {
    label: 'Voided with Entry',
    badgeClass: 'badge-voided',
    icon: '⚠️',
    color: '#475569',
    desc: 'Voided transaction with active B entry',
  },
}

function formatCurrency(val) {
  if (val === null || val === undefined || val === '') {
    return null
  }
  const num = typeof val === 'number' ? val : parseFloat(val)
  if (isNaN(num)) return null
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function ReasonBadge({ reason }) {
  const cfg = REASON_CONFIG[reason] || {
    label: reason,
    badgeClass: 'badge-generic',
    icon: 'ℹ️',
  }
  return (
    <span className={`badge ${cfg.badgeClass}`}>
      <span className="badge-icon">{cfg.icon}</span>
      <span>{cfg.label}</span>
    </span>
  )
}

export default function App() {
  const [orgsList, setOrgsList] = useState(['ORG-A', 'ORG-B'])
  const [selectedOrg, setSelectedOrg] = useState('ORG-A')
  const [selectedReason, setSelectedReason] = useState('')
  const [sortField, setSortField] = useState('value')
  const [sortDirection, setSortDirection] = useState('desc') // 'asc' or 'desc'
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedRow, setExpandedRow] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)

  const [data, setData] = useState({
    org: 'ORG-A',
    total_count: 0,
    reason_summary: {},
    results: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Show temporary toast feedback
  const showToast = (msg) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 3000)
  }

  // Fetch available orgs on mount
  useEffect(() => {
    fetch(`${API_BASE}/orgs/`)
      .then((res) => (res.ok ? res.json() : Promise.reject('Failed to fetch orgs')))
      .then((resData) => {
        if (resData.orgs && resData.orgs.length > 0) {
          const list = resData.orgs.map((o) => o.org_id)
          setOrgsList(list)
          if (!list.includes(selectedOrg)) {
            setSelectedOrg(list[0])
          }
        }
      })
      .catch((err) => {
        console.warn('Could not load orgs list, using fallback:', err)
      })
  }, [])

  // Fetch disagreements
  const loadData = () => {
    if (!selectedOrg) return

    setLoading(true)
    setError(null)

    const sortParam = `${sortDirection === 'desc' ? '-' : ''}${sortField}`
    const params = new URLSearchParams({
      org: selectedOrg,
      sort: sortParam,
    })
    if (selectedReason) {
      params.append('reason', selectedReason)
    }

    fetch(`${API_BASE}/disagreements/?${params.toString()}`)
      .then((res) => {
        if (!res.ok) {
          return res.json().then((d) => Promise.reject(d.error || 'Server error'))
        }
        return res.json()
      })
      .then((resData) => {
        setData(resData)
        setLoading(false)
      })
      .catch((err) => {
        console.error('Fetch error:', err)
        setError(typeof err === 'string' ? err : 'Unable to connect to reconciliation API')
        setLoading(false)
      })
  }

  useEffect(() => {
    loadData()
  }, [selectedOrg, selectedReason, sortField, sortDirection])

  const handleHeaderSort = (field) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  // Copy Record ID helper
  const copyToClipboard = (text, e) => {
    e.stopPropagation()
    navigator.clipboard.writeText(text)
    setCopiedId(text)
    showToast(`Copied ${text} to clipboard!`)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Export current table view to CSV
  const exportToCSV = () => {
    if (!filteredResults.length) return
    const headers = [
      'Reason',
      'Record ID',
      'Entry ID',
      'Location',
      'System A Value',
      'System B Value',
      'Difference',
      'Details',
    ]
    const rows = filteredResults.map((r) => [
      `"${r.reason}"`,
      `"${r.record_id || ''}"`,
      `"${r.entry_id || ''}"`,
      `"${r.location_id || ''}"`,
      r.a_value !== null ? r.a_value : '',
      r.b_value !== null ? r.b_value : '',
      r.difference !== null ? r.difference : '',
      `"${(r.details || '').replace(/"/g, '""')}"`,
    ])

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')

    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `reconciliation_${selectedOrg}_${Date.now()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    showToast(`Exported ${filteredResults.length} records to CSV`)
  }

  // Client-side search filtering
  const filteredResults = useMemo(() => {
    if (!data.results) return []
    if (!searchTerm.trim()) return data.results

    const q = searchTerm.toLowerCase().trim()
    return data.results.filter(
      (item) =>
        (item.record_id && item.record_id.toLowerCase().includes(q)) ||
        (item.entry_id && item.entry_id.toLowerCase().includes(q)) ||
        (item.location_id && item.location_id.toLowerCase().includes(q)) ||
        (item.details && item.details.toLowerCase().includes(q))
    )
  }, [data.results, searchTerm])

  const totalDiscrepancies = Object.values(data.reason_summary || {}).reduce(
    (a, b) => a + b,
    0
  )

  return (
    <div className="app-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="toast-banner">
          <span>✨ {toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo-container">
            <span className="brand-icon">⚖️</span>
          </div>
          <div className="brand-text">
            <div className="brand-badge">Financial Ledger OS</div>
            <h1>Dual-Ledger Reconciliation</h1>
            <p>Automated discrepancy detection between System A & System B with zero-leak tenant isolation</p>
          </div>
        </div>

        {/* Interactive Tenant Switcher */}
        <div className="tenant-switcher-card">
          <span className="tenant-switcher-label">Active Organization:</span>
          <div className="segmented-control">
            {orgsList.map((org) => {
              const isActive = selectedOrg === org
              return (
                <button
                  key={org}
                  type="button"
                  className={`segment-btn ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    if (selectedOrg !== org) {
                      setSelectedOrg(org)
                      setSelectedReason('')
                      setExpandedRow(null)
                      showToast(`Switched workspace to ${org}`)
                    }
                  }}
                >
                  <span className="segment-indicator"></span>
                  <span className="segment-text">{org}</span>
                  {isActive && <span className="active-dot"></span>}
                </button>
              )
            })}
          </div>
        </div>
      </header>

      {/* Tenant Boundary Safety Banner */}
      <div className="tenant-notice-banner">
        <div className="notice-left">
          <span className="shield-icon">🛡️</span>
          <div>
            <strong>Strict Tenant Boundary Enforced:</strong> All queries filtered for{' '}
            <span className="tenant-highlight">{selectedOrg}</span> at database query time.
            Foreign tenant locations are protected and redacted.
          </div>
        </div>
        <div className="system-pill">
          <span className="pulse-dot"></span>
          <span>Ledgers Synchronized</span>
        </div>
      </div>

      {/* Interactive Metric Cards Grid */}
      <section className="metrics-section">
        <div className="section-label">Discrepancy Overview by Reason (Click to filter):</div>
        <div className="metrics-grid">
          {/* Total Card */}
          <button
            type="button"
            className={`metric-card total-card ${selectedReason === '' ? 'active' : ''}`}
            onClick={() => setSelectedReason('')}
          >
            <div className="metric-header">
              <span className="metric-label">All Discrepancies</span>
              <span className="metric-icon-bubble">📊</span>
            </div>
            <div className="metric-value">{totalDiscrepancies}</div>
            <div className="metric-footer">
              <span>{selectedReason === '' ? 'Currently viewing all' : 'Click to view all'}</span>
            </div>
          </button>

          {/* Individual Category Cards */}
          {Object.entries(data.reason_summary || {}).map(([reason, count]) => {
            const cfg = REASON_CONFIG[reason] || {
              label: reason,
              icon: '📌',
              color: '#3b82f6',
            }
            const isSelected = selectedReason === reason

            return (
              <button
                key={reason}
                type="button"
                className={`metric-card ${isSelected ? 'active' : ''}`}
                onClick={() => setSelectedReason((prev) => (prev === reason ? '' : reason))}
              >
                <div className="metric-header">
                  <span className="metric-label">{cfg.label}</span>
                  <span className="metric-icon-bubble">{cfg.icon}</span>
                </div>
                <div className="metric-value">{count}</div>
                <div className="metric-footer">
                  <span>{isSelected ? '✓ Filter active' : 'Click to filter'}</span>
                </div>
              </button>
            )
          })}
        </div>
      </section>

      {/* Interactive Controls & Filters Bar */}
      <div className="controls-card">
        <div className="controls-left">
          {/* Reason Select Dropdown */}
          <div className="control-field">
            <label htmlFor="reason-filter">Filter Reason:</label>
            <div className="select-wrapper">
              <select
                id="reason-filter"
                className="custom-select"
                value={selectedReason}
                onChange={(e) => setSelectedReason(e.target.value)}
              >
                <option value="">All Discrepancy Reasons</option>
                <option value="VALUE_MISMATCH">⚡ Value Mismatch</option>
                <option value="MISSING_IN_B">🚫 Missing in System B</option>
                <option value="ORPHAN_IN_B">👻 Orphan in System B</option>
                <option value="DUPLICATE_IN_B">📑 Duplicate in System B</option>
                <option value="LOCATION_MISMATCH">📍 Location Mismatch</option>
                <option value="DATE_MISMATCH">📅 Date Mismatch</option>
                <option value="VOIDED_RECORD_HAS_ENTRY">⚠️ Voided with Active Entry</option>
              </select>
            </div>
          </div>

          {/* Sort Order Select */}
          <div className="control-field">
            <label htmlFor="sort-select">Sort Order:</label>
            <div className="select-wrapper">
              <select
                id="sort-select"
                className="custom-select"
                value={`${sortDirection === 'desc' ? '-' : ''}${sortField}`}
                onChange={(e) => {
                  const val = e.target.value
                  setSortDirection(val.startsWith('-') ? 'desc' : 'asc')
                  setSortField(val.replace('-', ''))
                }}
              >
                <option value="-value">Value: High to Low</option>
                <option value="value">Value: Low to High</option>
                <option value="-difference">Difference: High to Low</option>
                <option value="difference">Difference: Low to High</option>
                <option value="record_id">Record ID: A &rarr; Z</option>
                <option value="-record_id">Record ID: Z &rarr; A</option>
                <option value="reason">Reason: A &rarr; Z</option>
              </select>
            </div>
          </div>
        </div>

        <div className="controls-right">
          {/* Search Box */}
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              className="search-input"
              placeholder="Search ID, location, details..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button
                type="button"
                className="clear-search-btn"
                onClick={() => setSearchTerm('')}
              >
                ✕
              </button>
            )}
          </div>

          {/* Interactive Action Buttons */}
          <div className="btn-actions-group">
            <button
              type="button"
              className="action-btn btn-secondary"
              onClick={loadData}
              disabled={loading}
              title="Refresh ledger data"
            >
              <span className={`btn-icon ${loading ? 'spinning' : ''}`}>🔄</span>
              <span>Refresh</span>
            </button>

            <button
              type="button"
              className="action-btn btn-primary"
              onClick={exportToCSV}
              disabled={loading || filteredResults.length === 0}
              title="Export current discrepancies to CSV"
            >
              <span className="btn-icon">📥</span>
              <span>Export CSV</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Reconciliation Table */}
      <div className="table-card">
        {loading ? (
          <div className="state-container">
            <div className="spinner-loader"></div>
            <div className="state-title">Reconciling Ledgers...</div>
            <div className="state-desc">
              Analyzing transactions across System A and System B for {selectedOrg}
            </div>
          </div>
        ) : error ? (
          <div className="state-container state-error">
            <div className="state-icon">⚠️</div>
            <div className="state-title">Connection Error</div>
            <div className="state-desc">{error}</div>
            <button type="button" className="action-btn btn-primary" onClick={loadData}>
              Try Again
            </button>
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="state-container">
            <div className="state-icon">🎉</div>
            <div className="state-title">No Disagreements Found</div>
            <div className="state-desc">
              {selectedReason
                ? `No rows matched the filter '${REASON_CONFIG[selectedReason]?.label || selectedReason}'.`
                : `Both systems agree completely for ${selectedOrg} on all checked records.`}
            </div>
            {selectedReason && (
              <button
                type="button"
                className="action-btn btn-secondary"
                onClick={() => setSelectedReason('')}
                style={{ marginTop: '12px' }}
              >
                Clear Filter
              </button>
            )}
          </div>
        ) : (
          <div className="table-responsive">
            <table className="reconcile-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    onClick={() => handleHeaderSort('reason')}
                    title="Sort by Reason"
                  >
                    <div className="th-content">
                      <span>Reason</span>
                      <span className="sort-arrow">
                        {sortField === 'reason' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </div>
                  </th>

                  <th
                    className="sortable"
                    onClick={() => handleHeaderSort('record_id')}
                    title="Sort by Record ID"
                  >
                    <div className="th-content">
                      <span>Record ID</span>
                      <span className="sort-arrow">
                        {sortField === 'record_id' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </div>
                  </th>

                  <th>Location (A / B)</th>
                  <th>Dates (Event / Recorded)</th>

                  <th
                    className="sortable text-right"
                    onClick={() => handleHeaderSort('value')}
                    title="Sort by Value"
                  >
                    <div className="th-content justify-end">
                      <span>System A Total</span>
                      <span className="sort-arrow">
                        {sortField === 'value' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </div>
                  </th>

                  <th
                    className="sortable text-right"
                    onClick={() => handleHeaderSort('value')}
                    title="Sort by Value"
                  >
                    <div className="th-content justify-end">
                      <span>System B Value</span>
                      <span className="sort-arrow">
                        {sortField === 'value' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </div>
                  </th>

                  <th
                    className="sortable text-right"
                    onClick={() => handleHeaderSort('difference')}
                    title="Sort by Difference"
                  >
                    <div className="th-content justify-end">
                      <span>Difference</span>
                      <span className="sort-arrow">
                        {sortField === 'difference' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
                      </span>
                    </div>
                  </th>

                  <th>Audit Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.map((row, idx) => {
                  const aFmt = formatCurrency(row.a_value)
                  const bFmt = formatCurrency(row.b_value)
                  const diffNum =
                    row.difference !== null && row.difference !== undefined
                      ? parseFloat(row.difference)
                      : null

                  const isExpanded = expandedRow === idx

                  return (
                    <React.Fragment key={`${row.record_id}-${row.reason}-${idx}`}>
                      <tr
                        className={`table-row ${isExpanded ? 'row-expanded' : ''}`}
                        onClick={() => setExpandedRow(isExpanded ? null : idx)}
                        title="Click to toggle transaction inspection"
                      >
                        <td>
                          <ReasonBadge reason={row.reason} />
                        </td>

                        <td>
                          <div className="record-id-wrapper">
                            <span className="mono record-id-text">
                              {row.record_id || <span className="empty-cell">—</span>}
                            </span>
                            {row.record_id && (
                              <button
                                type="button"
                                className="copy-btn"
                                onClick={(e) => copyToClipboard(row.record_id, e)}
                                title="Copy Record ID"
                              >
                                {copiedId === row.record_id ? '✓' : '📋'}
                              </button>
                            )}
                          </div>
                          {row.entry_id && (
                            <div className="entry-id-subtext">Entry: {row.entry_id}</div>
                          )}
                        </td>

                        <td>
                          <div className="locations-pair">
                            <span className="loc-badge loc-a">A: {row.a_location || '—'}</span>
                            {row.b_location && (
                              <span
                                className={`loc-badge ${
                                  row.b_location === '[EXTERNAL_LOCATION]'
                                    ? 'loc-redacted'
                                    : 'loc-b'
                                }`}
                                title={
                                  row.b_location === '[EXTERNAL_LOCATION]'
                                    ? 'Foreign branch code masked to preserve tenant safety'
                                    : ''
                                }
                              >
                                B: {row.b_location}
                              </span>
                            )}
                          </div>
                        </td>

                        <td>
                          <div className="dates-pair">
                            <span>A: {row.a_date || '—'}</span>
                            <span>B: {row.b_date || '—'}</span>
                          </div>
                        </td>

                        <td className="amount-cell text-right">
                          {aFmt !== null ? (
                            <span className="amount-val">${aFmt}</span>
                          ) : (
                            <span className="empty-cell">—</span>
                          )}
                        </td>

                        <td className="amount-cell text-right">
                          {bFmt !== null ? (
                            <span className="amount-val">${bFmt}</span>
                          ) : (
                            <span className="empty-cell">—</span>
                          )}
                        </td>

                        <td className="text-right">
                          {diffNum !== null ? (
                            <span
                              className={`diff-chip ${
                                diffNum < 0
                                  ? 'diff-negative'
                                  : diffNum > 0
                                  ? 'diff-positive'
                                  : 'diff-zero'
                              }`}
                            >
                              {diffNum > 0 ? '+ ' : diffNum < 0 ? '- ' : ''}$
                              {Math.abs(diffNum).toLocaleString('en-US', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2,
                              })}
                            </span>
                          ) : (
                            <span className="empty-cell">—</span>
                          )}
                        </td>

                        <td>
                          <div className="details-text-cell">
                            <span>{row.details}</span>
                            <span className="expand-indicator">{isExpanded ? '▲' : '▼'}</span>
                          </div>
                        </td>
                      </tr>

                      {/* Expandable Inspection Drawer */}
                      {isExpanded && (
                        <tr className="drawer-row">
                          <td colSpan={8}>
                            <div className="drawer-content">
                              <div className="drawer-grid">
                                <div className="drawer-col">
                                  <h4>System A Ledger State</h4>
                                  <p>
                                    <strong>Record ID:</strong> {row.record_id || 'N/A'}
                                  </p>
                                  <p>
                                    <strong>Location:</strong> {row.a_location || 'None'}
                                  </p>
                                  <p>
                                    <strong>Event Date:</strong> {row.a_date || 'None'}
                                  </p>
                                  <p>
                                    <strong>Total Claim:</strong>{' '}
                                    {aFmt ? `$${aFmt}` : 'No System A record'}
                                  </p>
                                </div>

                                <div className="drawer-col">
                                  <h4>System B Posting</h4>
                                  <p>
                                    <strong>Entry ID:</strong> {row.entry_id || 'N/A'}
                                  </p>
                                  <p>
                                    <strong>Location:</strong> {row.b_location || 'None'}
                                  </p>
                                  <p>
                                    <strong>Recorded Date:</strong> {row.b_date || 'None'}
                                  </p>
                                  <p>
                                    <strong>Settled Amount:</strong>{' '}
                                    {bFmt ? `$${bFmt}` : 'Empty / Blank'}
                                  </p>
                                </div>

                                <div className="drawer-col">
                                  <h4>Reconciliation Audit</h4>
                                  <p>
                                    <strong>Status:</strong> {REASON_CONFIG[row.reason]?.label}
                                  </p>
                                  <p>
                                    <strong>Difference:</strong>{' '}
                                    {diffNum !== null ? `$${diffNum.toFixed(2)}` : 'Indeterminate'}
                                  </p>
                                  <p className="drawer-note">
                                    <em>{row.details}</em>
                                  </p>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Footer Info */}
      <footer className="app-footer">
        <div>
          DealerOS Ledger Platform &bull; Built with Django REST Framework & Vite + React
        </div>
        <div>
          Showing <strong>{filteredResults.length}</strong> of{' '}
          <strong>{totalDiscrepancies}</strong> total discrepancies
        </div>
      </footer>
    </div>
  )
}
