from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ContactInfo(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    company: str


class ContractOverview(BaseModel):
    parties: str
    contract_term: str
    effective_date: str
    expiration_date: str
    renewal_terms: str
    termination_provisions: str


class PricingTerms(BaseModel):
    brand_retail_awp_discount: str
    brand_mail_awp_discount: str
    generic_retail_awp_discount: str
    generic_mail_awp_discount: str
    specialty_awp_discount: str
    retail_dispensing_fee: str
    mail_dispensing_fee: str
    admin_fees: str
    rebate_guarantee: str
    mac_pricing_terms: str


class CostRiskItem(BaseModel):
    area: str
    description: str
    risk_level: str  # "high", "medium", "low"
    financial_impact: str


class MarketComparison(BaseModel):
    brand_retail_benchmark: str
    brand_retail_contract: str
    brand_retail_assessment: str
    generic_retail_benchmark: str
    generic_retail_contract: str
    generic_retail_assessment: str
    specialty_benchmark: str
    specialty_contract: str
    specialty_assessment: str
    overall_market_position: str


class PBMAnalysisReport(BaseModel):
    executive_summary: str
    contract_overview: ContractOverview
    pricing_terms: PricingTerms
    cost_risk_areas: list[CostRiskItem]
    market_comparison: MarketComparison
    negotiation_guidance: list[str]
    overall_grade: str
    key_concerns: list[str]


class SessionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


class SessionData:
    def __init__(self):
        self.status: SessionStatus = SessionStatus.PENDING
        self.status_message: str = "Initializing..."
        self.analysis_result: Optional[PBMAnalysisReport] = None
        self.contact_info: Optional[ContactInfo] = None
        self.pdf_path: Optional[str] = None
        self.error_message: Optional[str] = None
