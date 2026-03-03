"""
Lead capture service.
Saves contact info + analysis grade to a local SQLite database.
Optionally sends an email notification via SMTP on each new lead.
"""

import csv
import io
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Optional

from .models import ContactInfo, PBMAnalysisReport

# DB lives in DATA_DIR (env var) so Railway volume persistence works.
# Falls back to backend/ directory for local dev.
_DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_DATA_DIR, "leads.db")


# ── Database setup ────────────────────────────────────────────────────────────

def init_db():
    """Create the leads and contracts tables if they don't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_at  TEXT    NOT NULL,
                first_name    TEXT    NOT NULL,
                last_name     TEXT    NOT NULL,
                email         TEXT    NOT NULL,
                phone         TEXT    NOT NULL,
                company       TEXT    NOT NULL,
                overall_grade TEXT,
                key_concerns  TEXT,
                session_id    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id           TEXT UNIQUE NOT NULL,
                pbm_name             TEXT,
                uploaded_at          TEXT NOT NULL,
                overall_grade        TEXT,
                brand_retail         TEXT,
                generic_retail       TEXT,
                specialty            TEXT,
                retail_dispensing_fee TEXT,
                admin_fees           TEXT,
                rebate_guarantee     TEXT,
                key_concerns         TEXT,
                contract_text        TEXT
            )
        """)
        # Migration: add analysis_json column if it doesn't exist yet
        try:
            conn.execute("ALTER TABLE contracts ADD COLUMN analysis_json TEXT")
        except Exception:
            pass  # Column already exists

        # Broker profile table (single-row, upsert on save)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS broker_profile (
                id          INTEGER PRIMARY KEY,
                broker_name TEXT DEFAULT '',
                firm_name   TEXT DEFAULT '',
                email       TEXT DEFAULT '',
                phone       TEXT DEFAULT '',
                logo_path   TEXT,
                updated_at  TEXT
            )
        """)
        conn.commit()


# ── Save a lead ───────────────────────────────────────────────────────────────

def save_lead(contact: ContactInfo, analysis: PBMAnalysisReport, session_id: str):
    """
    Write a lead to SQLite, then attempt to send an email notification.
    Email errors are swallowed so they never break the HTTP response.
    """
    submitted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO leads
              (submitted_at, first_name, last_name, email, phone, company,
               overall_grade, key_concerns, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submitted_at,
                contact.first_name,
                contact.last_name,
                contact.email,
                contact.phone,
                contact.company,
                analysis.overall_grade,
                json.dumps(analysis.key_concerns),
                session_id,
            ),
        )
        conn.commit()

    # Email notification — log errors but don't break the HTTP response
    try:
        _send_notification(contact, analysis, submitted_at)
    except Exception as exc:
        logging.getLogger(__name__).error("Email notification failed: %s", exc, exc_info=True)


# ── Email notification ────────────────────────────────────────────────────────

def _send_notification(contact: ContactInfo, analysis: PBMAnalysisReport,
                       submitted_at: str):
    """
    Send an HTML email via Resend API (HTTPS — works on Railway).
    Required env vars: RESEND_API_KEY, NOTIFY_EMAIL
    Optional:          NOTIFY_FROM (default: onboarding@resend.dev for testing,
                       or your verified domain sender)
    """
    import requests as _requests

    api_key      = os.getenv("RESEND_API_KEY", "").strip()
    notify_email = os.getenv("NOTIFY_EMAIL", "").strip()
    from_address = os.getenv("NOTIFY_FROM", "PBM Analyzer <onboarding@resend.dev>")

    if not (api_key and notify_email):
        return  # Not configured — skip silently

    grade_color = {
        "A": "#16a34a", "B": "#1d4ed8", "C": "#d97706",
        "D": "#ea580c", "F": "#dc2626",
    }.get(analysis.overall_grade, "#1e3a5f")

    concerns_html = "".join(
        f'<li style="margin-bottom:4px;">{c}</li>'
        for c in analysis.key_concerns[:5]
    )

    body_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:580px;margin:0 auto;">
      <div style="background:#1e3a5f;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;font-size:18px;">
          New PBM Analysis Lead
        </h2>
      </div>
      <div style="border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;
                  padding:24px 28px;">
        <table style="border-collapse:collapse;width:100%;font-size:14px;">
          <tr>
            <td style="padding:8px 12px;font-weight:600;color:#64748b;width:130px;">Name</td>
            <td style="padding:8px 12px;color:#0f172a;">
              {contact.first_name} {contact.last_name}
            </td>
          </tr>
          <tr style="background:#f8fafc;">
            <td style="padding:8px 12px;font-weight:600;color:#64748b;">Company</td>
            <td style="padding:8px 12px;color:#0f172a;">{contact.company}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;font-weight:600;color:#64748b;">Email</td>
            <td style="padding:8px 12px;">
              <a href="mailto:{contact.email}" style="color:#1d4ed8;">{contact.email}</a>
            </td>
          </tr>
          <tr style="background:#f8fafc;">
            <td style="padding:8px 12px;font-weight:600;color:#64748b;">Phone</td>
            <td style="padding:8px 12px;color:#0f172a;">{contact.phone}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;font-weight:600;color:#64748b;">Grade</td>
            <td style="padding:8px 12px;font-weight:800;font-size:18px;
                       color:{grade_color};">{analysis.overall_grade}</td>
          </tr>
          <tr style="background:#f8fafc;">
            <td style="padding:8px 12px;font-weight:600;color:#64748b;">Submitted</td>
            <td style="padding:8px 12px;color:#64748b;">{submitted_at} UTC</td>
          </tr>
        </table>

        <div style="margin-top:20px;padding:14px 16px;background:#fef2f2;
                    border-left:4px solid #dc2626;border-radius:6px;">
          <p style="margin:0 0 8px;font-weight:600;color:#7f1d1d;font-size:13px;">
            Key concerns in their contract:
          </p>
          <ul style="margin:0;padding-left:18px;color:#7f1d1d;font-size:13px;line-height:1.6;">
            {concerns_html}
          </ul>
        </div>

        <p style="margin-top:20px;font-size:12px;color:#94a3b8;">
          PBM Contract Analyzer · Automated lead notification
        </p>
      </div>
    </div>
    """

    resp = _requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": from_address,
            "to": [notify_email],
            "subject": (f"New PBM Lead: {contact.first_name} {contact.last_name}"
                        f" — {contact.company} (Grade {analysis.overall_grade})"),
            "html": body_html,
        },
        timeout=10,
    )
    resp.raise_for_status()


# ── Contract Library ──────────────────────────────────────────────────────────

def _parse_pct(s: str) -> Optional[float]:
    """Extract the first numeric percentage value from a pricing string, or None."""
    if not s or s.lower().startswith("not"):
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*%', s)
    return float(m.group(1)) if m else None


def save_contract(session_id: str, analysis: PBMAnalysisReport, contract_text: str):
    """Save analyzed contract to the library for future benchmarking."""
    uploaded_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    pt = analysis.pricing_terms
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO contracts
              (session_id, pbm_name, uploaded_at, overall_grade,
               brand_retail, generic_retail, specialty,
               retail_dispensing_fee, admin_fees, rebate_guarantee,
               key_concerns, contract_text, analysis_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                analysis.contract_overview.parties,
                uploaded_at,
                analysis.overall_grade,
                pt.brand_retail_awp_discount,
                pt.generic_retail_awp_discount,
                pt.specialty_awp_discount,
                pt.retail_dispensing_fee,
                pt.admin_fees,
                pt.rebate_guarantee,
                json.dumps(analysis.key_concerns),
                contract_text,
                analysis.model_dump_json(),
            ),
        )
        conn.commit()


def _parse_dollar(s: str) -> Optional[float]:
    """Extract the first dollar amount from a string, or None."""
    if not s or s.lower().startswith("not"):
        return None
    m = re.search(r'\$\s*(\d+(?:\.\d+)?)', s)
    return float(m.group(1)) if m else None


def get_library_benchmarks() -> dict:
    """Return aggregate statistics from the contract library for prompt enrichment and comparison cards."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT overall_grade, brand_retail, generic_retail, specialty, "
            "retail_dispensing_fee, admin_fees, rebate_guarantee, key_concerns FROM contracts"
        ).fetchall()
        json_rows = conn.execute(
            "SELECT analysis_json FROM contracts WHERE analysis_json IS NOT NULL"
        ).fetchall()

    count = len(rows)
    if count == 0:
        return {"contracts_count": 0}

    grade_distribution: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    grades: list[str] = []
    brand_retails: list[str] = []
    generic_retails: list[str] = []
    specialties: list[str] = []
    dispensing_fees: list[str] = []
    admin_fees_list: list[str] = []
    rebate_guarantees: list[str] = []
    concern_counts: dict[str, int] = {}

    for row in rows:
        grade = row["overall_grade"]
        if grade in grade_distribution:
            grade_distribution[grade] += 1
        grades.append(grade)
        brand_retails.append(row["brand_retail"] or "")
        generic_retails.append(row["generic_retail"] or "")
        specialties.append(row["specialty"] or "")
        dispensing_fees.append(row["retail_dispensing_fee"] or "")
        admin_fees_list.append(row["admin_fees"] or "")
        rebate_guarantees.append(row["rebate_guarantee"] or "")
        try:
            for concern in json.loads(row["key_concerns"] or "[]"):
                concern_counts[concern] = concern_counts.get(concern, 0) + 1
        except Exception:
            pass

    # Parse analysis_json for risk distribution and mail AWP discounts
    risk_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    risk_area_counts: dict[str, int] = {}
    brand_mails: list[str] = []
    generic_mails: list[str] = []

    for row in json_rows:
        try:
            data = json.loads(row["analysis_json"])
        except Exception:
            continue
        for item in data.get("cost_risk_areas", []):
            level = item.get("risk_level", "").lower()
            if level in risk_counts:
                risk_counts[level] += 1
            if level == "high":
                area = item.get("area", "")
                if area:
                    risk_area_counts[area] = risk_area_counts.get(area, 0) + 1
        pt = data.get("pricing_terms", {})
        brand_mails.append(pt.get("brand_mail_awp_discount", "") or "")
        generic_mails.append(pt.get("generic_mail_awp_discount", "") or "")

    def _avg_awp(strings: list[str]) -> str:
        vals = [_parse_pct(s) for s in strings]
        vals = [v for v in vals if v is not None]
        if not vals:
            return "N/A"
        return f"AWP-{sum(vals) / len(vals):.1f}%"

    def _avg_dollar(strings: list[str], suffix: str = "") -> str:
        vals = [_parse_dollar(s) for s in strings]
        vals = [v for v in vals if v is not None]
        if not vals:
            return "N/A"
        avg = sum(vals) / len(vals)
        return f"${avg:.2f}{suffix}"

    top_concerns = sorted(concern_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_risk_areas = sorted(risk_area_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "contracts_count": count,
        "grade_distribution": grade_distribution,
        "grades": grades,
        "avg_brand_retail": _avg_awp(brand_retails),
        "avg_generic_retail": _avg_awp(generic_retails),
        "avg_specialty": _avg_awp(specialties),
        "avg_brand_mail": _avg_awp(brand_mails),
        "avg_generic_mail": _avg_awp(generic_mails),
        "avg_dispensing_fee": _avg_dollar(dispensing_fees, " per claim"),
        "avg_admin_fee": _avg_dollar(admin_fees_list, " PEPM"),
        "avg_rebate_guarantee": _avg_dollar(rebate_guarantees, " PMPY"),
        "top_concerns": top_concerns,
        "risk_distribution": risk_counts,
        "top_risk_areas": top_risk_areas,
    }


def scrub_key_concerns() -> dict:
    """Rewrite all stored key_concerns using Claude Haiku to remove party/employer names."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT session_id, key_concerns FROM contracts WHERE key_concerns IS NOT NULL"
        ).fetchall()

    processed = 0
    updated = 0
    errors = 0

    for row in rows:
        processed += 1
        try:
            concerns = json.loads(row["key_concerns"] or "[]")
        except Exception:
            continue
        if not concerns:
            continue

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": (
                        "Rewrite each of these PBM contract concern labels as a generic category label. "
                        "Remove any specific company names, employer names, plan sponsor names, or organization names. "
                        "Keep the concern's meaning intact but make it fully generic — no proper nouns referring to any company or entity. "
                        "Return ONLY a JSON array of strings, no explanation, no markdown.\n\n"
                        f"Concerns: {json.dumps(concerns)}"
                    ),
                }],
            )
            cleaned = json.loads(response.content[0].text.strip())
            if isinstance(cleaned, list) and len(cleaned) > 0:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "UPDATE contracts SET key_concerns = ? WHERE session_id = ?",
                        (json.dumps(cleaned), row["session_id"]),
                    )
                updated += 1
        except Exception as e:
            logging.warning(f"scrub_key_concerns: failed for {row['session_id']}: {e}")
            errors += 1

    return {"processed": processed, "updated": updated, "errors": errors}


# ── Queries ───────────────────────────────────────────────────────────────────

def count_leads() -> int:
    """Return the total number of stored leads."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


def get_contract_list(page: int = 1, limit: int = 20) -> dict:
    """Return a paginated list of contracts from the library, newest first."""
    offset = (page - 1) * limit
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        rows = conn.execute(
            "SELECT session_id, pbm_name, uploaded_at, overall_grade, key_concerns "
            "FROM contracts ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    contracts = []
    for row in rows:
        try:
            concerns = json.loads(row["key_concerns"] or "[]")[:2]
        except Exception:
            concerns = []
        contracts.append({
            "session_id": row["session_id"],
            "pbm_name": row["pbm_name"],
            "uploaded_at": row["uploaded_at"],
            "overall_grade": row["overall_grade"],
            "key_concerns": concerns,
        })

    return {
        "contracts": contracts,
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
    }


def get_contract_by_session(session_id: str) -> Optional[dict]:
    """Return the full contract row for a session_id, or None if not found."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM contracts WHERE session_id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def save_broker_profile(broker_name: str, firm_name: str, email: str, phone: str,
                        logo_path: Optional[str] = None) -> None:
    """Upsert the single broker profile row."""
    updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM broker_profile LIMIT 1").fetchone()
        if row:
            conn.execute(
                """UPDATE broker_profile
                   SET broker_name=?, firm_name=?, email=?, phone=?, logo_path=?, updated_at=?
                   WHERE id=?""",
                (broker_name, firm_name, email, phone, logo_path, updated_at, row[0]),
            )
        else:
            conn.execute(
                """INSERT INTO broker_profile
                   (broker_name, firm_name, email, phone, logo_path, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (broker_name, firm_name, email, phone, logo_path, updated_at),
            )
        conn.commit()


def get_broker_profile() -> Optional[dict]:
    """Return the broker profile dict or None if not configured."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM broker_profile LIMIT 1").fetchone()
    return dict(row) if row else None


def export_leads_csv() -> str:
    """Return all leads as a UTF-8 CSV string, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY submitted_at DESC"
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Submitted At (UTC)", "First Name", "Last Name",
        "Email", "Phone", "Company", "Grade", "Key Concerns", "Session ID",
    ])
    for row in rows:
        # Flatten key_concerns JSON array to a readable string
        try:
            concerns = "; ".join(json.loads(row["key_concerns"] or "[]"))
        except Exception:
            concerns = row["key_concerns"] or ""

        writer.writerow([
            row["id"],
            row["submitted_at"],
            row["first_name"],
            row["last_name"],
            row["email"],
            row["phone"],
            row["company"],
            row["overall_grade"],
            concerns,
            row["session_id"],
        ])

    return output.getvalue()
