"""
Lead capture service.
Saves contact info + analysis grade to a local SQLite database.
Optionally sends an email notification via SMTP on each new lead.
"""

import csv
import io
import json
import os
import smtplib
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import ContactInfo, PBMAnalysisReport

# leads.db lives at backend/leads.db (one level above this services/ directory)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "leads.db")


# ── Database setup ────────────────────────────────────────────────────────────

def init_db():
    """Create the leads table if it doesn't already exist."""
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

    # Email notification — skip silently if not configured
    try:
        _send_notification(contact, analysis, submitted_at)
    except Exception:
        pass


# ── Email notification ────────────────────────────────────────────────────────

def _send_notification(contact: ContactInfo, analysis: PBMAnalysisReport,
                       submitted_at: str):
    """
    Send an HTML email to NOTIFY_EMAIL using SMTP credentials from .env.
    Required env vars: NOTIFY_EMAIL, SMTP_USER, SMTP_PASS
    Optional:          SMTP_HOST (default: smtp.gmail.com), SMTP_PORT (default: 587)
    """
    notify_email = os.getenv("NOTIFY_EMAIL", "").strip()
    smtp_host    = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port    = int(os.getenv("SMTP_PORT", "587"))
    smtp_user    = os.getenv("SMTP_USER", "").strip()
    smtp_pass    = os.getenv("SMTP_PASS", "").strip()

    if not (notify_email and smtp_user and smtp_pass):
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
          ⚕ New PBM Analysis Lead
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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = (f"New PBM Lead: {contact.first_name} {contact.last_name}"
                      f" — {contact.company} (Grade {analysis.overall_grade})")
    msg["From"] = smtp_user
    msg["To"]   = notify_email
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, notify_email, msg.as_string())


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
