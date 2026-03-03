import type { RevisionCompareData, PricingDelta } from '../types'

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

const GRADE_LABELS: Record<string, string> = {
  A: 'Excellent', B: 'Good', C: 'Average', D: 'Below Market', F: 'Unfavorable',
}

function GradePill({ grade }: { grade: string }) {
  const color = GRADE_COLORS[grade] ?? '#64748b'
  return (
    <span
      className="revision-grade-pill"
      style={{ color, borderColor: color + '50', background: color + '14' }}
    >
      {grade}
    </span>
  )
}

function DeltaCell({ delta }: { delta: PricingDelta }) {
  const { improved } = delta
  if (delta.delta === 'no change') {
    return <td className="delta-cell delta-neutral"><span className="delta-tag delta-unchanged">= No change</span></td>
  }
  if (delta.delta === 'changed' || improved === null) {
    return <td className="delta-cell delta-neutral"><span className="delta-tag delta-changed">{delta.delta}</span></td>
  }
  return (
    <td className={`delta-cell ${improved ? 'delta-good' : 'delta-bad'}`}>
      <span className={`delta-tag ${improved ? 'delta-improved' : 'delta-regressed'}`}>
        {delta.delta}
      </span>
    </td>
  )
}

interface Props {
  data: RevisionCompareData
  onBack: () => void
}

export default function RevisionCompareView({ data, onBack }: Props) {
  const { grade_change, pricing_deltas, concerns_resolved, concerns_new, concerns_remaining } = data
  const { from_grade, to_grade, improved, regressed } = grade_change

  const fromColor = GRADE_COLORS[from_grade] ?? '#64748b'
  const toColor   = GRADE_COLORS[to_grade]   ?? '#64748b'

  const overallOutcome = improved ? 'improved' : regressed ? 'regressed' : 'unchanged'

  const outcomeConfig = {
    improved:  { bg: '#f0fdf4', border: '#86efac', text: '#15803d', label: 'Contract Improved' },
    regressed: { bg: '#fef2f2', border: '#fca5a5', text: '#dc2626', label: 'Contract Regressed' },
    unchanged: { bg: '#f8fafc', border: '#e2e8f0', text: '#64748b', label: 'No Overall Change' },
  }[overallOutcome]

  return (
    <div className="revision-view">
      {/* Back + title */}
      <div className="revision-header">
        <button className="btn btn-sm btn-secondary" onClick={onBack}>
          ← Back to Report
        </button>
        <div>
          <h2 className="revision-title">Before &amp; After: Negotiation Impact</h2>
          <p className="revision-subtitle">
            Comparing original contract against the renegotiated version
          </p>
        </div>
      </div>

      {/* Outcome summary banner */}
      <div
        className="revision-outcome-banner"
        style={{ background: outcomeConfig.bg, borderColor: outcomeConfig.border }}
      >
        {/* Grade change */}
        <div className="revision-grade-change">
          <div className="revision-grade-block">
            <div className="revision-grade-letter" style={{ color: fromColor }}>
              {from_grade}
            </div>
            <div className="revision-grade-label" style={{ color: fromColor }}>
              {GRADE_LABELS[from_grade]}
            </div>
            <div className="revision-grade-sub">Original</div>
          </div>

          <div className="revision-arrow" style={{ color: outcomeConfig.text }}>
            {improved ? '→' : regressed ? '→' : '→'}
          </div>

          <div className="revision-grade-block">
            <div className="revision-grade-letter" style={{ color: toColor }}>
              {to_grade}
            </div>
            <div className="revision-grade-label" style={{ color: toColor }}>
              {GRADE_LABELS[to_grade]}
            </div>
            <div className="revision-grade-sub">Revised</div>
          </div>
        </div>

        {/* Stats */}
        <div className="revision-stats">
          <div className="revision-stat">
            <span className="revision-stat-num revision-stat-good">{data.improvements_count}</span>
            <span className="revision-stat-label">Terms Improved</span>
          </div>
          <div className="revision-stat">
            <span className="revision-stat-num revision-stat-bad">{data.regressions_count}</span>
            <span className="revision-stat-label">Terms Regressed</span>
          </div>
          <div className="revision-stat">
            <span className="revision-stat-num revision-stat-neutral">{concerns_resolved.length}</span>
            <span className="revision-stat-label">Concerns Resolved</span>
          </div>
          <div className="revision-stat">
            <span className="revision-stat-num revision-stat-bad">{concerns_new.length}</span>
            <span className="revision-stat-label">New Concerns</span>
          </div>
        </div>

        <div
          className="revision-outcome-label"
          style={{ color: outcomeConfig.text }}
        >
          {outcomeConfig.label}
        </div>
      </div>

      {/* Pricing terms delta table */}
      <div className="revision-section">
        <h3 className="revision-section-title">Pricing Term Changes</h3>
        <div className="revision-table-wrap">
          <table className="revision-table">
            <thead>
              <tr>
                <th>Pricing Term</th>
                <th>Original Contract</th>
                <th>Revised Contract</th>
                <th>Change</th>
              </tr>
            </thead>
            <tbody>
              {pricing_deltas.map((d) => (
                <tr
                  key={d.term}
                  className={
                    d.improved === true
                      ? 'revision-row-improved'
                      : d.improved === false
                        ? 'revision-row-regressed'
                        : ''
                  }
                >
                  <td className="revision-term-label">{d.term}</td>
                  <td className="revision-orig-val">{d.original_val}</td>
                  <td className="revision-rev-val"><strong>{d.revised_val}</strong></td>
                  <DeltaCell delta={d} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Key concerns analysis */}
      <div className="revision-section">
        <h3 className="revision-section-title">Key Concerns Analysis</h3>
        <div className="revision-concerns-grid">

          {concerns_resolved.length > 0 && (
            <div className="revision-concerns-card revision-concerns-resolved">
              <div className="revision-concerns-card-header">
                <span className="revision-concerns-icon">✓</span>
                <span>Resolved ({concerns_resolved.length})</span>
              </div>
              <ul>
                {concerns_resolved.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {concerns_remaining.length > 0 && (
            <div className="revision-concerns-card revision-concerns-remaining">
              <div className="revision-concerns-card-header">
                <span className="revision-concerns-icon">⚠</span>
                <span>Still Present ({concerns_remaining.length})</span>
              </div>
              <ul>
                {concerns_remaining.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {concerns_new.length > 0 && (
            <div className="revision-concerns-card revision-concerns-new">
              <div className="revision-concerns-card-header">
                <span className="revision-concerns-icon">!</span>
                <span>New in Revised Contract ({concerns_new.length})</span>
              </div>
              <ul>
                {concerns_new.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {concerns_resolved.length === 0 && concerns_new.length === 0 && concerns_remaining.length === 0 && (
            <p className="revision-no-concerns">No key concerns to compare.</p>
          )}
        </div>
      </div>

      {/* Contract identifiers */}
      <div className="revision-footer-note">
        <span>
          Original: <GradePill grade={from_grade} /> {data.original.pbm_name}
          {data.original.uploaded_at && (
            <> · {new Date(data.original.uploaded_at + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</>
          )}
        </span>
        <span className="revision-footer-sep">vs.</span>
        <span>
          Revised: <GradePill grade={to_grade} /> {data.revised.pbm_name}
          {data.revised.uploaded_at && (
            <> · {new Date(data.revised.uploaded_at + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</>
          )}
        </span>
      </div>
    </div>
  )
}
