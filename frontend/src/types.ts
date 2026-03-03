export interface ContractOverview {
  parties: string
  contract_term: string
  effective_date: string
  expiration_date: string
  renewal_terms: string
  termination_provisions: string
}

export interface PricingTerms {
  brand_retail_awp_discount: string
  brand_mail_awp_discount: string
  generic_retail_awp_discount: string
  generic_mail_awp_discount: string
  specialty_awp_discount: string
  retail_dispensing_fee: string
  mail_dispensing_fee: string
  admin_fees: string
  rebate_guarantee: string
  mac_pricing_terms: string
}

export interface CostRiskItem {
  area: string
  description: string
  risk_level: 'high' | 'medium' | 'low'
  financial_impact: string
}

export interface MarketComparison {
  brand_retail_benchmark: string
  brand_retail_contract: string
  brand_retail_assessment: string
  generic_retail_benchmark: string
  generic_retail_contract: string
  generic_retail_assessment: string
  specialty_benchmark: string
  specialty_contract: string
  specialty_assessment: string
  overall_market_position: string
}

export interface LibraryComparison {
  contracts_in_library: number
  grade_percentile: string
  grade_distribution: Record<string, number>
  avg_brand_retail: string
  avg_generic_retail: string
  avg_specialty: string
  this_brand_retail: string
  this_generic_retail: string
  this_specialty: string
}

export interface AnalysisReport {
  executive_summary: string
  contract_overview: ContractOverview
  pricing_terms: PricingTerms
  cost_risk_areas: CostRiskItem[]
  market_comparison: MarketComparison
  negotiation_guidance: string[]
  overall_grade: 'A' | 'B' | 'C' | 'D' | 'F'
  key_concerns: string[]
  library_comparison?: LibraryComparison
}

export interface AnalysisStatus {
  status: 'pending' | 'processing' | 'complete' | 'error'
  status_message: string
  error_message?: string
}

export interface KnowledgeStatus {
  last_updated: string
  update_count: number
  analyses_count: number
  legislation_count: number
  industry_trends_count: number
  recent_updates: Array<{
    timestamp: string
    updates: string[]
  }>
}

export interface ContractListItem {
  session_id: string
  pbm_name: string | null
  uploaded_at: string
  overall_grade: string
  key_concerns: string[]
}

export interface ContractListResponse {
  contracts: ContractListItem[]
  total: number
  page: number
  pages: number
}

export interface StoredAnalysisResponse {
  analysis: AnalysisReport
  download_url: string | null
  pbm_name: string | null
  uploaded_at: string | null
}

export interface CompareContract {
  session_id: string
  pbm_name: string
  uploaded_at: string
  overall_grade: string
  brand_retail: string
  generic_retail: string
  specialty: string
  retail_dispensing_fee: string
  admin_fees: string
  rebate_guarantee: string
  key_concerns: string[]
}

export interface CompareData {
  a: CompareContract
  b: CompareContract
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface BrokerProfile {
  broker_name: string
  firm_name: string
  email: string
  phone: string
  logo_url: string | null
}

export interface PricingDelta {
  term: string
  original_val: string
  revised_val: string
  delta: string
  improved: boolean | null
}

export interface RevisionSide {
  session_id: string
  pbm_name: string
  uploaded_at: string | null
  overall_grade: string
  key_concerns: string[]
}

export interface RevisionCompareData {
  original: RevisionSide
  revised: RevisionSide
  grade_change: {
    from_grade: string
    to_grade: string
    improved: boolean
    regressed: boolean
  }
  pricing_deltas: PricingDelta[]
  concerns_resolved: string[]
  concerns_new: string[]
  concerns_remaining: string[]
  improvements_count: number
  regressions_count: number
}
