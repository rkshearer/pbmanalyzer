import type { ReactNode } from 'react'
import type { AnalysisReport, CostRiskItem } from '../types'

interface Props {
  analysis: AnalysisReport
  downloadUrl: string
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

const GRADE_COLORS: Record<string, string> = {
  A: '#2e7d32',
  B: '#1565c0',
  C: '#f57c00',
  D: '#e64a19',
  F: '#c62828',
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

export default function ReportView({ analysis, downloadUrl }: Props) {
  const gradeColor = GRADE_COLORS[analysis.overall_grade] ?? '#1e3a5f'

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = 'PBM_Analysis_Report.pdf'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const co = analysis.contract_overview
  const pt = analysis.pricing_terms
  const mc = analysis.market_comparison

  return (
    <div className="report-section">
      {/* Top download bar */}
      <div className="download-bar success">
        <div>
          <strong>✓ Analysis complete.</strong> Review the full report below or download the
          formatted PDF.
        </div>
        <button className="btn btn-download" onClick={handleDownload}>
          ↓ Download PDF Report
        </button>
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

      {/* Executive Summary */}
      <SectionCard num="01" title="Executive Summary">
        {analysis.executive_summary.split('\n\n').map((para, i) =>
          para.trim() ? (
            <p key={i} className="section-body">
              {para.trim()}
            </p>
          ) : null,
        )}
      </SectionCard>

      {/* Key Concerns */}
      <SectionCard num="02" title="Key Concerns">
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
      <SectionCard num="03" title="Contract Overview">
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
      <SectionCard num="04" title="Pricing Terms">
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
      <SectionCard num="05" title="Market Comparison">
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
                [
                  'Brand Retail',
                  mc.brand_retail_benchmark,
                  mc.brand_retail_contract,
                  mc.brand_retail_assessment,
                ],
                [
                  'Generic Retail',
                  mc.generic_retail_benchmark,
                  mc.generic_retail_contract,
                  mc.generic_retail_assessment,
                ],
                [
                  'Specialty',
                  mc.specialty_benchmark,
                  mc.specialty_contract,
                  mc.specialty_assessment,
                ],
              ] as [string, string, string, string][]
            ).map(([category, benchmark, contract, assessment]) => (
              <tr key={category}>
                <td>{category}</td>
                <td>{benchmark}</td>
                <td>
                  <strong>{contract}</strong>
                </td>
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
      <SectionCard num="06" title="Cost Risk Areas">
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
      <SectionCard num="07" title="Negotiation Guidance">
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

      {/* Bottom download */}
      <div className="download-bar bottom">
        <div>Ready to share this analysis with your client?</div>
        <button className="btn btn-download" onClick={handleDownload}>
          ⬇ Download PDF Report
        </button>
      </div>
    </div>
  )
}
