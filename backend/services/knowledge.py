"""
PBM Knowledge Base Service

Maintains a persistent, growing knowledge base of PBM market intelligence,
legislation, and industry trends. Updates automatically from public sources
and learns from each contract analysis performed.
"""

import json
import os
import threading
import time
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DATA_DIR = os.getenv("DATA_DIR", str(Path(__file__).parent.parent))
KNOWLEDGE_FILE = Path(_DATA_DIR) / "knowledge" / "pbm_knowledge.json"

_lock = threading.Lock()

# ── Curated benchmarks embedded in code ──────────────────────────────────────
# These are merged into knowledge.json on every load, so Railway deployments
# automatically refresh the benchmark section without touching volume data.
# Sources: PSG Rx Drug Benefit Practices Survey 2023-2024, Segal Consulting
# 2024, Milliman Employer Drug Benefit Report 2024, Willis Towers Watson 2024,
# FTC Report on Prescription Drug Middlemen July 2024.
_CURATED_BENCHMARKS = {
    "_sources": [
        "Pharmaceutical Strategies Group (PSG) Rx Drug Benefit Practices and Benchmarks Survey, 2023-2024",
        "Segal Consulting Prescription Drug Benefit Cost and Plan Design Survey, 2024",
        "Milliman Employer Drug Benefit Report, 2024",
        "Willis Towers Watson Best Practices in Health Care Employer Survey, 2024",
        "FTC Report on Prescription Drug Middlemen, July 2024",
    ],
    "_important_note": (
        "AWP discounts are only one dimension of PBM value. A contract with AWP-85% on generics "
        "but opaque MAC pricing may cost MORE than one with AWP-78% and transparent MAC. Always "
        "evaluate net effective cost. Pass-through and spread-based contracts require different "
        "benchmarking approaches."
    ),
    "_group_size_note": (
        "Group size (covered lives) significantly affects achievable terms. Smaller groups (<500 lives) "
        "should expect the lower end of ranges; larger groups (>5,000 lives) should demand the upper end."
    ),
    "brand_drugs": {
        "retail_30day": {
            "below_market": "AWP-14% or less",
            "at_market": "AWP-17% to AWP-19%",
            "favorable": "AWP-20% to AWP-22%",
            "top_of_market": "AWP-23%+",
            "typical_median": "AWP-18%",
            "notes": "Formulary preferred brands get higher discounts. Preferred network should yield 2-3% additional.",
        },
        "retail_90day": {
            "at_market": "AWP-19% to AWP-23%",
            "favorable": "AWP-24% to AWP-27%",
            "top_of_market": "AWP-28%+",
        },
        "mail_order_90day": {
            "below_market": "AWP-18% or less",
            "at_market": "AWP-20% to AWP-24%",
            "favorable": "AWP-25% to AWP-28%",
            "top_of_market": "AWP-30%+",
            "notes": "Mail order discounts should exceed retail by at least 3-5 percentage points.",
        },
    },
    "generic_drugs": {
        "_critical_note": (
            "AWP discounts on generics are misleading as a standalone metric. MAC pricing is the actual "
            "mechanism — MAC routinely prices generics at effective AWP discounts of 85-97%. A contract "
            "stating 'AWP-78%' with opaque MAC can cost more than 'AWP-80%' with transparent MAC. "
            "Always require MAC list disclosure and audit rights."
        ),
        "retail_30day": {
            "below_market": "AWP-78% or less (without MAC alternative)",
            "at_market": "AWP-80% to AWP-84% (or MAC, whichever is lower)",
            "favorable": "AWP-85% to AWP-88% (or MAC, whichever is lower)",
            "top_of_market": "AWP-89%+ (or MAC)",
            "mac_transparency_standard": (
                "MAC list disclosed quarterly; binding appeal adjudication within 5-10 business days; "
                "written denial explanation required"
            ),
            "notes": "Effective generic discount with transparent MAC typically ranges AWP-85% to AWP-95%+ claim-weighted.",
        },
        "retail_90day": {"at_market": "AWP-84% to AWP-88%", "favorable": "AWP-89%+"},
        "mail_order_90day": {
            "below_market": "AWP-80% or less",
            "at_market": "AWP-82% to AWP-86%",
            "favorable": "AWP-87% to AWP-90%",
            "top_of_market": "AWP-91%+",
        },
    },
    "specialty_drugs": {
        "_critical_note": (
            "Specialty drugs represent ~50-55% of total drug spend but only 1-2% of prescriptions — "
            "the single highest-impact negotiation area. AWP discount % matters less than: "
            "(1) rebate passthrough, (2) specialty pharmacy exclusivity, "
            "(3) UM program effectiveness, (4) biosimilar substitution policy."
        ),
        "awp_discount": {
            "below_market": "AWP-14% or less",
            "at_market": "AWP-15% to AWP-18%",
            "favorable": "AWP-19% to AWP-22%",
            "top_of_market": "AWP-23%+",
            "limited_distribution_drugs": (
                "AWP discounts of 0-8% for limited distribution drugs (LD drugs) are expected "
                "and not a red flag in isolation."
            ),
            "biosimilars": "AWP-20% to AWP-35% achievable for biosimilar alternatives (Humira biosimilars, etc.)",
        },
        "specialty_rebates": {
            "_note": (
                "Specialty rebates are the most variable and least transparent benchmark in PBM contracting. "
                "Ranges below are estimates based on published surveys — actual experience varies significantly "
                "by formulary design, UM intensity, member mix, and drug utilization. Flag uncertainty when "
                "assessing specialty rebate adequacy."
            ),
            "brand_specialty_rebates_pmpm": {
                "below_market": "Less than $15 PMPM",
                "at_market": "$15 to $40 PMPM",
                "favorable": "$40 to $80 PMPM",
                "top_of_market": "$80+ PMPM",
                "pass_through_note": (
                    "Pass-through arrangements return 100% of gross specialty rebates; actual PMPM depends "
                    "entirely on plan's drug utilization. High autoimmune/inflammation utilization yields highest pools."
                ),
                "key_classes_with_high_rebates": [
                    "Autoimmune/inflammation (TNF-inhibitors, IL-inhibitors)",
                    "Multiple sclerosis",
                    "Anticoagulants (branded)",
                    "Diabetes (branded insulins, GLP-1 agents)",
                    "Respiratory/Asthma",
                ],
                "key_classes_with_low_rebates": [
                    "Oncology (most agents)",
                    "HIV antiretrovirals",
                    "Orphan/rare disease drugs",
                    "Most limited distribution drugs",
                ],
            },
            "retention_model": {
                "below_market": "PBM retains 40%+ of specialty rebates",
                "at_market": "PBM retains 15-25% of specialty rebates",
                "favorable": "PBM retains 0-10% of specialty rebates",
                "top_of_market": "100% specialty rebate passthrough with gross disclosure",
            },
            "specialty_pharmacy_exclusivity": {
                "below_market": "Mandatory exclusive carve-in to PBM-owned specialty pharmacy for all specialty drugs",
                "at_market": "Preferred PBM specialty pharmacy with medical necessity exception",
                "favorable": "Competitive specialty network or right to carve out to independent specialty pharmacy",
                "top_of_market": "Open specialty network with transparent cost comparison",
            },
        },
    },
    "dispensing_fees": {
        "retail_per_claim": {
            "below_market": "$2.00 or more",
            "at_market": "$1.00 to $1.99",
            "favorable": "$0.01 to $0.99",
            "top_of_market": "$0.00",
        },
        "mail_order_per_fill": {
            "below_market": "$1.00 or more",
            "at_market": "$0.01 to $0.99",
            "top_of_market": "$0.00",
            "notes": "Mail order dispensing fees of $0 are common in competitive contracts.",
        },
        "specialty_per_claim": {
            "at_market": "$0.00",
            "notes": "Specialty dispensing fees should be $0; compensation embedded in AWP discount.",
        },
    },
    "rebates_brand_drugs": {
        "_note": (
            "Brand drug rebate guarantees are PMPY (per member per year) — not PEPM. "
            "They represent the minimum the plan receives. Actual rebates are typically higher; "
            "what matters is what the PBM retains above the floor."
        ),
        "pmpy_guarantee_by_group_size": {
            "small_under_500_lives": {
                "below_market": "Less than $30 PMPY",
                "at_market": "$30 to $80 PMPY",
                "favorable": "$80 to $150 PMPY",
            },
            "mid_500_to_5000_lives": {
                "below_market": "Less than $80 PMPY",
                "at_market": "$80 to $180 PMPY",
                "favorable": "$180 to $300 PMPY",
            },
            "large_5000_to_25000_lives": {
                "below_market": "Less than $180 PMPY",
                "at_market": "$180 to $300 PMPY",
                "favorable": "$300 to $500 PMPY",
                "top_of_market": "$500+ PMPY",
            },
            "very_large_over_25000_lives": {
                "at_market": "$300 to $500 PMPY",
                "favorable": "$500+ PMPY",
                "top_of_market": "Custom negotiated, often 100% pass-through",
            },
        },
        "passthrough_vs_retention": {
            "below_market": "PBM retains 40-50%+ of gross rebates; does not disclose gross amount",
            "at_market": "PBM retains 15-30% with quarterly reporting",
            "favorable": "PBM retains 5-15% as admin fee with full gross disclosure",
            "top_of_market": "100% rebate passthrough; PBM compensated only via disclosed admin fee",
        },
        "formulary_compliance_conditions": {
            "reasonable": "Rebate guarantee conditioned on 80-85% formulary compliance",
            "aggressive": "Rebate guarantee voided by any plan design change; threshold above 90%",
        },
    },
    "administrative_fees": {
        "_note": (
            "Admin fees should be evaluated as PMPM, not as % of claims. Spread-model PBMs often show "
            "low/zero admin fees because compensation is embedded in the spread."
        ),
        "pmpm_total": {
            "below_market": "$8.00+ PMPM combined (admin + clinical + reporting)",
            "at_market": "$5.00 to $7.99 PMPM combined",
            "favorable": "$3.00 to $4.99 PMPM combined",
            "top_of_market": "Under $3.00 PMPM (pass-through model only)",
            "notes": (
                "Pass-through model admin fees of $3-6 PMPM are appropriate. Spread model admin fees "
                "appear lower but total PBM compensation is higher via spread."
            ),
        },
        "implementation_fee": {
            "below_market": "$15,000+ with no credit",
            "at_market": "$5,000 to $15,000, sometimes waived",
            "favorable": "Waived or credited against future admin fees",
        },
    },
    "audit_rights": {
        "below_market": "1 audit/year; 12-month lookback; $5,000+ minimum threshold; client pays all audit costs",
        "at_market": "1-2 audits/year; 18-24 month lookback; $1,000-$2,500 minimum threshold; costs split",
        "favorable": "2 audits/year; 24-36 month lookback; no minimum threshold; PBM pays if errors >2% of audited claims",
        "top_of_market": (
            "Unlimited audits; 36-month lookback; no minimum threshold; "
            "independent auditor of client's choice; PBM pays all costs if material errors found"
        ),
        "data_access": {
            "below_market": "Claims data only; no access to actual pharmacy payment data or rebate receipts",
            "top_of_market": "Full access to actual pharmacy reimbursement, manufacturer rebate invoices, all PBM revenue",
        },
    },
    "performance_guarantees": {
        "generic_dispensing_rate": {
            "at_market": "85-88% GDR guarantee",
            "favorable": "89-92% GDR guarantee",
            "notes": "Market GDR is typically 87-91% for commercial plans with active generic programs",
        },
        "claim_accuracy": {"standard": "99.5%", "notes": "Below 99% unacceptable; above 99.9% aspirational"},
        "liability_cap": {
            "below_market": "Aggregate liability capped at 1-2 months of admin fees",
            "at_market": "Aggregate liability capped at 3-6 months of admin fees",
            "favorable": "Meaningful financial exposure without restrictive cap",
        },
    },
    "contract_terms": {
        "termination": {
            "below_market": "180+ days notice; penalty equal to 3+ months admin fees",
            "at_market": "90-120 days notice; penalty only in year 1",
            "favorable": "60-90 days notice; no penalty after year 1",
            "top_of_market": "60 days notice; no penalty at any time",
        },
        "auto_renewal": {
            "below_market": "Auto-renews; 90+ days notice required to cancel",
            "favorable": "30-60 days notice required to cancel renewal",
        },
    },
    "benchmark_confidence": {
        "high_confidence": [
            "Brand retail AWP discounts",
            "Dispensing fees",
            "Administrative fees PMPM",
            "MAC transparency standards",
            "Audit right structures",
        ],
        "medium_confidence": [
            "Generic AWP benchmarks (MAC complexity makes comparisons indirect)",
            "Brand rebate PMPY guarantees by group size",
            "Specialty AWP discounts",
        ],
        "lower_confidence": [
            "Specialty rebate PMPM amounts (highly variable by plan, formulary, and drug mix)",
            "Very large group (>25k lives) benchmarks (custom deals, limited public data)",
            "Post-2025 benchmarks reflecting GLP-1 and biosimilar market evolution",
        ],
    },
    "last_benchmark_update": "2026-02-26",
}

_CURATED_STATIC = {
    "legislation": [
        {
            "title": "Consolidated Appropriations Act, 2021 - PBM Transparency",
            "year": 2021,
            "jurisdiction": "Federal",
            "key_provisions": (
                "Required PBMs to disclose rebates and fees to group health plans. "
                "Prohibited gag clauses preventing pharmacists from telling patients about lower-cost options."
            ),
            "impact": "Increased transparency requirements. Eliminates gag clauses effective Jan 2023.",
        },
        {
            "title": "Inflation Reduction Act",
            "year": 2022,
            "jurisdiction": "Federal",
            "key_provisions": (
                "Medicare drug price negotiation, $35 insulin cap for Medicare, "
                "redesigned Part D benefit, manufacturer rebate changes."
            ),
            "impact": "CMS can negotiate prices for high-cost Medicare drugs. Part D redesign affects rebate calculations from 2025.",
        },
        {
            "title": "FTC PBM Investigation and Report",
            "year": 2024,
            "jurisdiction": "Federal",
            "key_provisions": (
                "FTC found major PBMs (CVS Caremark, Express Scripts, OptumRx) engaged in practices "
                "that may have harmed independent pharmacies and raised costs. Identified spread pricing, "
                "clawbacks, and DIR fees as concerns."
            ),
            "impact": "Increased regulatory scrutiny. Potential for new federal legislation targeting spread pricing and rebate transparency.",
        },
        {
            "title": "State PBM Transparency Laws (30+ states)",
            "year": 2023,
            "jurisdiction": "State - Multiple",
            "key_provisions": (
                "Most states have passed some form of PBM transparency or anti-spread pricing law. "
                "Requirements generally include MAC transparency, appeal rights, and non-discrimination provisions."
            ),
            "impact": "PBMs must disclose more information in many states. Contracts should reference state-specific compliance.",
        },
        {
            "title": "Lower Costs, More Transparency Act",
            "year": 2023,
            "jurisdiction": "Federal (Proposed)",
            "key_provisions": (
                "Would require PBMs to pass 100% of rebates to employer plan sponsors, "
                "prohibit spread pricing in Medicaid, require site-neutral payments."
            ),
            "impact": "If enacted, would fundamentally change PBM revenue model. Monitor for passage.",
        },
    ],
    "industry_trends": [
        "Vertical integration: Top 3 PBMs (CVS Caremark, Express Scripts/Cigna, OptumRx/UnitedHealth) own or are owned by major insurers and specialty pharmacy chains",
        "Specialty drug spend: Specialty drugs represent ~50% of total drug spend but only ~1-2% of prescriptions",
        "DIR fee elimination: Medicare eliminated direct and indirect remuneration fees in 2024, changing PBM economics for Medicare plans",
        "Rebate reform: Increasing pressure to move from rebate-based to net pricing models",
        "Biosimilar adoption: Growing biosimilar market (especially adalimumab/Humira biosimilars) creating new contracting opportunities",
        "Spread pricing scrutiny: Multiple states and federal government investigating spread pricing practices",
        "PBM market concentration: Top 3 PBMs control approximately 80% of commercial market",
        "GLP-1 drug impact: Dramatic increase in GLP-1 (Ozempic, Wegovy) utilization creating significant formulary and cost challenges",
        "Fiduciary standards: Growing movement to hold PBMs to ERISA fiduciary standards when serving employer plans",
        "Independent pharmacy closures: PBM reimbursement practices linked to closure of thousands of independent pharmacies",
    ],
}


def load_knowledge() -> dict:
    with _lock:
        if KNOWLEDGE_FILE.exists():
            with open(KNOWLEDGE_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}
    # Always overlay curated static data so deployments refresh benchmarks
    data["market_benchmarks"] = _CURATED_BENCHMARKS
    if not data.get("legislation"):
        data["legislation"] = _CURATED_STATIC["legislation"]
    if not data.get("industry_trends"):
        data["industry_trends"] = _CURATED_STATIC["industry_trends"]
    return data


def save_knowledge(knowledge: dict):
    knowledge["last_updated"] = datetime.now(timezone.utc).isoformat()
    knowledge["update_count"] = knowledge.get("update_count", 0) + 1
    with _lock:
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_FILE, "w") as f:
            json.dump(knowledge, f, indent=2)


def get_knowledge_status() -> dict:
    from .leads import get_library_benchmarks
    knowledge = load_knowledge()
    library = get_library_benchmarks()
    return {
        "last_updated": knowledge.get("last_updated", "Never"),
        "update_count": knowledge.get("update_count", 0),
        "analyses_count": knowledge.get("market_intelligence", {}).get("analyses_count", 0),
        "legislation_count": len(knowledge.get("legislation", [])),
        "industry_trends_count": len(knowledge.get("industry_trends", [])),
        "recent_updates": knowledge.get("knowledge_updates", [])[-5:],
        "contracts_in_library": library.get("contracts_count", 0),
    }


def record_analysis_insights(analysis_result) -> None:
    """Learn from each contract analysis to build market intelligence."""
    knowledge = load_knowledge()
    mi = knowledge.setdefault("market_intelligence", {
        "analyses_count": 0,
        "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
        "common_risk_areas": [],
        "pricing_observations": []
    })

    mi["analyses_count"] = mi.get("analyses_count", 0) + 1

    grade = analysis_result.overall_grade
    mi.setdefault("grade_distribution", {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0})
    if grade in mi["grade_distribution"]:
        mi["grade_distribution"][grade] += 1

    for risk in analysis_result.cost_risk_areas:
        risk_areas = mi.setdefault("common_risk_areas", [])
        existing = next((r for r in risk_areas if r["area"] == risk.area), None)
        if existing:
            existing["count"] = existing.get("count", 1) + 1
        else:
            risk_areas.append({"area": risk.area, "count": 1, "risk_level": risk.risk_level})

    pricing_obs = mi.setdefault("pricing_observations", [])
    pricing_obs.append({
        "date": datetime.now(timezone.utc).date().isoformat(),
        "brand_retail": analysis_result.pricing_terms.brand_retail_awp_discount,
        "generic_retail": analysis_result.pricing_terms.generic_retail_awp_discount,
        "specialty": analysis_result.pricing_terms.specialty_awp_discount,
        "grade": grade,
    })
    if len(pricing_obs) > 100:
        mi["pricing_observations"] = pricing_obs[-100:]

    knowledge["market_intelligence"] = mi
    save_knowledge(knowledge)


def fetch_federal_register_updates(knowledge: dict) -> list[str]:
    """Fetch recent PBM-related rules from the Federal Register API."""
    updates = []
    try:
        url = (
            "https://www.federalregister.gov/api/v1/articles.json"
            "?per_page=5&order=newest"
            "&conditions[term]=pharmacy+benefit+manager"
            "&conditions[type][]=Rule&conditions[type][]=Proposed+Rule"
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            articles = data.get("results", [])
            new_items = []
            existing_titles = {
                item.get("title") for item in knowledge.get("recent_federal_updates", [])
            }
            for article in articles:
                title = article.get("title", "")
                if title and title not in existing_titles:
                    new_items.append({
                        "title": title,
                        "date": article.get("publication_date", ""),
                        "abstract": (article.get("abstract") or "")[:400],
                        "url": article.get("html_url", ""),
                        "source": "Federal Register",
                    })
                    updates.append(f"New federal rule: {title}")

            all_items = new_items + knowledge.get("recent_federal_updates", [])
            knowledge["recent_federal_updates"] = all_items[:20]
    except Exception as e:
        print(f"[Knowledge] Federal Register fetch failed: {e}")
    return updates


def update_knowledge_base() -> dict:
    """
    Fetch updates from public sources and refresh the knowledge base.
    Returns a summary of what was updated.
    """
    print("[Knowledge] Starting knowledge base update...")
    knowledge = load_knowledge()
    all_updates = []

    federal_updates = fetch_federal_register_updates(knowledge)
    all_updates.extend(federal_updates)

    if all_updates:
        update_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "updates": all_updates,
        }
        knowledge.setdefault("knowledge_updates", []).append(update_record)
        if len(knowledge["knowledge_updates"]) > 50:
            knowledge["knowledge_updates"] = knowledge["knowledge_updates"][-50:]

    save_knowledge(knowledge)
    print(f"[Knowledge] Update complete. {len(all_updates)} new items found.")
    return {"updates_found": len(all_updates), "details": all_updates}


def format_knowledge_for_prompt(knowledge: dict) -> str:
    """Format knowledge base into a concise string for inclusion in the system prompt."""
    sections = []

    benchmarks = knowledge.get("market_benchmarks", {})
    if benchmarks:
        b = benchmarks
        sections.append("CURRENT MARKET BENCHMARKS (sourced from PSG, Segal, Milliman 2024 surveys):")
        sections.append(f"  IMPORTANT: {b.get('_important_note', '')}")
        sections.append(f"  GROUP SIZE NOTE: {b.get('_group_size_note', '')}")

        bd = b.get("brand_drugs", {})
        if bd:
            r30 = bd.get("retail_30day", {})
            sections.append("  Brand Retail (30-day):")
            sections.append(f"    - Below market: {r30.get('below_market', 'N/A')}")
            sections.append(f"    - At market: {r30.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {r30.get('favorable', 'N/A')}")
            sections.append(f"    - Top of market: {r30.get('top_of_market', 'N/A')}")
            mo = bd.get("mail_order_90day", {})
            sections.append("  Brand Mail Order (90-day):")
            sections.append(f"    - At market: {mo.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {mo.get('favorable', 'N/A')}")

        gd = b.get("generic_drugs", {})
        if gd:
            gr = gd.get("retail_30day", {})
            sections.append(f"  Generic Retail: {gd.get('_critical_note', '')}")
            sections.append(f"    - Below market: {gr.get('below_market', 'N/A')}")
            sections.append(f"    - At market: {gr.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {gr.get('favorable', 'N/A')}")
            sections.append(f"    - MAC transparency standard: {gr.get('mac_transparency_standard', 'N/A')}")
            gm = gd.get("mail_order_90day", {})
            sections.append("  Generic Mail Order (90-day):")
            sections.append(f"    - At market: {gm.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {gm.get('favorable', 'N/A')}")

        sp = b.get("specialty_drugs", {})
        if sp:
            sections.append(f"  Specialty Drugs: {sp.get('_critical_note', '')}")
            sa = sp.get("awp_discount", {})
            sections.append("  Specialty AWP Discount:")
            sections.append(f"    - Below market: {sa.get('below_market', 'N/A')}")
            sections.append(f"    - At market: {sa.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {sa.get('favorable', 'N/A')}")
            sections.append(f"    - Biosimilars: {sa.get('biosimilars', 'N/A')}")
            sr = sp.get("specialty_rebates", {})
            pmpm = sr.get("brand_specialty_rebates_pmpm", {})
            sections.append(f"  Specialty Rebates (PMPM): NOTE — {sr.get('_note', '')}")
            sections.append(f"    - Below market: {pmpm.get('below_market', 'N/A')}")
            sections.append(f"    - At market: {pmpm.get('at_market', 'N/A')}")
            sections.append(f"    - Favorable: {pmpm.get('favorable', 'N/A')}")
            sections.append(f"    - High-rebate drug classes: {', '.join(pmpm.get('key_classes_with_high_rebates', []))}")
            sections.append(f"    - Low/no rebate classes: {', '.join(pmpm.get('key_classes_with_low_rebates', []))}")
            ret = sr.get("retention_model", {})
            sections.append("  Specialty Rebate Retention:")
            sections.append(f"    - Below market: {ret.get('below_market', 'N/A')}")
            sections.append(f"    - Favorable: {ret.get('favorable', 'N/A')}")
            exc = sr.get("specialty_pharmacy_exclusivity", {})
            sections.append("  Specialty Pharmacy Exclusivity:")
            sections.append(f"    - Below market: {exc.get('below_market', 'N/A')}")
            sections.append(f"    - Favorable: {exc.get('favorable', 'N/A')}")

        df = b.get("dispensing_fees", {})
        if df:
            sections.append("  Dispensing Fees:")
            sections.append(f"    - Retail per claim: below market={df.get('retail_per_claim', {}).get('below_market','N/A')}, favorable={df.get('retail_per_claim', {}).get('favorable','N/A')}")
            sections.append(f"    - Mail order per fill: top of market={df.get('mail_order_per_fill', {}).get('top_of_market','N/A')}")

        rb = b.get("rebates_brand_drugs", {})
        if rb:
            psz = rb.get("pmpy_guarantee_by_group_size", {})
            sections.append("  Brand Rebate Guarantees (PMPY — per member per year):")
            sections.append(f"    - Small groups (<500 lives): at market={psz.get('small_under_500_lives',{}).get('at_market','N/A')}, favorable={psz.get('small_under_500_lives',{}).get('favorable','N/A')}")
            sections.append(f"    - Mid groups (500-5k lives): at market={psz.get('mid_500_to_5000_lives',{}).get('at_market','N/A')}, favorable={psz.get('mid_500_to_5000_lives',{}).get('favorable','N/A')}")
            sections.append(f"    - Large groups (5k-25k lives): at market={psz.get('large_5000_to_25000_lives',{}).get('at_market','N/A')}, favorable={psz.get('large_5000_to_25000_lives',{}).get('favorable','N/A')}")
            pt = rb.get("passthrough_vs_retention", {})
            sections.append(f"    - Pass-through (best): {pt.get('top_of_market','N/A')}")
            sections.append(f"    - Below market retention: {pt.get('below_market','N/A')}")

        af = b.get("administrative_fees", {})
        if af:
            pm = af.get("pmpm_total", {})
            sections.append("  Administrative Fees (PMPM total):")
            sections.append(f"    - Below market: {pm.get('below_market','N/A')}")
            sections.append(f"    - At market: {pm.get('at_market','N/A')}")
            sections.append(f"    - Favorable: {pm.get('favorable','N/A')}")
            sections.append(f"    - Note: {pm.get('notes','')}")

        ar = b.get("audit_rights", {})
        if ar:
            sections.append("  Audit Rights:")
            sections.append(f"    - Below market: {ar.get('below_market','N/A')}")
            sections.append(f"    - Favorable: {ar.get('favorable','N/A')}")

        conf = b.get("benchmark_confidence", {})
        if conf:
            sections.append("  Benchmark confidence levels:")
            sections.append(f"    - High confidence: {', '.join(conf.get('high_confidence',[]))}")
            sections.append(f"    - Lower confidence (flag uncertainty): {', '.join(conf.get('lower_confidence',[]))}")

    legislation = knowledge.get("legislation", [])
    if legislation:
        sections.append("\nKEY LEGISLATION AND REGULATORY DEVELOPMENTS:")
        for law in legislation[-6:]:
            sections.append(f"  - {law.get('title', '')} ({law.get('year', '')}): {law.get('key_provisions', '')[:200]}")

    recent_fed = knowledge.get("recent_federal_updates", [])
    if recent_fed:
        sections.append("\nRECENT FEDERAL REGISTER UPDATES (PBM-related):")
        for item in recent_fed[:3]:
            sections.append(f"  - [{item.get('date', '')}] {item.get('title', '')}")

    trends = knowledge.get("industry_trends", [])
    if trends:
        sections.append("\nCURRENT INDUSTRY TRENDS:")
        for trend in trends[:6]:
            sections.append(f"  - {trend}")

    mi = knowledge.get("market_intelligence", {})
    if mi.get("analyses_count", 0) > 0:
        sections.append(f"\nMARKET INTELLIGENCE (from {mi['analyses_count']} analyzed contracts):")
        grade_dist = mi.get("grade_distribution", {})
        total = sum(grade_dist.values())
        if total > 0:
            grade_str = ", ".join(f"{g}:{c}" for g, c in grade_dist.items() if c > 0)
            sections.append(f"  - Grade distribution: {grade_str}")
        common_risks = sorted(
            mi.get("common_risk_areas", []),
            key=lambda x: x.get("count", 0),
            reverse=True
        )[:5]
        if common_risks:
            risk_str = ", ".join(r["area"] for r in common_risks)
            sections.append(f"  - Most common risk areas: {risk_str}")

    # Contract library benchmarks (only when ≥3 contracts analyzed)
    try:
        from .leads import get_library_benchmarks
        lib = get_library_benchmarks()
        if lib.get("contracts_count", 0) >= 3:
            n = lib["contracts_count"]
            gd = lib["grade_distribution"]
            grade_str = ", ".join(f"{g}:{c}" for g, c in gd.items() if c > 0)
            top = lib.get("top_concerns", [])
            concern_str = ", ".join(f"{c} ({cnt})" for c, cnt in top) if top else "N/A"
            sections.append(f"\nINTERNAL CONTRACT LIBRARY ({n} analyzed contracts):")
            sections.append(f"  - Grade distribution: {grade_str}")
            sections.append(f"  - Avg brand retail discount: {lib['avg_brand_retail']}")
            sections.append(f"  - Avg generic retail discount: {lib['avg_generic_retail']}")
            sections.append(f"  - Avg specialty discount: {lib['avg_specialty']}")
            sections.append(f"  - Most common red flags: {concern_str}")
            sections.append(
                "Use this data to calibrate percentile rankings and relative comparisons."
            )
    except Exception as e:
        print(f"[Knowledge] Could not load contract library: {e}")

    last_updated = knowledge.get("last_updated", "Unknown")
    sections.append(f"\n[Knowledge base last updated: {last_updated}]")

    return "\n".join(sections)


def periodic_update_worker():
    """Background thread that updates knowledge every 24 hours."""
    # Run immediately on startup, then every 24 hours
    try:
        update_knowledge_base()
    except Exception as e:
        print(f"[Knowledge] Initial update error: {e}")
    while True:
        time.sleep(24 * 3600)
        try:
            update_knowledge_base()
        except Exception as e:
            print(f"[Knowledge] Periodic update error: {e}")


def start_background_updater():
    """Start the background knowledge update thread."""
    thread = threading.Thread(target=periodic_update_worker, daemon=True)
    thread.start()
    print("[Knowledge] Background updater started (updates every 24 hours, first run in 1 hour)")
