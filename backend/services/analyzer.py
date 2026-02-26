"""
Claude API integration for PBM contract analysis.
Uses the Files API for efficient document handling and extended thinking
for deep domain-specific contract analysis.
"""

import io
import os
import anthropic
from .models import (
    PBMAnalysisReport,
    ContractOverview,
    LibraryComparison,
    PricingTerms,
    CostRiskItem,
    MarketComparison,
    SessionStatus,
)
from .knowledge import load_knowledge, format_knowledge_for_prompt, record_analysis_insights
from .leads import save_contract, get_library_benchmarks

_GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def _build_library_comparison(analysis: PBMAnalysisReport, benchmarks: dict) -> LibraryComparison:
    total = benchmarks["contracts_count"]
    this_order = _GRADE_ORDER.get(analysis.overall_grade, 2)
    worse = sum(1 for g in benchmarks["grades"] if _GRADE_ORDER.get(g, 2) < this_order)
    pct = round(worse / total * 100) if total > 0 else 0
    if pct > 50:
        grade_percentile = f"top {max(1, 100 - pct)}%"
    else:
        grade_percentile = f"bottom {max(1, pct)}%"
    pt = analysis.pricing_terms
    return LibraryComparison(
        contracts_in_library=total,
        grade_percentile=grade_percentile,
        grade_distribution=benchmarks["grade_distribution"],
        avg_brand_retail=benchmarks["avg_brand_retail"],
        avg_generic_retail=benchmarks["avg_generic_retail"],
        avg_specialty=benchmarks["avg_specialty"],
        this_brand_retail=pt.brand_retail_awp_discount,
        this_generic_retail=pt.generic_retail_awp_discount,
        this_specialty=pt.specialty_awp_discount,
    )


ANALYSIS_TOOL = {
    "name": "analyze_pbm_contract",
    "description": "Analyze a PBM contract and return comprehensive structured findings for benefit consultants",
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-3 paragraph summary of the contract's key strengths, weaknesses, and overall value proposition. Written for benefits consultants to share with clients."
            },
            "contract_overview": {
                "type": "object",
                "properties": {
                    "parties": {"type": "string", "description": "Full names of the contracting parties"},
                    "contract_term": {"type": "string", "description": "Duration of the contract (e.g., '3 years')"},
                    "effective_date": {"type": "string", "description": "Contract start date"},
                    "expiration_date": {"type": "string", "description": "Contract end date"},
                    "renewal_terms": {"type": "string", "description": "Auto-renewal provisions and terms"},
                    "termination_provisions": {"type": "string", "description": "Terms for early termination, notice periods, and penalties"}
                },
                "required": ["parties", "contract_term", "effective_date", "expiration_date", "renewal_terms", "termination_provisions"]
            },
            "pricing_terms": {
                "type": "object",
                "properties": {
                    "brand_retail_awp_discount": {"type": "string", "description": "Brand drug AWP discount % for retail (e.g., '18% off AWP')"},
                    "brand_mail_awp_discount": {"type": "string", "description": "Brand drug AWP discount % for mail order"},
                    "generic_retail_awp_discount": {"type": "string", "description": "Generic drug AWP discount % for retail"},
                    "generic_mail_awp_discount": {"type": "string", "description": "Generic drug AWP discount % for mail order"},
                    "specialty_awp_discount": {"type": "string", "description": "Specialty drug AWP discount %"},
                    "retail_dispensing_fee": {"type": "string", "description": "Per-claim dispensing fee for retail"},
                    "mail_dispensing_fee": {"type": "string", "description": "Per-prescription dispensing fee for mail order"},
                    "admin_fees": {"type": "string", "description": "Administrative fees structure"},
                    "rebate_guarantee": {"type": "string", "description": "Rebate guarantees (PEPM, per-claim, or pass-through commitment)"},
                    "mac_pricing_terms": {"type": "string", "description": "MAC list terms, transparency, appeal rights"}
                },
                "required": ["brand_retail_awp_discount", "brand_mail_awp_discount", "generic_retail_awp_discount", "generic_mail_awp_discount", "specialty_awp_discount", "retail_dispensing_fee", "mail_dispensing_fee", "admin_fees", "rebate_guarantee", "mac_pricing_terms"]
            },
            "cost_risk_areas": {
                "type": "array",
                "description": "Identified cost risk areas, listed from highest to lowest risk",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string", "description": "Short name of the risk area"},
                        "description": {"type": "string", "description": "Plain-English explanation of the risk for consultants"},
                        "risk_level": {"type": "string", "enum": ["high", "medium", "low"]},
                        "financial_impact": {"type": "string", "description": "Estimated or potential financial impact"}
                    },
                    "required": ["area", "description", "risk_level", "financial_impact"]
                }
            },
            "market_comparison": {
                "type": "object",
                "properties": {
                    "brand_retail_benchmark": {"type": "string", "description": "Market benchmark (e.g., '15-22% off AWP')"},
                    "brand_retail_contract": {"type": "string", "description": "What this contract provides"},
                    "brand_retail_assessment": {"type": "string", "description": "One of: 'Favorable', 'At Market', 'Below Market', 'Unfavorable'"},
                    "generic_retail_benchmark": {"type": "string"},
                    "generic_retail_contract": {"type": "string"},
                    "generic_retail_assessment": {"type": "string"},
                    "specialty_benchmark": {"type": "string"},
                    "specialty_contract": {"type": "string"},
                    "specialty_assessment": {"type": "string"},
                    "overall_market_position": {"type": "string", "description": "2-3 sentence overall assessment vs. market"}
                },
                "required": ["brand_retail_benchmark", "brand_retail_contract", "brand_retail_assessment", "generic_retail_benchmark", "generic_retail_contract", "generic_retail_assessment", "specialty_benchmark", "specialty_contract", "specialty_assessment", "overall_market_position"]
            },
            "negotiation_guidance": {
                "type": "array",
                "items": {"type": "string"},
                "description": "6-10 specific, actionable negotiation recommendations tailored to this contract"
            },
            "overall_grade": {
                "type": "string",
                "enum": ["A", "B", "C", "D", "F"],
                "description": "A=excellent (top 20% of market), B=good, C=average market terms, D=below market, F=significantly unfavorable"
            },
            "key_concerns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3-5 most critical red flags or areas of concern, phrased clearly for non-technical readers"
            }
        },
        "required": ["executive_summary", "contract_overview", "pricing_terms", "cost_risk_areas", "market_comparison", "negotiation_guidance", "overall_grade", "key_concerns"]
    }
}


def build_system_prompt() -> str:
    knowledge = load_knowledge()
    knowledge_text = format_knowledge_for_prompt(knowledge)

    return f"""You are an expert PBM (Pharmacy Benefit Manager) contract analyst with 20+ years of experience evaluating pharmacy benefit contracts for employer groups, health plans, and benefits consultants.

Your expertise covers:
- PBM contract structure, standard terms, and negotiation tactics
- Market benchmark pricing across all drug tiers and dispensing channels
- Common PBM tactics that disadvantage plan sponsors (spread pricing, rebate retention, MAC manipulation, DAW penalties, formulary steering)
- Regulatory and legislative environment affecting PBM contracts
- Financial modeling of pharmacy benefit costs

{knowledge_text}

ANALYSIS APPROACH:
1. Extract ALL pricing terms precisely as stated in the contract
2. Compare each pricing term to current market benchmarks
3. Identify every cost risk area with plain-English explanations
4. Provide a realistic grade based on overall market competitiveness
5. Give specific, actionable negotiation guidance tailored to the specific issues found

IMPORTANT RULES:
- If a term is not found in the contract, state "Not specified in contract" rather than guessing
- Use plain English that a CFO or HR Director can understand without pharmacy expertise
- Flag any terms that are aggressive, unusual, or potentially costly
- The grade should reflect the TRUE market position — most contracts are C or D, not A or B
- Negotiation guidance must be specific to the issues found, not generic advice

Write for benefits consultants who will present this to employer clients."""


def analyze_contract_background(sessions: dict, session_id: str, text: str) -> None:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        sessions[session_id].status = SessionStatus.PROCESSING
        sessions[session_id].status_message = "Uploading contract to analysis engine..."

        system_prompt = build_system_prompt()

        # Try Files API for efficient handling of large documents
        file_id = None
        try:
            file_content = io.BytesIO(text.encode("utf-8"))
            file_response = client.beta.files.upload(
                file=("contract.txt", file_content, "text/plain"),
            )
            file_id = file_response.id
            print(f"[Analyzer] Uploaded to Files API: {file_id}")
        except Exception as e:
            print(f"[Analyzer] Files API unavailable ({e}), using direct text")

        sessions[session_id].status_message = "Reading and parsing contract terms..."

        if file_id:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {"type": "file", "file_id": file_id},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Please perform a comprehensive analysis of this PBM contract. "
                                "Extract all pricing terms, identify cost risk areas, compare to market benchmarks, "
                                "and provide specific negotiation guidance. "
                                "Use the analyze_pbm_contract tool to return your complete structured findings."
                            ),
                        },
                    ],
                }
            ]
        else:
            text_truncated = text[:120000]
            messages = [
                {
                    "role": "user",
                    "content": (
                        "Please perform a comprehensive analysis of this PBM contract. "
                        "Extract all pricing terms, identify cost risk areas, compare to market benchmarks, "
                        "and provide specific negotiation guidance. "
                        "Use the analyze_pbm_contract tool to return your complete structured findings.\n\n"
                        f"CONTRACT TEXT:\n{text_truncated}"
                    ),
                }
            ]

        sessions[session_id].status_message = "Analyzing pricing terms and contract structure..."

        response = _call_claude_with_fallbacks(
            client=client,
            system_prompt=system_prompt,
            messages=messages,
            use_files_api=(file_id is not None),
        )

        sessions[session_id].status_message = "Comparing to market benchmarks..."

        tool_use_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use" and b.name == "analyze_pbm_contract"),
            None,
        )

        if not tool_use_block:
            raise ValueError("Claude did not return structured analysis data. Please try again.")

        sessions[session_id].status_message = "Generating recommendations..."

        data = tool_use_block.input
        analysis = PBMAnalysisReport(
            executive_summary=data["executive_summary"],
            contract_overview=ContractOverview(**data["contract_overview"]),
            pricing_terms=PricingTerms(**data["pricing_terms"]),
            cost_risk_areas=[CostRiskItem(**item) for item in data["cost_risk_areas"]],
            market_comparison=MarketComparison(**data["market_comparison"]),
            negotiation_guidance=data["negotiation_guidance"],
            overall_grade=data["overall_grade"],
            key_concerns=data["key_concerns"],
        )

        sessions[session_id].analysis_result = analysis
        sessions[session_id].status = SessionStatus.COMPLETE
        sessions[session_id].status_message = "Analysis complete"

        # Learn from this analysis
        try:
            record_analysis_insights(analysis)
        except Exception as e:
            print(f"[Analyzer] Failed to record insights: {e}")

        # Save to contract library and build comparison
        try:
            save_contract(session_id, analysis, text)
            benchmarks = get_library_benchmarks()
            if benchmarks.get("contracts_count", 0) >= 3:
                analysis.library_comparison = _build_library_comparison(analysis, benchmarks)
        except Exception as e:
            print(f"[Analyzer] Failed to save/compare contract library: {e}")

        # Clean up Files API file
        if file_id:
            try:
                client.beta.files.delete(file_id)
            except Exception:
                pass

    except Exception as e:
        sessions[session_id].status = SessionStatus.ERROR
        sessions[session_id].status_message = "Analysis failed"
        sessions[session_id].error_message = str(e)
        print(f"[Analyzer] Error for session {session_id}: {e}")


def _call_claude_with_fallbacks(client, system_prompt, messages, use_files_api: bool):
    """
    Try Claude API calls with progressive fallbacks:
    1. Files API + extended thinking + tool_use
    2. Files API + tool_use (no thinking)
    3. Direct text + thinking + tool_use
    4. Direct text + tool_use only
    """
    common_kwargs = {
        "model": "claude-opus-4-6",
        "max_tokens": 16000,
        "system": system_prompt,
        "messages": messages,
        "tools": [ANALYSIS_TOOL],
        "tool_choice": {"type": "tool", "name": "analyze_pbm_contract"},
    }

    # Attempt 1: Files API + thinking
    if use_files_api:
        try:
            return client.beta.messages.create(
                **common_kwargs,
                betas=["files-api-2025-04-14"],
                thinking={"type": "enabled", "budget_tokens": 8000},
            )
        except Exception as e:
            print(f"[Analyzer] Files API + thinking failed: {e}")

        # Attempt 2: Files API without thinking
        try:
            return client.beta.messages.create(
                **common_kwargs,
                betas=["files-api-2025-04-14"],
            )
        except Exception as e:
            print(f"[Analyzer] Files API (no thinking) failed: {e}")

    # Attempt 3: Direct text + thinking
    try:
        return client.messages.create(
            **common_kwargs,
            thinking={"type": "enabled", "budget_tokens": 8000},
        )
    except Exception as e:
        print(f"[Analyzer] Direct text + thinking failed: {e}")

    # Attempt 4: Direct text, no thinking
    return client.messages.create(**common_kwargs)
