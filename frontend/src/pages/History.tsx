import { useState, useEffect } from 'react'
import type { ContractListItem, StoredAnalysisResponse, AnalysisReport } from '../types'
import { getContractLibrary, getStoredAnalysis } from '../api'

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

interface Props {
  onOpenReport: (sessionId: string, analysis: AnalysisReport, downloadUrl: string | null) => void
  onCompare: (sessionId: string) => void
}

export default function History({ onOpenReport, onCompare }: Props) {
  const [contracts, setContracts] = useState<ContractListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [openingId, setOpeningId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getContractLibrary(page)
      .then((data) => {
        setContracts(data.contracts)
        setTotal(data.total)
        setPages(data.pages)
      })
      .catch(() => setError('Failed to load contract history.'))
      .finally(() => setLoading(false))
  }, [page])

  const handleOpenReport = async (sessionId: string) => {
    setOpeningId(sessionId)
    try {
      const data: StoredAnalysisResponse = await getStoredAnalysis(sessionId)
      onOpenReport(sessionId, data.analysis, data.download_url)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      alert(`Could not load report: ${msg}`)
    } finally {
      setOpeningId(null)
    }
  }

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

      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th>Contract</th>
              <th>Analyzed</th>
              <th>Grade</th>
              <th>Top Concerns</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c, rowIndex) => {
              const contractNumber = total - ((page - 1) * 20) - rowIndex
              const gradeColor = GRADE_COLORS[c.overall_grade] ?? '#64748b'
              const isOpening = openingId === c.session_id
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
                  <td className="history-concerns">
                    {c.key_concerns.length > 0
                      ? c.key_concerns.slice(0, 2).map((concern, i) => (
                          <div key={i} className="history-concern-chip">{concern}</div>
                        ))
                      : <span className="history-unknown">—</span>}
                  </td>
                  <td className="history-actions">
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={() => handleOpenReport(c.session_id)}
                      disabled={isOpening}
                    >
                      {isOpening ? 'Loading…' : 'View Report'}
                    </button>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => onCompare(c.session_id)}
                    >
                      Compare
                    </button>
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
