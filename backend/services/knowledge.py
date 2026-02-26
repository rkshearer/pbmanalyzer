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

KNOWLEDGE_FILE = Path(__file__).parent.parent / "knowledge" / "pbm_knowledge.json"

_lock = threading.Lock()


def load_knowledge() -> dict:
    with _lock:
        if KNOWLEDGE_FILE.exists():
            with open(KNOWLEDGE_FILE, "r") as f:
                return json.load(f)
        return {}


def save_knowledge(knowledge: dict):
    knowledge["last_updated"] = datetime.now(timezone.utc).isoformat()
    knowledge["update_count"] = knowledge.get("update_count", 0) + 1
    with _lock:
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_FILE, "w") as f:
            json.dump(knowledge, f, indent=2)


def get_knowledge_status() -> dict:
    knowledge = load_knowledge()
    return {
        "last_updated": knowledge.get("last_updated", "Never"),
        "update_count": knowledge.get("update_count", 0),
        "analyses_count": knowledge.get("market_intelligence", {}).get("analyses_count", 0),
        "legislation_count": len(knowledge.get("legislation", [])),
        "industry_trends_count": len(knowledge.get("industry_trends", [])),
        "recent_updates": knowledge.get("knowledge_updates", [])[-5:],
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
        sections.append("CURRENT MARKET BENCHMARKS:")
        sections.append(f"  - Brand retail: {benchmarks.get('brand_retail_awp_range', 'N/A')}")
        sections.append(f"  - Brand mail order: {benchmarks.get('brand_mail_awp_range', 'N/A')}")
        sections.append(f"  - Generic retail: {benchmarks.get('generic_retail_awp_range', 'N/A')}")
        sections.append(f"  - Generic mail order: {benchmarks.get('generic_mail_awp_range', 'N/A')}")
        sections.append(f"  - Specialty: {benchmarks.get('specialty_awp_range', 'N/A')}")
        sections.append(f"  - Retail dispensing fee: {benchmarks.get('retail_dispensing_fee_range', 'N/A')}")
        sections.append(f"  - Mail dispensing fee: {benchmarks.get('mail_dispensing_fee_range', 'N/A')}")
        sections.append(f"  - Admin fees: {benchmarks.get('admin_fee_range', 'N/A')}")
        sections.append(f"  - Rebate guarantee: {benchmarks.get('rebate_guarantee_range', 'N/A')}")

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

    last_updated = knowledge.get("last_updated", "Unknown")
    sections.append(f"\n[Knowledge base last updated: {last_updated}]")

    return "\n".join(sections)


def periodic_update_worker():
    """Background thread that updates knowledge every 24 hours."""
    time.sleep(3600)
    while True:
        try:
            update_knowledge_base()
        except Exception as e:
            print(f"[Knowledge] Periodic update error: {e}")
        time.sleep(24 * 3600)


def start_background_updater():
    """Start the background knowledge update thread."""
    thread = threading.Thread(target=periodic_update_worker, daemon=True)
    thread.start()
    print("[Knowledge] Background updater started (updates every 24 hours, first run in 1 hour)")
