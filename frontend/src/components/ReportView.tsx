import { useState, useRef, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { AnalysisReport, CostRiskItem, LibraryComparison, ChatMessage } from '../types'
import { API_BASE_URL, downloadNegotiationLetter, downloadRfpExport } from '../api'

interface Props {
  analysis: AnalysisReport
  downloadUrl: string | null
  sessionId: string
  onCompare: (sessionId: string) => void
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
      const response = await fetch(`${API_BASE_URL}/api/chat/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

export default function ReportView({ analysis, downloadUrl, sessionId, onCompare }: Props) {
  const gradeColor = GRADE_COLORS[analysis.overall_grade] ?? '#1e3a5f'
  const [letterLoading, setLetterLoading] = useState(false)
  const [rfpLoading, setRfpLoading] = useState(false)

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
  const sn = (n: number) => String(lc ? n + 1 : n).padStart(2, '0')

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
    </div>
  )
}
