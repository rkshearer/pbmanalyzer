import { useState, useEffect } from 'react'
import type { CompareData, CompareContract, ContractListItem } from '../types'
import { getCompareData, getContractLibrary } from '../api'

const GRADE_ORDER: Record<string, number> = { A: 4, B: 3, C: 2, D: 1, F: 0 }
const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

function gradeWinner(a: string, b: string): 'a' | 'b' | 'tie' {
  const oa = GRADE_ORDER[a] ?? 2
  const ob = GRADE_ORDER[b] ?? 2
  return oa > ob ? 'a' : ob > oa ? 'b' : 'tie'
}

/** Extract the first percentage number found in a string, for numeric comparison. */
function extractPct(s: string): number | null {
  const m = s.match(/(\d+(?:\.\d+)?)\s*%/)
  return m ? parseFloat(m[1]) : null
}

type HigherBetter = 'higher' | 'lower'

function numericWinner(
  a: string,
  b: string,
  pref: HigherBetter = 'higher',
): 'a' | 'b' | 'tie' {
  const pa = extractPct(a)
  const pb = extractPct(b)
  if (pa === null || pb === null) return 'tie'
  if (pref === 'higher') return pa > pb ? 'a' : pb > pa ? 'b' : 'tie'
  return pa < pb ? 'a' : pb < pa ? 'b' : 'tie'
}

function WinnerBadge({ side, winner }: { side: 'a' | 'b'; winner: 'a' | 'b' | 'tie' }) {
  if (winner === 'tie') return null
  if (winner !== side) return null
  return <span className="compare-winner-badge">✓ Better</span>
}

function CompareCell({
  value,
  side,
  winner,
}: {
  value: string
  side: 'a' | 'b'
  winner: 'a' | 'b' | 'tie'
}) {
  const isWinner = winner === side
  const isLoser  = winner !== 'tie' && winner !== side
  return (
    <td className={`compare-cell ${isWinner ? 'compare-winner' : isLoser ? 'compare-loser' : ''}`}>
      <strong>{value}</strong>
      <WinnerBadge side={side} winner={winner} />
    </td>
  )
}

const COMPARE_ROWS: Array<{
  label: string
  key: keyof CompareContract
  pref?: HigherBetter
  useGrade?: boolean
}> = [
  { label: 'Overall Grade',          key: 'overall_grade',        useGrade: true },
  { label: 'Brand Retail AWP',        key: 'brand_retail',         pref: 'higher' },
  { label: 'Generic Retail AWP',      key: 'generic_retail',       pref: 'higher' },
  { label: 'Specialty AWP',           key: 'specialty',            pref: 'higher' },
  { label: 'Retail Dispensing Fee',   key: 'retail_dispensing_fee',pref: 'lower'  },
  { label: 'Admin Fees',              key: 'admin_fees',           pref: 'lower'  },
  { label: 'Rebate Guarantee',        key: 'rebate_guarantee',     pref: 'higher' },
]

interface Props {
  sessionIdA: string
  onBack: () => void
}

export default function CompareView({ sessionIdA, onBack }: Props) {
  const [library, setLibrary] = useState<ContractListItem[]>([])
  const [sessionIdB, setSessionIdB] = useState<string>('')
  const [compareData, setCompareData] = useState<CompareData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getContractLibrary(1, 100)
      .then((data) => {
        setLibrary(data.contracts.filter((c) => c.session_id !== sessionIdA))
      })
      .catch(() => {/* ignore */})
  }, [sessionIdA])

  useEffect(() => {
    if (!sessionIdB) return
    setLoading(true)
    setError(null)
    setCompareData(null)
    getCompareData(sessionIdA, sessionIdB)
      .then(setCompareData)
      .catch(() => setError('Failed to load comparison data.'))
      .finally(() => setLoading(false))
  }, [sessionIdA, sessionIdB])

  const ca = compareData?.a
  const cb = compareData?.b

  return (
    <div className="compare-view">
      <div className="compare-header">
        <button className="btn btn-sm btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <h2 className="compare-title">Side-by-Side Contract Comparison</h2>
      </div>

      <div className="compare-selector">
        <label className="compare-selector-label">
          Compare against:
          <select
            className="compare-select"
            value={sessionIdB}
            onChange={(e) => setSessionIdB(e.target.value)}
          >
            <option value="">— Select a contract from your library —</option>
            {library.map((c) => (
              <option key={c.session_id} value={c.session_id}>
                {c.pbm_name || 'Unknown PBM'} · Grade {c.overall_grade} ·{' '}
                {c.uploaded_at
                  ? new Date(c.uploaded_at + 'Z').toLocaleDateString('en-US', {
                      month: 'short', day: 'numeric', year: 'numeric',
                    })
                  : ''}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && (
        <div className="compare-loading">
          <div className="spinner" />
          <p>Loading comparison…</p>
        </div>
      )}

      {error && <div className="compare-error">{error}</div>}

      {compareData && ca && cb && (
        <>
          {/* Header row */}
          <div className="compare-names">
            <div className="compare-label-col" />
            <div className="compare-contract-header">
              <div
                className="compare-grade-circle"
                style={{ color: GRADE_COLORS[ca.overall_grade] ?? '#64748b', borderColor: GRADE_COLORS[ca.overall_grade] ?? '#64748b' }}
              >
                {ca.overall_grade}
              </div>
              <div className="compare-contract-name">{ca.pbm_name}</div>
              <div className="compare-contract-date">
                {ca.uploaded_at
                  ? new Date(ca.uploaded_at + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                  : ''}
              </div>
            </div>
            <div className="compare-contract-header">
              <div
                className="compare-grade-circle"
                style={{ color: GRADE_COLORS[cb.overall_grade] ?? '#64748b', borderColor: GRADE_COLORS[cb.overall_grade] ?? '#64748b' }}
              >
                {cb.overall_grade}
              </div>
              <div className="compare-contract-name">{cb.pbm_name}</div>
              <div className="compare-contract-date">
                {cb.uploaded_at
                  ? new Date(cb.uploaded_at + 'Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                  : ''}
              </div>
            </div>
          </div>

          {/* Comparison table */}
          <table className="compare-table">
            <tbody>
              {COMPARE_ROWS.map(({ label, key, pref, useGrade }) => {
                const va = String(ca[key] ?? 'N/A')
                const vb = String(cb[key] ?? 'N/A')
                const winner = useGrade
                  ? gradeWinner(va, vb)
                  : numericWinner(va, vb, pref ?? 'higher')
                return (
                  <tr key={key}>
                    <td className="compare-row-label">{label}</td>
                    <CompareCell value={va} side="a" winner={winner} />
                    <CompareCell value={vb} side="b" winner={winner} />
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Key Concerns */}
          <div className="compare-concerns-section">
            <h3 className="compare-concerns-title">Key Concerns</h3>
            <div className="compare-concerns-grid">
              <div className="compare-concerns-col">
                <h4>{ca.pbm_name}</h4>
                {ca.key_concerns.length > 0 ? (
                  <ul>
                    {ca.key_concerns.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                ) : (
                  <p className="compare-no-concerns">None identified</p>
                )}
              </div>
              <div className="compare-concerns-col">
                <h4>{cb.pbm_name}</h4>
                {cb.key_concerns.length > 0 ? (
                  <ul>
                    {cb.key_concerns.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                ) : (
                  <p className="compare-no-concerns">None identified</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {!sessionIdB && !loading && (
        <div className="compare-placeholder">
          <p>Select a contract from your library above to begin the comparison.</p>
        </div>
      )}
    </div>
  )
}
