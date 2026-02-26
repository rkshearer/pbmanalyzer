"""
PBM Contract Analyzer — FastAPI Backend
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from services.analyzer import analyze_contract_background
from services.document import extract_text
from services.knowledge import (
    get_knowledge_status,
    start_background_updater,
    update_knowledge_base,
)
from services.leads import count_leads, export_leads_csv, init_db, save_lead
from services.models import ContactInfo, SessionData, SessionStatus
from services.report_gen import generate_pdf_report

load_dotenv()

_DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(__file__))
REPORTS_DIR = os.path.join(_DATA_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

sessions: dict[str, SessionData] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize leads database and start background knowledge updater
    init_db()
    start_background_updater()
    yield


app = FastAPI(title="PBM Contract Analyzer", lifespan=lifespan)

_origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
_frontend_url = os.getenv("FRONTEND_URL", "").strip()
if _frontend_url:
    _origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Analysis Endpoints ────────────────────────────────────────────────────────

async def _run_analysis(session_id: str, text: str):
    """Run analysis in thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, analyze_contract_background, sessions, session_id, text
    )


@app.post("/api/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith((".pdf", ".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must not exceed 50MB.")

    try:
        text = extract_text(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in the file.")

    session_id = str(uuid.uuid4())
    sessions[session_id] = SessionData()

    asyncio.create_task(_run_analysis(session_id, text))

    return {"session_id": session_id}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = sessions[session_id]
    return {
        "status": session.status,
        "status_message": session.status_message,
        "error_message": session.error_message,
    }


# ── Report Endpoints ──────────────────────────────────────────────────────────

class ContactFormData(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    company: str


@app.post("/api/report/{session_id}")
async def submit_contact_and_get_report(session_id: str, contact_data: ContactFormData):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = sessions[session_id]

    if session.status != SessionStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not complete yet. Current status: {session.status}",
        )

    contact_info = ContactInfo(**contact_data.model_dump())
    session.contact_info = contact_info

    pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")
    try:
        generate_pdf_report(session.analysis_result, contact_info, pdf_path)
        session.pdf_path = pdf_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

    # Save lead to SQLite + fire email notification in background thread
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(
        loop.run_in_executor(
            None, save_lead, contact_info, session.analysis_result, session_id
        )
    )

    return {
        "success": True,
        "download_url": f"/api/download/{session_id}",
        "analysis": session.analysis_result.model_dump(),
    }


@app.get("/api/download/{session_id}")
async def download_report(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = sessions[session_id]

    if not session.pdf_path or not os.path.exists(session.pdf_path):
        raise HTTPException(
            status_code=404,
            detail="Report PDF not found. Please submit the contact form first.",
        )

    contact = session.contact_info
    if contact:
        safe_company = "".join(c for c in contact.company if c.isalnum() or c in " _-")[:30].strip()
        filename = f"PBM_Analysis_{contact.last_name}_{safe_company}.pdf"
    else:
        filename = "PBM_Analysis_Report.pdf"

    return FileResponse(
        session.pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


# ── Leads Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/leads/export")
async def export_leads(key: str = Query(..., description="Export secret key")):
    """
    Download all leads as a CSV file.
    Protected by LEADS_EXPORT_KEY in .env — pass it as ?key=YOUR_KEY.
    """
    export_key = os.getenv("LEADS_EXPORT_KEY", "").strip()
    if not export_key:
        raise HTTPException(status_code=503, detail="Leads export not configured (set LEADS_EXPORT_KEY in .env).")
    if key != export_key:
        raise HTTPException(status_code=403, detail="Invalid export key.")

    csv_content = export_leads_csv()
    filename = f"pbm_leads_{__import__('datetime').datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Knowledge Base Endpoints ──────────────────────────────────────────────────

@app.get("/api/knowledge/status")
async def knowledge_status():
    return get_knowledge_status()


@app.post("/api/knowledge/update")
async def trigger_knowledge_update():
    """Manually trigger a knowledge base update from public sources."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, update_knowledge_base)
    return {"success": True, **result}


# ── Debug Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/debug/email")
async def debug_email():
    """Test Resend email configuration and return result. Remove after debugging."""
    import requests as _requests
    notify_email = os.getenv("NOTIFY_EMAIL", "").strip()
    api_key      = os.getenv("RESEND_API_KEY", "").strip()
    from_address = os.getenv("NOTIFY_FROM", "PBM Analyzer <onboarding@resend.dev>")

    config = {
        "NOTIFY_EMAIL_set": bool(notify_email),
        "RESEND_API_KEY_set": bool(api_key),
        "RESEND_API_KEY_length": len(api_key),
        "from_address": from_address,
    }

    try:
        resp = _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_address,
                "to": [notify_email],
                "subject": "PBM Analyzer — Email Test",
                "html": "<p>SMTP config is working via Resend.</p>",
            },
            timeout=10,
        )
        detail = resp.json() if resp.content else {}
        if not resp.ok:
            return {"status": "error", "http_status": resp.status_code, "detail": detail, **config}
        return {"status": "ok", "message": f"Test email sent to {notify_email}", **config}
    except Exception as exc:
        return {"status": "error", "error": str(exc), **config}


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "sessions_active": len(sessions),
        "leads_captured": count_leads(),
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
