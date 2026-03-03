import { useState, useEffect } from 'react'
import type { LibraryStats } from '../types'
import { getLibraryStats } from '../api'

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

const GRADE_ORDER = ['A', 'B', 'C', 'D', 'F']

const RISK_CONFIG = [
  { key: 'high',   label: 'High',   className: 'history-risk-high' },
  { key: 'medium', label: 'Medium', className: 'history-risk-medium' },
  { key: 'low',    label: 'Low',    className: 'history-risk-low' },
] as const

export default function History() {
  const [stats, setStats] = useState<LibraryStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getLibraryStats()
      .then(setStats)
      .catch(() => setError('Failed to load contract summary.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="history-loading">
        <div className="spinner" />
        <p>Loading contract summary…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="history-error">
        <p>{error}</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Retry</button>
      </div>
    )
  }

  if (!stats || stats.contracts_count === 0) {
    return (
      <div className="history-empty">
        <div className="history-empty-icon">📋</div>
        <h3>No contracts analyzed yet</h3>
        <p>Upload a PBM contract to begin building your analysis history.</p>
      </div>
    )
  }

  const totalRisk = (stats.risk_distribution?.high ?? 0)
    + (stats.risk_distribution?.medium ?? 0)
    + (stats.risk_distribution?.low ?? 0)

  return (
    <div className="history-page">

      {/* Hero banner */}
      <div className="history-hero">
        <div className="history-hero-count">{stats.contracts_count}</div>
        <div className="history-hero-text">
          <div className="history-hero-label">Contracts Analyzed</div>
          <div className="history-hero-sub">Aggregate insights across your contract library</div>
        </div>
      </div>

      {/* Row 1: Grade Distribution + Risk Profile */}
      <div className="history-section-label">Performance Overview</div>
      <div className="history-stats-grid">

        <div className="history-stat-card">
          <div className="history-stat-label">Grade Distribution</div>
          <div className="history-grade-dist">
            {GRADE_ORDER.map((g) => {
              const count = stats.grade_distribution[g] ?? 0
              const pct = Math.round((count / stats.contracts_count) * 100)
              const color = GRADE_COLORS[g]
              return (
                <div key={g} className="history-grade-row">
                  <span className="history-grade-letter" style={{ color, borderColor: color + '40', background: color + '12' }}>{g}</span>
                  <div className="history-grade-bar-wrap">
                    <div className="history-grade-bar" style={{ width: `${pct}%`, background: color + '60' }} />
                  </div>
                  <span className="history-grade-pct">{pct > 0 ? `${pct}%` : '—'}</span>
                  <span className="history-grade-count">{count}</span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="history-stat-card">
          <div className="history-stat-label">Risk Profile</div>
          <div className="history-risk-dist">
            {RISK_CONFIG.map(({ key, label, className }) => {
              const count = stats.risk_distribution?.[key] ?? 0
              const pct = totalRisk > 0 ? Math.round((count / totalRisk) * 100) : 0
              return (
                <div key={key} className="history-risk-row">
                  <span className={`history-risk-badge ${className}`}>{label}</span>
                  <div className="history-grade-bar-wrap">
                    <div className={`history-grade-bar history-risk-bar-${key}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="history-grade-pct">{pct > 0 ? `${pct}%` : '—'}</span>
                  <span className="history-grade-count">{count}</span>
                </div>
              )
            })}
            <div className="history-risk-total">
              Based on {stats.contracts_count} contract{stats.contracts_count !== 1 ? 's' : ''} by grade
            </div>
          </div>
        </div>

      </div>

      {/* Row 2: AWP Discounts + Rebates & Fees */}
      <div className="history-section-label">Pricing Benchmarks</div>
      <div className="history-stats-grid">

        <div className="history-stat-card">
          <div className="history-stat-label">Avg AWP Discounts</div>
          <div className="history-pricing-list">
            <div className="history-pricing-row">
              <span className="history-pricing-term">Brand Retail</span>
              <span className="history-pricing-val">{stats.avg_brand_retail}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Brand Mail</span>
              <span className="history-pricing-val">{stats.avg_brand_mail ?? 'N/A'}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Generic Retail</span>
              <span className="history-pricing-val">{stats.avg_generic_retail}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Generic Mail</span>
              <span className="history-pricing-val">{stats.avg_generic_mail ?? 'N/A'}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Specialty</span>
              <span className="history-pricing-val">{stats.avg_specialty}</span>
            </div>
          </div>
        </div>

        <div className="history-stat-card">
          <div className="history-stat-label">Avg Rebates &amp; Fees</div>
          <div className="history-pricing-list">
            <div className="history-pricing-row">
              <span className="history-pricing-term">Rebate Guarantee</span>
              <span className="history-pricing-val">{stats.avg_rebate_guarantee}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Dispensing Fee</span>
              <span className="history-pricing-val">{stats.avg_dispensing_fee}</span>
            </div>
            <div className="history-pricing-row">
              <span className="history-pricing-term">Admin Fee</span>
              <span className="history-pricing-val">{stats.avg_admin_fee}</span>
            </div>
          </div>
        </div>

      </div>

      {/* Row 3: Top Concerns + Top High-Risk Areas */}
      <div className="history-section-label">Key Findings</div>
      <div className="history-stats-grid">

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

        <div className="history-stat-card">
          <div className="history-stat-label">Top High-Risk Areas</div>
          <div className="history-concern-list">
            {(stats.top_risk_areas ?? []).length > 0
              ? stats.top_risk_areas.map(([area, count], i) => (
                  <div key={i} className="history-concern-stat-row">
                    <span className="history-concern-chip history-concern-chip--risk">{area}</span>
                    <span className="history-concern-freq">{count}×</span>
                  </div>
                ))
              : <span className="history-unknown">No risk area data yet</span>}
          </div>
        </div>

      </div>

    </div>
  )
}
