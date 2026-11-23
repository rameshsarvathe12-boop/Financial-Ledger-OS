import React, { useState, useEffect, useMemo } from 'react'
import './App.css'

const API_BASE = '/api'

const REASON_LABELS = {
  VALUE_MISMATCH: 'Value Mismatch',
  MISSING_IN_B: 'Missing in System B',
  ORPHAN_IN_B: 'Orphan in System B',
  DUPLICATE_IN_B: 'Duplicate in System B',
  LOCATION_MISMATCH: 'Location Mismatch',
  DATE_MISMATCH: 'Date Mismatch',
  VOIDED_RECORD_HAS_ENTRY: 'Voided with Entry',
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
  let badgeClass = 'badge-value-mismatch'
  if (reason === 'MISSING_IN_B') badgeClass = 'badge-missing'
  else if (reason === 'ORPHAN_IN_B') badgeClass = 'badge-orphan'
  else if (reason === 'DUPLICATE_IN_B') badgeClass = 'badge-duplicate'
  else if (reason === 'LOCATION_MISMATCH') badgeClass = 'badge-location'
  else if (reason === 'DATE_MISMATCH') badgeClass = 'badge-date'
  else if (reason === 'VOIDED_RECORD_HAS_ENTRY') badgeClass = 'badge-voided'

  return (
    <span className={`badge ${badgeClass}`}>
      {REASON_LABELS[reason] || reason}
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

  const [data, setData] = useState({
    org: 'ORG-A',
    total_count: 0,
    reason_summary: {},
    results: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch available orgs on mount
  useEffect(() => {
    fetch(`${API_BASE}/orgs/`)
      .then((res) => (res.ok ? res.json() : Promise.reject('Failed to fetch orgs')))
      .then((data) => {
        if (data.orgs && data.orgs.length > 0) {
          const list = data.orgs.map((o) => o.org_id)
          setOrgsList(list)
          if (!list.includes(selectedOrg)) {
            setSelectedOrg(list[0])
          }
        }
      })
      .catch((err) => {
        console.warn('Could not load orgs list, using defaults:', err)
      })
  }, [])

  // Fetch disagreements when org, reason, or sort changes
  useEffect(() => {
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
        setError(typeof err === 'string' ? err : 'Unable to load reconciliation data')
        setLoading(false)
      })
  }, [selectedOrg, selectedReason, sortField, sortDirection])

  const handleHeaderSort = (field) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  // Filter client-side search query (Record ID, entry ID, location)
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

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">D</div>
          <div className="brand-text">
            <h1>DealerOS Dual-Ledger Reconciliation</h1>
            <p>Disagreement detection across System A and System B with strict tenant boundaries</p>
          </div>
        </div>

        <div className="tenant-selector-box">
          <label htmlFor="tenant-select">Tenant Org:</label>
          <select
            id="tenant-select"
            className="tenant-select"
            value={selectedOrg}
            onChange={(e) => {
              setSelectedOrg(e.target.value)
              setSelectedReason('')
            }}
          >
            {orgsList.map((org) => (
              <option key={org} value={org}>
                {org}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Tenant Boundary Notice */}
      <div className="tenant-notice">
        <div>
          Active Tenant Scope: <strong>{selectedOrg}</strong> &bull; Showing only records
          belonging to <strong>{selectedOrg}</strong>. Cross-tenant records and locations are
          isolated at the database level.
        </div>
        <div className="mono">Tenant Isolated &bull; Safe Mode</div>
      </div>

      {/* Metric Cards */}
      <div className="metrics-grid">
        <div
          className={`metric-card ${selectedReason === '' ? 'active' : ''}`}
          onClick={() => setSelectedReason('')}
        >
          <div className="metric-title">Total Discrepancies</div>
          <div className="metric-value">
            {Object.values(data.reason_summary || {}).reduce((a, b) => a + b, 0)}
          </div>
        </div>

        {Object.entries(data.reason_summary || {}).map(([reason, count]) => (
          <div
            key={reason}
            className={`metric-card ${selectedReason === reason ? 'active' : ''}`}
            onClick={() => setSelectedReason((prev) => (prev === reason ? '' : reason))}
          >
            <div className="metric-title">{REASON_LABELS[reason] || reason}</div>
            <div className="metric-value">{count}</div>
          </div>
        ))}
      </div>

      {/* Controls Bar */}
      <div className="controls-card">
        <div className="filter-group">
          <div className="control-item">
            <label htmlFor="reason-filter">Filter Reason:</label>
            <select
              id="reason-filter"
              className="custom-select"
              value={selectedReason}
              onChange={(e) => setSelectedReason(e.target.value)}
            >
              <option value="">All Discrepancy Reasons</option>
              <option value="VALUE_MISMATCH">Value Mismatch</option>
              <option value="MISSING_IN_B">Missing in System B</option>
              <option value="ORPHAN_IN_B">Orphan in System B</option>
              <option value="DUPLICATE_IN_B">Duplicate in System B</option>
              <option value="LOCATION_MISMATCH">Location Mismatch</option>
              <option value="DATE_MISMATCH">Date Mismatch</option>
              <option value="VOIDED_RECORD_HAS_ENTRY">Voided with Active Entry</option>
            </select>
          </div>

          <div className="control-item">
            <label htmlFor="sort-select">Sort By:</label>
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

        <div className="filter-group">
          <input
            type="text"
            className="search-input"
            placeholder="Search record, entry, loc..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* Table Card */}
      <div className="table-card">
        {loading ? (
          <div className="state-container">
            <div className="state-title">Loading Discrepancies...</div>
            <div className="state-desc">Reconciling System A and System B ledgers for {selectedOrg}</div>
          </div>
        ) : error ? (
          <div className="state-container">
            <div className="state-title" style={{ color: '#dc2626' }}>
              Error Loading Data
            </div>
            <div className="state-desc">{error}</div>
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="state-container">
            <div className="state-title">No Disagreements Found</div>
            <div className="state-desc">
              {selectedReason
                ? `No rows matched the filter '${REASON_LABELS[selectedReason] || selectedReason}' for ${selectedOrg}.`
                : `Both systems agree completely for ${selectedOrg} on all checked records.`}
            </div>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="reconcile-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    onClick={() => handleHeaderSort('reason')}
                    title="Click to sort by reason"
                  >
                    Reason {sortField === 'reason' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th
                    className="sortable"
                    onClick={() => handleHeaderSort('record_id')}
                    title="Click to sort by record ID"
                  >
                    Record ID {sortField === 'record_id' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th>Location (A / B)</th>
                  <th>Dates (Event / Recorded)</th>
                  <th
                    className="sortable"
                    style={{ textAlign: 'right' }}
                    onClick={() => handleHeaderSort('value')}
                    title="Click to sort by value"
                  >
                    System A Total {sortField === 'value' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th
                    className="sortable"
                    style={{ textAlign: 'right' }}
                    onClick={() => handleHeaderSort('value')}
                    title="Click to sort by value"
                  >
                    System B Value {sortField === 'value' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th
                    className="sortable"
                    style={{ textAlign: 'right' }}
                    onClick={() => handleHeaderSort('difference')}
                    title="Click to sort by difference"
                  >
                    Difference {sortField === 'difference' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th>Details</th>
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

                  return (
                    <tr key={`${row.record_id}-${row.reason}-${idx}`}>
                      <td>
                        <ReasonBadge reason={row.reason} />
                      </td>
                      <td className="mono" style={{ fontWeight: 600 }}>
                        {row.record_id || <span className="empty-cell">—</span>}
                        {row.entry_id && (
                          <div
                            style={{
                              fontSize: '11px',
                              color: 'var(--text-muted)',
                              fontWeight: 400,
                            }}
                          >
                            Ref: {row.entry_id}
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <span className="location-tag">A: {row.a_location || '—'}</span>
                          {row.b_location && (
                            <span
                              className={`location-tag ${
                                row.b_location === '[EXTERNAL_LOCATION]'
                                  ? 'location-redacted'
                                  : ''
                              }`}
                            >
                              B: {row.b_location}
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        <div>A: {row.a_date || '—'}</div>
                        <div>B: {row.b_date || '—'}</div>
                      </td>
                      <td className="amount-cell" style={{ textAlign: 'right' }}>
                        {aFmt !== null ? `$${aFmt}` : <span className="empty-cell">—</span>}
                      </td>
                      <td className="amount-cell" style={{ textAlign: 'right' }}>
                        {bFmt !== null ? `$${bFmt}` : <span className="empty-cell">—</span>}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {diffNum !== null ? (
                          <span
                            className={`diff-tag ${
                              diffNum < 0
                                ? 'diff-negative'
                                : diffNum > 0
                                ? 'diff-positive'
                                : 'diff-zero'
                            }`}
                          >
                            {diffNum > 0 ? '+' : ''}
                            ${diffNum.toLocaleString('en-US', {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </span>
                        ) : (
                          <span className="empty-cell">—</span>
                        )}
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '280px' }}>
                        {row.details}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
