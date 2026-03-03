import { useState, useEffect } from 'react'
import type { ContractListItem, LibraryStats } from '../types'
import { getContractLibrary, getLibraryStats } from '../api'

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

const GRADE_ORDER = ['A', 'B', 'C', 'D', 'F']

export default function History() {
  const [contracts, setContracts] = useState<ContractListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<LibraryStats | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      getContractLibrary(page),
      page === 1 ? getLibraryStats() : Promise.resolve(null),
    ])
      .then(([listData, statsData]) => {
        setContracts(listData.contracts)
        setTotal(listData.total)
        setPages(listData.pages)
        if (statsData) setStats(statsData)
      })
      .catch(() => setError('Failed to load contract history.'))
      .finally(() => setLoading(false))
  }, [page])

  if (loading) {
    return (
      <div className="history-loading">
        <div className="spinner" />
        <p>Loading contract history…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="history-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => setPage(1)}>Retry</button>
      </div>
    )
  }

  if (contracts.length === 0) {
    return (
      <div className="history-empty">
        <div className="history-empty-icon">📋</div>
        <h3>No contracts analyzed yet</h3>
        <p>Upload a PBM contract to begin building your analysis history.</p>
      </div>
    )
  }

  return (
    <div className="history-page">
      <div className="history-header">
        <div>
          <h2 className="history-title">Contract History</h2>
          <p className="history-subtitle">
            {total} contract{total !== 1 ? 's' : ''} analyzed
          </p>
        </div>
      </div>

      {/* Aggregate summary */}
      {stats && stats.contracts_count > 0 && (
        <div className="history-stats-grid">

          {/* Grade distribution */}
          <div className="history-stat-card">
            <div className="history-stat-label">Grade Distribution</div>
            <div className="history-grade-dist">
              {GRADE_ORDER.map((g) => {
                const count = stats.grade_distribution[g] ?? 0
                const pct = stats.contracts_count > 0
                  ? Math.round((count / stats.contracts_count) * 100)
                  : 0
                const color = GRADE_COLORS[g]
                return (
                  <div key={g} className="history-grade-row">
                    <span className="history-grade-letter" style={{ color, borderColor: color + '40', background: color + '12' }}>{g}</span>
                    <div className="history-grade-bar-wrap">
                      <div
                        className="history-grade-bar"
                        style={{ width: `${pct}%`, background: color + '60' }}
                      />
                    </div>
                    <span className="history-grade-count">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Average pricing */}
          <div className="history-stat-card">
            <div className="history-stat-label">Average Pricing (AWP Discounts)</div>
            <div className="history-pricing-list">
              <div className="history-pricing-row">
                <span className="history-pricing-term">Brand Retail</span>
                <span className="history-pricing-val">{stats.avg_brand_retail}</span>
              </div>
              <div className="history-pricing-row">
                <span className="history-pricing-term">Generic Retail</span>
                <span className="history-pricing-val">{stats.avg_generic_retail}</span>
              </div>
              <div className="history-pricing-row">
                <span className="history-pricing-term">Specialty</span>
                <span className="history-pricing-val">{stats.avg_specialty}</span>
              </div>
            </div>
          </div>

          {/* Most common concerns */}
          <div className="history-stat-card">
            <div className="history-stat-label">Most Common Concerns</div>
            <div className="history-concern-list">
              {stats.top_concerns.length > 0
                ? stats.top_concerns.map(([concern, count], i) => (
                    <div key={i} className="history-concern-stat-row">
                      <span className="history-concern-chip">{concern}</span>
                      <span className="history-concern-freq">{count}×</span>
                    </div>
                  ))
                : <span className="history-unknown">No concern data yet</span>}
            </div>
          </div>

        </div>
      )}

      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th>Contract</th>
              <th>Analyzed</th>
              <th>Grade</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c, rowIndex) => {
              const contractNumber = total - ((page - 1) * 20) - rowIndex
              const gradeColor = GRADE_COLORS[c.overall_grade] ?? '#64748b'
              return (
                <tr key={c.session_id}>
                  <td className="history-pbm-name">
                    Contract #{contractNumber}
                  </td>
                  <td className="history-date">
                    {c.uploaded_at
                      ? new Date(c.uploaded_at + 'Z').toLocaleDateString('en-US', {
                          month: 'short', day: 'numeric', year: 'numeric',
                        })
                      : '—'}
                  </td>
                  <td>
                    <span
                      className="history-grade"
                      style={{ color: gradeColor, borderColor: gradeColor + '40', background: gradeColor + '12' }}
                    >
                      {c.overall_grade}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="history-pagination">
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            ← Prev
          </button>
          <span className="history-page-info">
            Page {page} of {pages}
          </span>
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
