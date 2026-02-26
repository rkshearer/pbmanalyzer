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
               key_concerns, contract_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()


def get_library_benchmarks() -> dict:
    """Return aggregate statistics from the contract library for prompt enrichment and comparison cards."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT overall_grade, brand_retail, generic_retail, specialty, key_concerns FROM contracts"
        ).fetchall()

    count = len(rows)
    if count == 0:
        return {"contracts_count": 0}

    grade_distribution: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    grades: list[str] = []
    brand_retails: list[str] = []
    generic_retails: list[str] = []
    specialties: list[str] = []
    concern_counts: dict[str, int] = {}

    for row in rows:
        grade = row["overall_grade"]
        if grade in grade_distribution:
            grade_distribution[grade] += 1
        grades.append(grade)
        brand_retails.append(row["brand_retail"] or "")
        generic_retails.append(row["generic_retail"] or "")
        specialties.append(row["specialty"] or "")
        try:
            for concern in json.loads(row["key_concerns"] or "[]"):
                concern_counts[concern] = concern_counts.get(concern, 0) + 1
        except Exception:
            pass

    def _avg_str(strings: list[str]) -> str:
        vals = [_parse_pct(s) for s in strings]
        vals = [v for v in vals if v is not None]
        if not vals:
            return "N/A"
        return f"AWP-{sum(vals) / len(vals):.1f}%"

    top_concerns = sorted(concern_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "contracts_count": count,
        "grade_distribution": grade_distribution,
        "grades": grades,
        "avg_brand_retail": _avg_str(brand_retails),
        "avg_generic_retail": _avg_str(generic_retails),
        "avg_specialty": _avg_str(specialties),
        "top_concerns": top_concerns,
    }


# ── Queries ───────────────────────────────────────────────────────────────────

def count_leads() -> int:
    """Return the total number of stored leads."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


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
