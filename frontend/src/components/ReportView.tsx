import { useState, useRef, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { AnalysisReport, CostRiskItem, LibraryComparison, ChatMessage, SavingsItem } from '../types'
import { API_BASE_URL, downloadNegotiationLetter, downloadRfpExport, getStoredToken } from '../api'

interface Props {
  analysis: AnalysisReport
  downloadUrl: string | null
  sessionId: string
  onCompare: (sessionId: string) => void
  onStartRevision: (sessionId: string) => void
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32', B: '#1565c0', C: '#f57c00', D: '#e64a19', F: '#c62828',
}

const GRADE_LABELS: Record<string, string> = {
  A: 'Excellent — Top of Market',
  B: 'Good — Above Average Terms',
  C: 'Average — Market Rate',
  D: 'Below Market — Needs Improvement',
  F: 'Unfavorable — Significant Concerns',
}

const SAVINGS_CATEGORY_COLORS: Record<string, { bg: string; accent: string; pill: string }> = {
  'Biosimilar Opportunity':  { bg: '#dcfce7', accent: '#16a34a', pill: '#bbf7d0' },
  'New Generic Available':   { bg: '#dbeafe', accent: '#1d4ed8', pill: '#bfdbfe' },
  'Alternative Pharmacy':    { bg: '#f3e8ff', accent: '#7c3aed', pill: '#e9d5ff' },
  'Coupon/Accumulator':      { bg: '#ffedd5', accent: '#ea580c', pill: '#fed7aa' },
  'Formulary Optimization':  { bg: '#ccfbf1', accent: '#0d9488', pill: '#99f6e4' },
}

const SAVINGS_IMPACT_COLORS: Record<string, { bg: string; color: string }> = {
  High:   { bg: '#fee2e2', color: '#b91c1c' },
  Medium: { bg: '#ffedd5', color: '#c2410c' },
  Low:    { bg: '#dbeafe', color: '#1d4ed8' },
}

interface GlossaryEntry {
  term: string
  definition: string
  example?: string
}

function getAssessmentClass(assessment: string): string {
  const lower = assessment.toLowerCase()
  if (lower.includes('favorable') && !lower.includes('un')) return 'assess-favorable'
  if (lower.includes('at market')) return 'assess-market'
  if (lower.includes('below market')) return 'assess-below'
  if (lower.includes('unfavorable')) return 'assess-unfavorable'
  return 'assess-market'
}

function RiskBadge({ level }: { level: string }) {
  return <span className={`risk-badge risk-${level.toLowerCase()}`}>{level.toUpperCase()}</span>
}

function SectionCard({ num, title, children }: { num: string; title: string; children: ReactNode }) {
  return (
    <section className="report-section-card">
      <div className="section-inner">
        <p className="section-num">{num}</p>
        <h2 className="section-title">{title}</h2>
        <div className="section-divider" />
        {children}
      </div>
    </section>
  )
}

function LibraryComparisonCard({ lc }: { lc: LibraryComparison }) {
  const rows: [string, string, string][] = [
    ['Brand Retail AWP Discount', lc.this_brand_retail, lc.avg_brand_retail],
    ['Generic Retail AWP Discount', lc.this_generic_retail, lc.avg_generic_retail],
    ['Specialty AWP Discount', lc.this_specialty, lc.avg_specialty],
  ]
  const gradeOrder: Record<string, string[]> = {
    A: ['#2e7d32', 'var(--success-bg)', 'var(--success-border)'],
    B: ['#1565c0', 'var(--primary-pale)', '#bfdbfe'],
    C: ['#f57c00', 'var(--warning-bg)', 'var(--warning-border)'],
    D: ['#e64a19', '#fff3ed', '#fdba74'],
    F: ['#c62828', 'var(--danger-bg)', 'var(--danger-border)'],
  }
  const isTop = lc.grade_percentile.startsWith('top')
  const [pctColor, pctBg, pctBorder] = isTop
    ? ['#2e7d32', 'var(--success-bg)', 'var(--success-border)']
    : ['#c62828', 'var(--danger-bg)', 'var(--danger-border)']

  const gradeEntries = Object.entries(lc.grade_distribution).filter(([, v]) => v > 0)

  return (
    <div className="library-comparison">
      <div className="library-meta">
        <span className="library-count">
          Benchmarked against <strong>{lc.contracts_in_library}</strong> contracts in our database
        </span>
        <span
          className="library-percentile"
          style={{ color: pctColor, background: pctBg, borderColor: pctBorder }}
        >
          {lc.grade_percentile}
        </span>
      </div>

      <div className="library-grade-dist">
        {gradeEntries.map(([grade, count]) => {
          const [color, bg, border] = gradeOrder[grade] ?? ['#64748b', '#f8fafc', '#e2e8f0']
          return (
            <span key={grade} className="grade-dist-pill" style={{ color, background: bg, borderColor: border }}>
              {grade}: {count}
            </span>
          )
        })}
      </div>

      <table className="data-table pricing-table library-table">
        <thead>
          <tr>
            <th>Pricing Category</th>
            <th>This Contract</th>
            <th>Library Average</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, thisVal, avgVal]) => (
            <tr key={label}>
              <td>{label}</td>
              <td><strong>{thisVal}</strong></td>
              <td className="benchmark">{avgVal}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Chat Panel ────────────────────────────────────────────────────────────────

function ChatPanel({ sessionId }: { sessionId: string }) {
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, streamingText])

  const sendMessage = async () => {
    const question = input.trim()
    if (!question || streaming) return

    setInput('')
    setError(null)
    setStreaming(true)
    setStreamingText('')

    const newHistory: ChatMessage[] = [...history, { role: 'user', content: question }]
    setHistory(newHistory)

    let fullText = ''
    try {
      const fetchHeaders: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = getStoredToken()
      if (token) fetchHeaders['Authorization'] = `Bearer ${token}`
      const response = await fetch(`${API_BASE_URL}/api/chat/${sessionId}`, {
        method: 'POST',
        headers: fetchHeaders,
        body: JSON.stringify({ question, history }),
      })

      if (!response.ok) throw new Error('Request failed')
      if (!response.body) throw new Error('No response body')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6).trim()
          if (data === '[DONE]') break
          try {
            const parsed = JSON.parse(data)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.text) {
              fullText += parsed.text
              setStreamingText(fullText)
            }
          } catch (parseErr) {
            if (parseErr instanceof SyntaxError) continue
            throw parseErr
          }
        }
      }

      setHistory([...newHistory, { role: 'assistant', content: fullText }])
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setError(`Chat error: ${msg}`)
      setHistory(newHistory) // keep user message, no assistant reply
    } finally {
      setStreaming(false)
      setStreamingText('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="chat-icon">💬</span>
        <div>
          <h3 className="chat-title">Ask About This Contract</h3>
          <p className="chat-subtitle">
            Ask specific questions about terms, clauses, or obligations in this contract.
          </p>
        </div>
      </div>

      <div className="chat-messages">
        {history.length === 0 && !streaming && (
          <div className="chat-empty">
            <p>Examples: "Does this contract have audit rights?" · "What is the termination penalty?" · "Are there any automatic renewal provisions?"</p>
          </div>
        )}

        {history.map((msg, i) => (
          <div key={i} className={`chat-message chat-message-${msg.role}`}>
            <div className="chat-bubble">
              {msg.content.split('\n').map((line, j) =>
                line ? <p key={j}>{line}</p> : <br key={j} />
              )}
            </div>
          </div>
        ))}

        {streaming && streamingText && (
          <div className="chat-message chat-message-assistant">
            <div className="chat-bubble chat-bubble-streaming">
              {streamingText.split('\n').map((line, j) =>
                line ? <p key={j}>{line}</p> : <br key={j} />
              )}
              <span className="chat-cursor" />
            </div>
          </div>
        )}

        {streaming && !streamingText && (
          <div className="chat-message chat-message-assistant">
            <div className="chat-bubble chat-bubble-thinking">
              <span className="chat-dots">
                <span /><span /><span />
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="chat-error">{error}</div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a specific clause, term, or provision…"
          rows={2}
          disabled={streaming}
        />
        <button
          className="btn btn-primary chat-send"
          onClick={sendMessage}
          disabled={streaming || !input.trim()}
        >
          {streaming ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function ReportView({ analysis, downloadUrl, sessionId, onCompare, onStartRevision }: Props) {
  const gradeColor = GRADE_COLORS[analysis.overall_grade] ?? '#1e3a5f'
  const [letterLoading, setLetterLoading] = useState(false)
  const [rfpLoading, setRfpLoading] = useState(false)

  // Glossary state
  const [glossaryOpen, setGlossaryOpen] = useState(false)
  const [glossaryLoaded, setGlossaryLoaded] = useState(false)
  const [glossaryTerms, setGlossaryTerms] = useState<GlossaryEntry[]>([])
  const [glossarySearch, setGlossarySearch] = useState('')
  const [glossaryExpanded, setGlossaryExpanded] = useState<Record<string, boolean>>({})
  const [glossaryError, setGlossaryError] = useState<string | null>(null)

  const handleGlossaryToggle = async () => {
    const opening = !glossaryOpen
    setGlossaryOpen(opening)
    if (opening && !glossaryLoaded) {
      try {
        const headers: Record<string, string> = {}
        const token = getStoredToken()
        if (token) headers['Authorization'] = `Bearer ${token}`
        const res = await fetch(`${API_BASE_URL}/api/glossary`, { headers })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setGlossaryTerms(data.glossary ?? [])
        setGlossaryLoaded(true)
      } catch (e: unknown) {
        setGlossaryError(e instanceof Error ? e.message : 'Failed to load glossary')
        setGlossaryLoaded(true)
      }
    }
  }

  const toggleGlossaryTerm = (term: string) => {
    setGlossaryExpanded(prev => ({ ...prev, [term]: !prev[term] }))
  }

  const filteredGlossary = glossaryTerms.filter(entry => {
    const q = glossarySearch.toLowerCase()
    return !q || entry.term.toLowerCase().includes(q) || entry.definition.toLowerCase().includes(q)
  })

  const handleDownload = () => {
    if (!downloadUrl) return
    const a = document.createElement('a')
    a.href = `${API_BASE_URL}${downloadUrl}`
    a.download = 'PBM_Analysis_Report.pdf'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleNegotiationLetter = async () => {
    setLetterLoading(true)
    try {
      await downloadNegotiationLetter(sessionId)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      alert(`Could not generate letter: ${msg}`)
    } finally {
      setLetterLoading(false)
    }
  }

  const handleRfpExport = async () => {
    setRfpLoading(true)
    try {
      await downloadRfpExport(sessionId)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      alert(`Could not generate RFP export: ${msg}`)
    } finally {
      setRfpLoading(false)
    }
  }

  const co = analysis.contract_overview
  const pt = analysis.pricing_terms
  const mc = analysis.market_comparison
  const lc = analysis.library_comparison
  const hasSavings = !!(analysis.savings_opportunities && analysis.savings_opportunities.length > 0)
  const _o = lc ? 1 : 0
  const sn = (n: number) => String(n + _o).padStart(2, '0')

  return (
    <div className="report-section">
      {/* Top download bar */}
      <div className="download-bar success">
        <div>
          <strong>✓ Analysis complete.</strong> Review the full report below or download the
          formatted PDF.
        </div>
        <div className="download-bar-actions">
          {downloadUrl && (
            <button className="btn btn-download" onClick={handleDownload}>
              ↓ Download PDF
            </button>
          )}
          <button
            className="btn btn-action"
            onClick={handleNegotiationLetter}
            disabled={letterLoading}
            title="Generate a negotiation letter to send to the PBM"
          >
            {letterLoading ? 'Generating…' : '✉ Negotiation Letter'}
          </button>
          <button
            className="btn btn-action"
            onClick={handleRfpExport}
            disabled={rfpLoading}
            title="Export a prioritized RFP question bank"
          >
            {rfpLoading ? 'Generating…' : '📋 Export RFP Questions'}
          </button>
          <button
            className="btn btn-action"
            onClick={() => onCompare(sessionId)}
            title="Compare with another contract"
          >
            ⇄ Compare
          </button>
          <button
            className="btn btn-action"
            onClick={() => onStartRevision(sessionId)}
            title="Upload the renegotiated contract for a before/after comparison"
          >
            ↺ Upload Revised Contract
          </button>
        </div>
      </div>

      {/* Overall Grade */}
      <div className="grade-banner" style={{ borderLeftColor: gradeColor, backgroundColor: hexToRgba(gradeColor, 0.05) }}>
        <div className="grade-left">
          <div className="grade-letter" style={{ color: gradeColor }}>
            {analysis.overall_grade}
          </div>
        </div>
        <div className="grade-right">
          <div className="grade-label" style={{ color: gradeColor }}>
            {GRADE_LABELS[analysis.overall_grade]}
          </div>
          <p className="grade-desc">
            This contract received a grade of <strong>{analysis.overall_grade}</strong> based on
            pricing competitiveness, risk exposure, and overall client protection relative to
            current market standards.
          </p>
        </div>
      </div>

      {/* Library Comparison (only when ≥3 contracts in library) */}
      {lc && (
        <SectionCard num="01" title="Library Comparison">
          <LibraryComparisonCard lc={lc} />
        </SectionCard>
      )}

      {/* Executive Summary */}
      <SectionCard num={sn(1)} title="Executive Summary">
        {analysis.executive_summary.split('\n\n').map((para, i) =>
          para.trim() ? (
            <p key={i} className="section-body">
              {para.trim()}
            </p>
          ) : null,
        )}
      </SectionCard>

      {/* Key Concerns */}
      <SectionCard num={sn(2)} title="Key Concerns">
        <div className="concerns-list">
          {analysis.key_concerns.map((concern, i) => (
            <div key={i} className="concern-item">
              <span className="concern-num">{i + 1}</span>
              <span>{concern}</span>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Contract Overview */}
      <SectionCard num={sn(3)} title="Contract Overview">
        <table className="data-table">
          <tbody>
            {(
              [
                ['Contracting Parties', co.parties],
                ['Contract Term', co.contract_term],
                ['Effective Date', co.effective_date],
                ['Expiration Date', co.expiration_date],
                ['Renewal Terms', co.renewal_terms],
                ['Termination Provisions', co.termination_provisions],
              ] as [string, string][]
            ).map(([label, value]) => (
              <tr key={label}>
                <td className="table-label">{label}</td>
                <td className="table-value">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      {/* Pricing Terms */}
      <SectionCard num={sn(4)} title="Pricing Terms">
        <table className="data-table pricing-table">
          <thead>
            <tr>
              <th>Pricing Component</th>
              <th>Contract Terms</th>
              <th>Market Benchmark</th>
            </tr>
          </thead>
          <tbody>
            {(
              [
                ['Brand Retail AWP Discount', pt.brand_retail_awp_discount, '15–22% off AWP'],
                ['Brand Mail Order AWP Discount', pt.brand_mail_awp_discount, '20–28% off AWP'],
                ['Generic Retail AWP Discount', pt.generic_retail_awp_discount, '78–88% off AWP'],
                ['Generic Mail Order AWP Discount', pt.generic_mail_awp_discount, '80–90% off AWP'],
                ['Specialty AWP Discount', pt.specialty_awp_discount, '10–20% off AWP'],
                ['Retail Dispensing Fee', pt.retail_dispensing_fee, '$0.00–$2.50 / claim'],
                ['Mail Order Dispensing Fee', pt.mail_dispensing_fee, '$0.00–$1.50 / Rx'],
                ['Administrative Fees', pt.admin_fees, '0–3% of claims'],
                ['Rebate Guarantee', pt.rebate_guarantee, '$100–$400 PEPM'],
                ['MAC Pricing Terms', pt.mac_pricing_terms, 'Transparent list, appeal rights'],
              ] as [string, string, string][]
            ).map(([label, contract, benchmark]) => (
              <tr key={label}>
                <td>{label}</td>
                <td>
                  <strong>{contract}</strong>
                </td>
                <td className="benchmark">{benchmark}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      {/* Market Comparison */}
      <SectionCard num={sn(5)} title="Market Comparison">
        <table className="data-table pricing-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Market Benchmark</th>
              <th>This Contract</th>
              <th>Assessment</th>
            </tr>
          </thead>
          <tbody>
            {(
              [
                ['Brand Retail',   mc.brand_retail_benchmark,   mc.brand_retail_contract,   mc.brand_retail_assessment],
                ['Generic Retail', mc.generic_retail_benchmark, mc.generic_retail_contract, mc.generic_retail_assessment],
                ['Specialty',      mc.specialty_benchmark,      mc.specialty_contract,      mc.specialty_assessment],
              ] as [string, string, string, string][]
            ).map(([category, benchmark, contract, assessment]) => (
              <tr key={category}>
                <td>{category}</td>
                <td>{benchmark}</td>
                <td><strong>{contract}</strong></td>
                <td>
                  <span className={`assessment-badge ${getAssessmentClass(assessment)}`}>
                    {assessment}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="market-summary">{mc.overall_market_position}</p>
      </SectionCard>

      {/* Cost Risk Areas */}
      <SectionCard num={sn(6)} title="Cost Risk Areas">
        <div className="risk-list">
          {analysis.cost_risk_areas.map((risk: CostRiskItem, i) => (
            <div key={i} className={`risk-item risk-border-${risk.risk_level.toLowerCase()}`}>
              <div className="risk-header">
                <span className="risk-name">{risk.area}</span>
                <RiskBadge level={risk.risk_level} />
              </div>
              <p className="risk-desc">{risk.description}</p>
              <p className="risk-impact">
                <strong>Estimated Impact:</strong> {risk.financial_impact}
              </p>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Negotiation Guidance */}
      <SectionCard num={sn(7)} title="Negotiation Guidance">
        <p className="section-intro">
          The following recommendations are specific to the terms found in this contract. Use
          these points during renegotiation to improve client value.
        </p>
        <ol className="guidance-list">
          {analysis.negotiation_guidance.map((item, i) => (
            <li key={i} className="guidance-item">
              {item}
            </li>
          ))}
        </ol>
      </SectionCard>

      {/* Cost Savings Opportunities */}
      {hasSavings && (
        <SectionCard num={sn(8)} title="Cost Savings Opportunities">
          <p className="section-intro">
            The following opportunities can be pursued <strong>independently of PBM renegotiation</strong> — actions your client can take now to reduce pharmacy costs without waiting for contract renewal.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
            {(analysis.savings_opportunities as SavingsItem[]).map((item, i) => {
              const colors = SAVINGS_CATEGORY_COLORS[item.category] ?? { bg: '#f8fafc', accent: '#64748b', pill: '#e2e8f0' }
              const impactColors = SAVINGS_IMPACT_COLORS[item.estimated_impact] ?? { bg: '#f1f5f9', color: '#475569' }
              return (
                <div
                  key={i}
                  style={{
                    background: colors.bg,
                    borderLeft: `4px solid ${colors.accent}`,
                    borderRadius: '8px',
                    padding: '14px 16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                    <span style={{
                      background: colors.pill,
                      color: colors.accent,
                      fontWeight: 600,
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      letterSpacing: '0.03em',
                    }}>
                      {item.category}
                    </span>
                    <span style={{
                      background: impactColors.bg,
                      color: impactColors.color,
                      fontWeight: 600,
                      fontSize: '11px',
                      padding: '2px 8px',
                      borderRadius: '12px',
                    }}>
                      {item.estimated_impact} Impact
                    </span>
                    <span style={{ fontWeight: 700, color: '#1e293b', fontSize: '14px' }}>
                      {item.drug_or_area}
                    </span>
                  </div>
                  <p style={{ color: '#334155', fontSize: '14px', margin: '0 0 8px 0', lineHeight: 1.55 }}>
                    {item.opportunity}
                  </p>
                  <p style={{ color: '#475569', fontSize: '13px', margin: 0 }}>
                    <strong>Action Required:</strong> {item.action_required}
                  </p>
                </div>
              )
            })}
          </div>
        </SectionCard>
      )}

      {/* Chat / Q&A */}
      <ChatPanel sessionId={sessionId} />

      {/* Bottom download */}
      <div className="download-bar bottom">
        <div>Ready to share this analysis with your client?</div>
        <div className="download-bar-actions">
          {downloadUrl && (
            <button className="btn btn-download" onClick={handleDownload}>
              ⬇ Download PDF Report
            </button>
          )}
          <button
            className="btn btn-action"
            onClick={handleNegotiationLetter}
            disabled={letterLoading}
          >
            {letterLoading ? 'Generating…' : '✉ Negotiation Letter'}
          </button>
          <button
            className="btn btn-action"
            onClick={handleRfpExport}
            disabled={rfpLoading}
          >
            {rfpLoading ? 'Generating…' : '📋 RFP Questions'}
          </button>
        </div>
      </div>

      {/* Inline Glossary */}
      <section className="report-section-card" style={{ marginTop: '24px' }}>
        <div className="section-inner">
          <button
            onClick={handleGlossaryToggle}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: '100%',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              textAlign: 'left',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <p className="section-num" style={{ margin: 0 }}>?</p>
              <h2 className="section-title" style={{ margin: 0 }}>PBM Term Glossary</h2>
              {glossaryLoaded && glossaryTerms.length > 0 && (
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>
                  {glossaryTerms.length} terms
                </span>
              )}
            </div>
            <span style={{ fontSize: '18px', color: '#64748b', lineHeight: 1 }}>
              {glossaryOpen ? '▲' : '▼'}
            </span>
          </button>

          {glossaryOpen && (
            <div style={{ marginTop: '16px' }}>
              <div className="section-divider" />
              {!glossaryLoaded && (
                <p style={{ color: '#64748b', textAlign: 'center', padding: '24px 0' }}>Loading glossary…</p>
              )}
              {glossaryError && (
                <p style={{ color: '#dc2626', textAlign: 'center', padding: '16px 0' }}>
                  Could not load glossary: {glossaryError}
                </p>
              )}
              {glossaryLoaded && !glossaryError && (
                <>
                  <input
                    type="text"
                    placeholder="Search terms…"
                    value={glossarySearch}
                    onChange={e => setGlossarySearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #e2e8f0',
                      borderRadius: '6px',
                      fontSize: '14px',
                      marginTop: '12px',
                      marginBottom: '12px',
                      boxSizing: 'border-box',
                    }}
                  />
                  {filteredGlossary.length === 0 && (
                    <p style={{ color: '#64748b', textAlign: 'center', padding: '16px 0' }}>
                      No matching terms.
                    </p>
                  )}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {filteredGlossary.map(entry => (
                      <div
                        key={entry.term}
                        style={{
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                          overflow: 'hidden',
                        }}
                      >
                        <button
                          onClick={() => toggleGlossaryTerm(entry.term)}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            width: '100%',
                            padding: '10px 14px',
                            background: glossaryExpanded[entry.term] ? '#f1f5f9' : '#ffffff',
                            border: 'none',
                            cursor: 'pointer',
                            textAlign: 'left',
                            fontWeight: 600,
                            fontSize: '14px',
                            color: '#1e293b',
                          }}
                        >
                          {entry.term}
                          <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                            {glossaryExpanded[entry.term] ? '▲' : '▼'}
                          </span>
                        </button>
                        {glossaryExpanded[entry.term] && (
                          <div style={{ padding: '10px 14px', background: '#f8fafc', borderTop: '1px solid #e2e8f0' }}>
                            <p style={{ margin: '0 0 6px 0', fontSize: '14px', color: '#334155', lineHeight: 1.55 }}>
                              {entry.definition}
                            </p>
                            {entry.example && (
                              <p style={{ margin: 0, fontSize: '13px', color: '#64748b', fontStyle: 'italic' }}>
                                Example: {entry.example}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
