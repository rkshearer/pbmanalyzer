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
