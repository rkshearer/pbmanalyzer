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


# ── Market intelligence: biosimilars, patent cliffs, alt pharmacy, coupons ──
# Curated clinical/market data overlaid on every load (same pattern as benchmarks).

_BIOSIMILAR_OPPORTUNITIES = [
    {
        "drug_name": "Humira (adalimumab)",
        "biosimilar_name": "Hadlima, Cyltezo, Hyrimoz, Yusimry, Hulio, Simlandi, Abrilada, and others (10+ FDA-approved)",
        "fda_status": "FDA-approved; multiple commercially available since 2023",
        "launch_date": "2023 (multiple biosimilars launched Jan 2023+)",
        "typical_savings_pct": "30–85% depending on formulary strategy and rebate approach",
        "action_for_employer": (
            "Prefer biosimilar tier with mandatory step therapy. Move originator Humira to non-preferred "
            "or excluded tier. Coordinate with PBM to capture biosimilar rebates, which may partially "
            "offset savings if originator rebates are still flowing through."
        ),
        "notes": (
            "Humira is the single highest-cost specialty drug for most employer plans. Biosimilar adoption "
            "strategy requires careful formulary management. High-concentration citrate-free formulations "
            "may have limited biosimilar substitution; verify interchangeability designation."
        ),
    },
    {
        "drug_name": "Stelara (ustekinumab)",
        "biosimilar_name": "Wezlana, Imuldosa, Pyzchiva, Selarsdi (FDA-approved 2023–2024)",
        "fda_status": "FDA-approved; commercial launches beginning 2025",
        "launch_date": "2025 (patent settlement; commercial availability 2025)",
        "typical_savings_pct": "40–70% vs. originator Stelara",
        "action_for_employer": (
            "Add ustekinumab biosimilars to preferred specialty tier at next renewal. "
            "Confirm step therapy requiring biosimilar trial before originator. "
            "Coordinate with PBM to update formulary positioning before 2025 plan year if possible."
        ),
        "notes": (
            "Stelara (ustekinumab) is a top-5 spend drug for plans with autoimmune population. "
            "Biosimilar launch timing and rebate offset dynamics will affect net savings — model both scenarios."
        ),
    },
    {
        "drug_name": "Enbrel (etanercept)",
        "biosimilar_name": "Erelzi (etanercept-szzs), Eticovo (etanercept-ykro)",
        "fda_status": "FDA-approved; commercially available",
        "launch_date": "Erelzi 2016 (FDA approval), commercial access limited; Eticovo 2019",
        "typical_savings_pct": "20–40% (market adoption slower than Humira biosimilars due to patent disputes)",
        "action_for_employer": (
            "Require prior authorization with biosimilar first for new starts. "
            "Ask PBM about biosimilar rebate contracts vs. originator. "
            "Verify PBM specialty pharmacy formulary positioning."
        ),
        "notes": (
            "Enbrel biosimilar adoption has been slower than Humira due to Amgen exclusivity arrangements "
            "with some PBMs. Check if your PBM has a biosimilar preferred or originator-preferred strategy."
        ),
    },
    {
        "drug_name": "Remicade (infliximab)",
        "biosimilar_name": "Inflectra (infliximab-dyyb), Renflexis (infliximab-abda), Avsola (infliximab-axxq)",
        "fda_status": "FDA-approved; commercially available since 2016–2019",
        "launch_date": "2016+ (multiple biosimilars commercially available)",
        "typical_savings_pct": "30–50% vs. originator Remicade",
        "action_for_employer": (
            "If current formulary still prefers originator Remicade, request immediate biosimilar-first "
            "step therapy. This is a mature biosimilar market — significant savings are available now "
            "if formulary has not been updated. Verify if infliximab claims are going to PBM-owned "
            "specialty pharmacy or independent."
        ),
        "notes": (
            "Infliximab biosimilars represent a mature opportunity. Plans still on originator-preferred "
            "formularies are paying unnecessarily. Rebate offsets from originator J&J should be modeled."
        ),
    },
    {
        "drug_name": "Lantus (insulin glargine)",
        "biosimilar_name": "Rezvoglar (insulin glargine-aglr), Semglee (insulin glargine-yfgn, interchangeable)",
        "fda_status": "FDA-approved and interchangeable; Semglee is first interchangeable biosimilar insulin",
        "launch_date": "Semglee interchangeable 2021; Rezvoglar 2023",
        "typical_savings_pct": "50–80% vs. originator Lantus at list price; $35/month cap through some programs",
        "action_for_employer": (
            "Switch formulary to prefer Semglee (interchangeable) or Rezvoglar over originator Lantus. "
            "Also evaluate Cost Plus Drugs pricing for insulin glargine for members willing to self-pay. "
            "Coordinate with PBM on automatic interchangeable dispensing at retail."
        ),
        "notes": (
            "Insulin pricing has been dramatically reduced through biosimilar entry and manufacturer "
            "voluntary caps. Semglee is FDA-designated interchangeable, allowing automatic substitution "
            "at pharmacy without prescriber action in most states."
        ),
    },
]

_PATENT_CLIFF_GENERICS = [
    {
        "brand_name": "Jardiance (empagliflozin)",
        "generic_name": "empagliflozin",
        "patent_expiry_year": "2025–2026 (expected generic entry)",
        "high_volume_condition": "Type 2 diabetes; also approved for heart failure and CKD",
        "action_for_employer": (
            "Ensure MAC pricing is set aggressively for empagliflozin generics at launch. "
            "Add generic step therapy requirement for new starts as soon as generics are available. "
            "High-volume drug — savings could be significant for plans with large diabetic populations."
        ),
    },
    {
        "brand_name": "Ozempic / Wegovy (semaglutide)",
        "generic_name": "semaglutide (injectable GLP-1; biosimilar path developing; compound FDA-restricted)",
        "patent_expiry_year": "2031+ (branded GLP-1; no generic/biosimilar imminent)",
        "high_volume_condition": "Type 2 diabetes (Ozempic), obesity (Wegovy) — fastest-growing drug class by spend",
        "action_for_employer": (
            "No generic/biosimilar imminent. Focus cost management on: (1) prior authorization for "
            "obesity vs. diabetes indication, (2) step therapy requiring older GLP-1s first, "
            "(3) specialty carve-out review. NOTE: compounded semaglutide is FDA-restricted."
        ),
    },
    {
        "brand_name": "Eliquis (apixaban)",
        "generic_name": "apixaban",
        "patent_expiry_year": "2026 (generics expected mid-2026 after patent settlement)",
        "high_volume_condition": "Atrial fibrillation, DVT/PE prevention — extremely high volume drug",
        "action_for_employer": (
            "Ensure generic step therapy is in place for all new Eliquis starts before generic launch. "
            "At launch, move originator to non-preferred and require generic substitution. "
            "Eliquis is one of the top-10 highest-cost brand drugs — savings at generic launch will be material."
        ),
    },
    {
        "brand_name": "Xarelto (rivaroxaban)",
        "generic_name": "rivaroxaban",
        "patent_expiry_year": "Generic available now (2024+)",
        "high_volume_condition": "Blood clot prevention, atrial fibrillation — high volume",
        "action_for_employer": (
            "Verify that MAC pricing on rivaroxaban generics is current and competitive. "
            "If still seeing originator Xarelto claims, activate generic substitution step therapy. "
            "Check MAC list update frequency — generic MACs may lag actual market pricing."
        ),
    },
    {
        "brand_name": "Dupixent (dupilumab)",
        "generic_name": "dupilumab (biologic — biosimilar path, not traditional generic)",
        "patent_expiry_year": "~2031+ (biologic; biosimilar development underway)",
        "high_volume_condition": "Atopic dermatitis, asthma, COPD, nasal polyps — rapidly expanding indications",
        "action_for_employer": (
            "Biosimilar not imminent. Manage via: (1) prior authorization requiring specialist documentation, "
            "(2) step therapy through topical steroids and other agents first, "
            "(3) specialty carve-out review. Watch for biosimilar development timeline."
        ),
    },
    {
        "brand_name": "Keytruda (pembrolizumab)",
        "generic_name": "pembrolizumab (biologic — biosimilar path)",
        "patent_expiry_year": "~2028 (biosimilar development in progress)",
        "high_volume_condition": "Multiple oncology indications — highest-cost oncology drug by global spend",
        "action_for_employer": (
            "Primarily managed through specialty carve-out and oncology benefit design. "
            "For employer plans: review specialty pharmacy exclusivity clauses, ensure oncology "
            "drugs aren't locked to PBM-owned pharmacy at inflated spreads. "
            "Biosimilar timeline worth monitoring for 2028+ renewal negotiations."
        ),
    },
]

_ALTERNATIVE_PHARMACY_PROGRAMS = [
    {
        "program_name": "Mark Cuban Cost Plus Drugs (costplusdrugs.com)",
        "description": (
            "Transparent pricing model: actual drug cost + 15% markup + $3.00 dispensing fee + $5.00 shipping. "
            "No rebates, no spread, no PBM markups. Prices are dramatically lower than insured prices for "
            "many high-volume generics. Example: metformin 1000mg/90-day ~$6, atorvastatin 20mg/90-day ~$15."
        ),
        "best_for": (
            "High-volume generic medications: metformin, statins (atorvastatin, rosuvastatin), "
            "lisinopril, amlodipine, fluoxetine, sertraline, omeprazole, levothyroxine, and hundreds more."
        ),
        "how_to_access": (
            "Direct-to-consumer at costplusdrugs.com; accessible to all members. "
            "Some employer plans have begun integrating Cost Plus via direct carve-out arrangement."
        ),
        "contract_considerations": (
            "Check if PBM contract contains exclusivity clauses prohibiting directing members to "
            "non-network pharmacies or requiring all covered claims go through contracted network. "
            "Negotiate removal of non-compete or exclusivity provisions at renewal."
        ),
    },
    {
        "program_name": "TrumpRx / HHS Most Favored Nation Pricing",
        "description": (
            "Federal initiative to align U.S. drug prices with international benchmarks. "
            "Executive order issued 2025; implementation details evolving. "
            "If implemented, would significantly reduce list prices for high-cost drugs."
        ),
        "best_for": "High-cost brand and specialty drugs if pricing benchmarks are implemented",
        "how_to_access": "Monitor HHS and CMS guidance; applicable primarily to Medicare initially; employer plan applicability TBD",
        "contract_considerations": (
            "Current PBM contracts may not automatically pass through any list price reductions. "
            "Ensure contract language requires pricing to reflect any government-mandated price reductions."
        ),
    },
    {
        "program_name": "Amazon Pharmacy",
        "description": (
            "Competitive pricing on generic medications with Prime membership discount. "
            "Offers 80+ generics free for Prime members. Also competitive on hundreds of other generics."
        ),
        "best_for": "Generic medications for Prime members; useful for uninsured or high-deductible plan members.",
        "how_to_access": "Direct consumer access at pharmacy.amazon.com; accepts most insurance plans",
        "contract_considerations": (
            "Check whether Amazon Pharmacy is in the PBM's retail network — most major PBMs include it. "
            "Review network exclusivity clauses that may restrict using out-of-network pharmacies."
        ),
    },
    {
        "program_name": "GoodRx",
        "description": (
            "Prescription discount card program offering prices often below insured copays for generics. "
            "Free to use; accepted at most major pharmacies."
        ),
        "best_for": "Uninsured members, high-deductible members, drugs not on formulary, or when GoodRx price beats insurance copay",
        "how_to_access": "goodrx.com or mobile app; show card/coupon at pharmacy; no enrollment required",
        "contract_considerations": (
            "PBM contracts may include accumulator adjustment provisions that prevent GoodRx savings "
            "from counting toward member deductible/OOP max. "
            "Some PBMs prohibit members from using discount cards at network pharmacies."
        ),
    },
    {
        "program_name": "ScriptSave WellRx / NeedyMeds",
        "description": (
            "Prescription discount card and patient assistance programs for non-covered or unaffordable drugs. "
            "NeedyMeds connects members with manufacturer patient assistance programs (PAPs) for free brand drugs."
        ),
        "best_for": "Non-formulary drugs, uninsured members, very low-income members for PAPs",
        "how_to_access": "scriptsave.com, needymeds.org; free to members",
        "contract_considerations": (
            "Same accumulator/maximizer concerns as GoodRx. "
            "Manufacturer PAPs: some PBM contracts treat PAP copay assistance as subject to accumulator rules."
        ),
    },
]

_MANUFACTURER_COUPON_PROVISIONS = [
    {
        "provision_name": "Accumulator Adjustment Programs (AAP)",
        "description": (
            "PBM or insurer collects manufacturer coupon/copay assistance on member's behalf but does NOT "
            "credit the coupon value toward the member's deductible or out-of-pocket maximum. "
            "Member pays full OOP once manufacturer coupon runs out (typically mid-year)."
        ),
        "risk_to_employer": (
            "High: Members who can no longer afford the drug after coupon expiry often abandon therapy. "
            "Also increases plan costs when brand drug claims resume at full OOP after coupon runs out."
        ),
        "what_to_look_for_in_contract": (
            "Search for 'accumulator adjustment,' 'coupon adjustment program,' 'manufacturer assistance adjustment,' "
            "or 'third-party assistance.' Also look for benefit design language around deductible crediting."
        ),
        "negotiation_target": (
            "Negotiate to prohibit accumulator adjustments: all manufacturer coupon/assistance value must credit "
            "toward member deductible and OOP max. Several states have banned accumulator adjustments — "
            "reference applicable state law in contract."
        ),
    },
    {
        "provision_name": "Maximizer Programs",
        "description": (
            "More aggressive variant of accumulator programs. PBM extracts the full manufacturer coupon/OOP "
            "assistance on the member's behalf, applying it to the member's OOP max but keeping or redirecting "
            "the coupon value rather than truly crediting the member's costs."
        ),
        "risk_to_employer": (
            "High: Maximizer programs can significantly increase net plan costs for brand drugs and create "
            "regulatory and fiduciary risk. Some are under legal challenge."
        ),
        "what_to_look_for_in_contract": (
            "Search for 'benefit maximizer,' 'OOP optimizer,' 'copay optimization,' or 'manufacturer assistance "
            "management program.' Often buried in service schedules or addenda."
        ),
        "negotiation_target": (
            "Require written disclosure and explicit plan sponsor consent for any maximizer program. "
            "Consider prohibiting outright. Require all manufacturer assistance to benefit the member directly."
        ),
    },
    {
        "provision_name": "Coupon / Rebate Retention by PBM",
        "description": (
            "PBM retains manufacturer coupons, copay cards, or patient assistance program rebates as additional "
            "revenue without disclosing the amounts or passing them through to the plan sponsor or member."
        ),
        "risk_to_employer": (
            "Medium-High: Reduces transparency of true PBM compensation. PBM revenue from coupon retention "
            "is not visible in standard rebate reporting. Fiduciary duty concerns for ERISA plans."
        ),
        "what_to_look_for_in_contract": (
            "Search for 'administrative fee' language that includes coupon or patient assistance processing. "
            "Look for definitions of 'gross rebate' and whether manufacturer coupons are excluded."
        ),
        "negotiation_target": (
            "Require 100% pass-through of all manufacturer assistance to the plan/member. "
            "Expand rebate audit rights to include coupon and patient assistance programs."
        ),
    },
]

PBM_GLOSSARY = [
    {
        "term": "AWP (Average Wholesale Price)",
        "definition": (
            "A published reference price for prescription drugs used as the basis for calculating "
            "discounts in PBM contracts. PBMs negotiate discounts expressed as a percentage off AWP "
            "(e.g., AWP minus 18% for brand drugs). AWP is not the actual wholesale price — it is a "
            "benchmark established by drug manufacturers and published in industry databases."
        ),
        "example": (
            "If a brand drug has an AWP of $100, an AWP-18% discount means the plan pays $82 per "
            "unit. An AWP-85% discount on a generic means the plan pays $15 per unit."
        ),
        "why_it_matters": (
            "AWP is the foundation of all drug pricing calculations in a PBM contract. Larger "
            "discounts off AWP mean lower net drug costs — but AWP discounts on generics are "
            "misleading without also evaluating MAC pricing."
        ),
    },
    {
        "term": "MAC (Maximum Allowable Cost)",
        "definition": (
            "A PBM-controlled pricing list that sets the maximum reimbursement for generic and "
            "multi-source brand drugs, regardless of the stated AWP discount. MAC pricing typically "
            "results in effective discounts of AWP-85% to AWP-97% on generics."
        ),
        "example": (
            "A generic drug with AWP of $10 might have a MAC price of $0.50 — an effective AWP-95% "
            "discount. A contract showing AWP-80% with opaque MAC could cost more than AWP-78% with "
            "transparent MAC if the MAC list is inflated."
        ),
        "why_it_matters": (
            "MAC pricing is the primary mechanism for generic drug reimbursement and is far more "
            "impactful than the stated AWP discount. Require MAC list disclosure, transparent appeal "
            "rights, and audit access to verify MAC pricing fairly reflects market costs."
        ),
    },
    {
        "term": "Formulary",
        "definition": (
            "A list of covered prescription drugs maintained by the PBM or health plan. Formularies "
            "organize drugs into tiers (1–5+) with different cost-sharing levels. A drug on formulary "
            "is covered; off-formulary drugs may require prior authorization or may not be covered."
        ),
        "example": (
            "A 3-tier formulary: Tier 1 = generic drugs ($10 copay), Tier 2 = preferred brands ($40 "
            "copay), Tier 3 = non-preferred brands ($80 copay). A drug not on any tier is off-formulary "
            "and typically requires PA."
        ),
        "why_it_matters": (
            "Formulary design drives member costs, generic dispensing rates, and rebate revenue. "
            "The employer should control formulary changes — contracts that allow PBM-unilateral "
            "formulary changes mid-term create cost uncertainty."
        ),
    },
    {
        "term": "Formulary Tier",
        "definition": (
            "A classification level within a formulary that determines the cost-sharing requirement "
            "for a drug. Lower tiers typically have lower copays; higher tiers have higher cost-sharing. "
            "Tier placement influences which drugs members use and drives rebate eligibility."
        ),
        "example": (
            "Moving a brand drug from Tier 2 (preferred) to Tier 3 (non-preferred) increases the "
            "member copay, which can shift utilization to generics or biosimilars — reducing plan costs."
        ),
        "why_it_matters": (
            "PBMs earn rebates based on formulary tier placement. Manufacturers pay higher rebates "
            "for preferred (lower) tier placement. Understanding tier structure helps evaluate whether "
            "formulary design maximizes rebate revenue and minimizes net cost."
        ),
    },
    {
        "term": "Generic Dispensing Rate (GDR)",
        "definition": (
            "The percentage of all prescriptions filled with generic drugs rather than brand-name drugs. "
            "A higher GDR indicates more cost-effective drug utilization. GDR is often a performance "
            "guarantee metric in PBM contracts."
        ),
        "example": (
            "A plan with a 90% GDR fills 9 out of 10 prescriptions with generics. PBMs typically "
            "guarantee a minimum GDR of 85–92% for commercial employer plans."
        ),
        "why_it_matters": (
            "Generic drugs cost 80–95% less than brand equivalents on average. Each 1% increase in "
            "GDR can reduce total drug spend by 2–4%. Negotiate a minimum GDR guarantee with financial "
            "consequences if the PBM fails to achieve it."
        ),
    },
    {
        "term": "Rebate",
        "definition": (
            "A payment made by a drug manufacturer to the PBM in exchange for favorable formulary "
            "placement (preferred tier position). Rebates are negotiated between PBMs and manufacturers "
            "and may or may not be passed through to the employer plan."
        ),
        "example": (
            "A manufacturer pays the PBM a 40% rebate on a brand drug with AWP of $500/month "
            "in exchange for preferred Tier 2 placement. If the plan has pass-through pricing, "
            "the employer receives the rebate; if not, the PBM retains all or part."
        ),
        "why_it_matters": (
            "Rebates can significantly offset drug costs — often $100–$500+ per member per year for "
            "employers with pass-through contracts. The key question is: what percentage does the PBM "
            "retain vs. pass to the plan?"
        ),
    },
    {
        "term": "Rebate Guarantee (PMPY)",
        "definition": (
            "A contractual minimum rebate amount the PBM guarantees to pass to the employer plan, "
            "expressed as per member per year (PMPY). The plan receives at least this amount regardless "
            "of actual manufacturer rebate collections."
        ),
        "example": (
            "A $150 PMPY rebate guarantee for a plan with 500 members means the PBM guarantees "
            "at least $75,000 in annual rebate payments to the employer. Actual rebates may be higher."
        ),
        "why_it_matters": (
            "The rebate guarantee floor protects against PBM underperformance but does not cap "
            "PBM retention above the floor. Always review both the guarantee (minimum) and the "
            "passthrough rate (what share of total rebates the employer actually receives)."
        ),
    },
    {
        "term": "Dispensing Fee",
        "definition": (
            "A per-prescription fee paid by the plan to the pharmacy (or PBM) to cover the cost "
            "of dispensing the drug. Separate from the drug ingredient cost (AWP discount). "
            "Dispensing fees apply at retail, mail order, and specialty pharmacies."
        ),
        "example": (
            "A $1.50 per-claim retail dispensing fee on 10,000 annual prescriptions adds $15,000 "
            "in annual dispensing costs. A $0.00 dispensing fee at mail order saves costs on high-volume "
            "maintenance medications."
        ),
        "why_it_matters": (
            "Dispensing fees add to the total drug cost beyond the ingredient cost. "
            "Favorable contracts typically have retail dispensing fees under $1.00 and mail order "
            "fees of $0.00. Specialty dispensing fees should be $0."
        ),
    },
    {
        "term": "Admin Fee (PMPM)",
        "definition": (
            "A fixed per-member-per-month administrative charge paid to the PBM for services "
            "including claims processing, customer service, and formulary management. Separate from "
            "drug ingredient costs and rebates."
        ),
        "example": (
            "A $5.00 PMPM admin fee for a 500-member plan costs $2,500/month or $30,000/year "
            "in administrative charges, regardless of drug spend."
        ),
        "why_it_matters": (
            "Admin fees should be evaluated as a total cost component. Spread-based PBMs often show "
            "low or zero admin fees because compensation is embedded in the spread. Pass-through "
            "contracts rely on transparent admin fees of $3–6 PMPM as the PBM's primary compensation."
        ),
    },
    {
        "term": "Spread Pricing",
        "definition": (
            "A PBM compensation model where the PBM charges the employer plan more for a drug than "
            "it actually reimburses the pharmacy, keeping the difference (the 'spread') as revenue. "
            "The spread is not separately disclosed on claims data."
        ),
        "example": (
            "The PBM reimburses a pharmacy $10 for a generic drug but charges the employer plan "
            "$15 for the same drug — the $5 difference is the spread. On $1M in generic claims, "
            "a 15% average spread = $150,000 in hidden PBM compensation."
        ),
        "why_it_matters": (
            "Spread pricing makes it impossible to verify true drug costs without access to pharmacy "
            "reimbursement data. The FTC has flagged spread pricing as a significant cost driver. "
            "Pass-through contracts eliminate spread by requiring the PBM to charge exactly what it "
            "pays pharmacies."
        ),
    },
    {
        "term": "Pass-Through Pricing",
        "definition": (
            "A PBM contract model where the plan pays the exact same amount the PBM reimburses "
            "pharmacies (no spread), receives 100% of manufacturer rebates, and compensates the PBM "
            "via a transparent admin fee. The opposite of spread pricing."
        ),
        "example": (
            "Under pass-through, if the PBM pays a pharmacy $10 for a generic, the employer pays "
            "exactly $10 plus a disclosed admin fee (e.g., $0.50). Total cost: $10.50, fully transparent."
        ),
        "why_it_matters": (
            "Pass-through contracts provide complete cost transparency and typically deliver better "
            "total value for plans with significant drug spend. They allow independent audit of "
            "actual pharmacy costs and rebate amounts."
        ),
    },
    {
        "term": "Mail Order Pharmacy",
        "definition": (
            "A pharmacy (often PBM-owned or affiliated) that dispenses a 90-day supply of maintenance "
            "medications directly to members by mail. Mail order typically offers higher AWP discounts "
            "and lower or no dispensing fees compared to retail pharmacies."
        ),
        "example": (
            "A member taking a statin for cholesterol gets a 90-day supply by mail for one copay "
            "instead of three retail copays. The plan benefits from higher AWP discounts and lower "
            "dispensing fees at the PBM's mail order facility."
        ),
        "why_it_matters": (
            "Mail order can reduce drug costs significantly for maintenance medications. However, "
            "mandatory mail order requirements for all maintenance drugs can create member "
            "dissatisfaction. Evaluate mail order incentives vs. mandates."
        ),
    },
    {
        "term": "Specialty Pharmacy",
        "definition": (
            "A pharmacy that handles high-cost, complex specialty medications requiring special "
            "handling, storage, or patient management. Most specialty drugs ($600+ per month) must "
            "be dispensed through a specialty pharmacy. PBMs often own or have preferred specialty "
            "pharmacy networks."
        ),
        "example": (
            "A member taking Humira (adalimumab) for rheumatoid arthritis must use the PBM's "
            "preferred specialty pharmacy. If the plan has an exclusive arrangement, the member "
            "cannot use an independent specialty pharmacy even if it offers lower costs."
        ),
        "why_it_matters": (
            "Specialty drugs represent ~50% of total drug spend but only 1-2% of prescriptions. "
            "Specialty pharmacy exclusivity arrangements restrict competition and limit the plan's "
            "ability to find better pricing. Negotiate for competitive specialty pharmacy options."
        ),
    },
    {
        "term": "Specialty Drug",
        "definition": (
            "A prescription drug used to treat complex, chronic, or rare conditions — typically "
            "costing $600+ per month. Specialty drugs include biologics, injectables, infusables, "
            "and oral agents for conditions like rheumatoid arthritis, multiple sclerosis, cancer, "
            "HIV, and rare diseases."
        ),
        "example": (
            "Humira (adalimumab) for rheumatoid arthritis costs approximately $6,000–$8,000/month "
            "at list price. GLP-1 drugs (Ozempic, Wegovy) for diabetes/obesity cost $900–$1,300/month "
            "and are driving significant specialty spend increases in 2024–2025."
        ),
        "why_it_matters": (
            "Specialty drug management is the highest-impact area in PBM contracting. Rebate "
            "passthrough, specialty AWP discounts, UM program effectiveness, and biosimilar "
            "substitution policy have a far greater financial impact than retail drug pricing."
        ),
    },
    {
        "term": "Biosimilar",
        "definition": (
            "A biologic drug approved by the FDA as highly similar to an already-approved reference "
            "biologic (the 'originator' drug), with no clinically meaningful differences in safety "
            "or effectiveness. Biosimilars are typically priced 15–35% below the reference biologic."
        ),
        "example": (
            "There are 10+ FDA-approved biosimilars for Humira (adalimumab). Plans that mandate or "
            "incentivize use of adalimumab biosimilars can save $2,000–$5,000 per patient per year "
            "compared to branded Humira."
        ),
        "why_it_matters": (
            "The Humira biosimilar market and other biosimilar launches represent major cost-saving "
            "opportunities. PBM contracts should include explicit biosimilar substitution policies "
            "and ensure biosimilar rebates are passed through — not offset by higher originator rebates."
        ),
    },
    {
        "term": "Step Therapy",
        "definition": (
            "A utilization management program requiring members to try lower-cost drugs (usually "
            "generics or preferred brands) before the plan will cover more expensive alternatives. "
            "Also called 'fail first' — the member must fail on the first-line drug before the "
            "second-line drug is approved."
        ),
        "example": (
            "Before covering a brand SSRI antidepressant, the plan requires the member to try "
            "a generic SSRI for 60 days. If the member has an adverse reaction or inadequate "
            "response, a prior authorization for the brand is then approved."
        ),
        "why_it_matters": (
            "Step therapy reduces plan costs by directing members to effective lower-cost options "
            "first. However, overly rigid step requirements can create access barriers for members "
            "with established medication regimens. Evaluate step therapy programs for clinical "
            "appropriateness and member impact."
        ),
    },
    {
        "term": "Prior Authorization (PA)",
        "definition": (
            "A utilization management requirement that the prescribing physician must obtain advance "
            "approval from the PBM or plan before a drug will be covered. PAs typically require "
            "clinical documentation demonstrating medical necessity."
        ),
        "example": (
            "A physician prescribing a GLP-1 drug for weight loss must submit clinical notes "
            "confirming BMI ≥30, failed lifestyle interventions, and absence of contraindications "
            "before the claim is approved."
        ),
        "why_it_matters": (
            "PA programs control access to high-cost drugs but can create administrative burden "
            "and care delays. Evaluate PA approval rates, turnaround times, and appeal processes. "
            "PA criteria should be clinically based, not purely cost-driven."
        ),
    },
    {
        "term": "Audit Rights",
        "definition": (
            "Contractual rights allowing the employer (or an independent auditor) to verify the "
            "accuracy of PBM billing, rebate payments, MAC pricing, and pharmacy reimbursements. "
            "Audit rights define frequency, lookback period, auditor selection, and cost responsibility."
        ),
        "example": (
            "A favorable audit clause allows 2 audits per year, 24-month lookback, independent "
            "auditor of the client's choice, and requires the PBM to pay all costs if billing "
            "errors exceed 2% of audited claims."
        ),
        "why_it_matters": (
            "PBM audits routinely identify material billing errors, underpaid rebates, and MAC "
            "pricing issues. Without robust audit rights, these errors go undetected. Audit rights "
            "are one of the highest-ROI provisions to negotiate."
        ),
    },
    {
        "term": "Performance Guarantee",
        "definition": (
            "A contractual commitment by the PBM to achieve minimum performance standards — such "
            "as generic dispensing rate, claim accuracy, rebate guarantee, or customer service levels "
            "— with financial consequences (credits or refunds) if standards are not met."
        ),
        "example": (
            "The PBM guarantees a 90% GDR. If actual GDR is 88%, the PBM pays the employer a "
            "financial credit calculated on the missed 2%. Performance guarantee payments are "
            "typically capped at a multiple of monthly admin fees."
        ),
        "why_it_matters": (
            "Performance guarantees create financial accountability for PBM service quality. "
            "Evaluate the aggregate liability cap — a cap of 1–2 months of admin fees makes "
            "guarantees nearly meaningless. Negotiate meaningful caps and clear measurement criteria."
        ),
    },
    {
        "term": "Drug Utilization Review (DUR)",
        "definition": (
            "A program that evaluates drug prescriptions for appropriateness, safety, and cost-effectiveness "
            "before dispensing (prospective DUR) or after claims are paid (retrospective DUR). DUR "
            "programs identify therapeutic duplication, drug interactions, and inappropriate dosing."
        ),
        "example": (
            "Prospective DUR flags a prescription for an opioid to a member already on a benzodiazepine "
            "and alerts the pharmacist to contact the prescriber before dispensing."
        ),
        "why_it_matters": (
            "Effective DUR programs reduce adverse drug events, unnecessary prescriptions, and "
            "wasteful spend. Retrospective DUR generates utilization reports that identify outlier "
            "prescribers and members for clinical management. Evaluate PBM DUR program effectiveness "
            "and reporting transparency."
        ),
    },
]


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
    # Always overlay curated market intelligence (refreshed on every deploy)
    data["biosimilar_opportunities"] = _BIOSIMILAR_OPPORTUNITIES
    data["patent_cliff_generics"] = _PATENT_CLIFF_GENERICS
    data["alternative_pharmacy_programs"] = _ALTERNATIVE_PHARMACY_PROGRAMS
    data["manufacturer_coupon_provisions"] = _MANUFACTURER_COUPON_PROVISIONS
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

    biosimilars = knowledge.get("biosimilar_opportunities", [])
    if biosimilars:
        sections.append("\nBIOSIMILAR OPPORTUNITIES (use for savings_opportunities):")
        for b in biosimilars:
            sections.append(f"  - {b['drug_name']}: {b['biosimilar_name']} | Status: {b['fda_status']} | Savings: {b['typical_savings_pct']}")
            sections.append(f"    Action: {b['action_for_employer'][:200]}")

    patent_cliffs = knowledge.get("patent_cliff_generics", [])
    if patent_cliffs:
        sections.append("\nPATENT CLIFF / UPCOMING GENERICS (use for savings_opportunities):")
        for p in patent_cliffs:
            sections.append(f"  - {p['brand_name']} ({p['generic_name']}): Generic entry {p['patent_expiry_year']} | Condition: {p['high_volume_condition']}")
            sections.append(f"    Action: {p['action_for_employer'][:200]}")

    alt_programs = knowledge.get("alternative_pharmacy_programs", [])
    if alt_programs:
        sections.append("\nALTERNATIVE PHARMACY PROGRAMS (use for savings_opportunities when contract shows weak generic pricing or spread):")
        for a in alt_programs:
            sections.append(f"  - {a['program_name']}: {a['description'][:200]}")
            sections.append(f"    Best for: {a['best_for'][:150]}")
            sections.append(f"    Contract consideration: {a['contract_considerations'][:200]}")

    coupon_provisions = knowledge.get("manufacturer_coupon_provisions", [])
    if coupon_provisions:
        sections.append("\nMANUFACTURER COUPON / ACCUMULATOR PROVISIONS (use for savings_opportunities when accumulator/coupon language found):")
        for c in coupon_provisions:
            sections.append(f"  - {c['provision_name']}: {c['description'][:200]}")
            sections.append(f"    Contract risk: {c['risk_to_employer'][:150]}")
            sections.append(f"    Negotiation target: {c['negotiation_target'][:200]}")

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
