"""
PBM Contract Analyzer — FastAPI Backend
"""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import anthropic as _anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from services.analyzer import analyze_contract_background
from services.document import extract_text
from services.knowledge import (
    get_knowledge_status,
    start_background_updater,
    update_knowledge_base,
)
from services.leads import (
    count_leads,
    export_leads_csv,
    get_contract_by_session,
    get_contract_list,
    init_db,
    save_lead,
)
from services.models import ContactInfo, PBMAnalysisReport, SessionData, SessionStatus
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


# ── Negotiation Letter ────────────────────────────────────────────────────────

@app.post("/api/negotiate/{session_id}")
async def generate_negotiation_letter_endpoint(session_id: str):
    """Generate a negotiation letter DOCX based on the analysis for this session."""
    from services.negotiate import generate_negotiation_letter

    analysis = _get_analysis(session_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Complete the analysis first.")

    loop = asyncio.get_event_loop()
    docx_bytes = await loop.run_in_executor(None, generate_negotiation_letter, analysis)

    safe_name = "".join(
        c for c in (analysis.contract_overview.parties or "PBM") if c.isalnum() or c in " _-"
    )[:30].strip()
    filename = f"PBM_Negotiation_Letter_{safe_name}.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Contract Library ──────────────────────────────────────────────────────────

@app.get("/api/library")
async def get_library(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Paginated list of all analyzed contracts, newest first."""
    return get_contract_list(page=page, limit=limit)


@app.get("/api/session/{session_id}/analysis")
async def get_stored_analysis(session_id: str):
    """Re-hydrate a past analysis from the contract library."""
    # Check live session first
    if session_id in sessions and sessions[session_id].status == SessionStatus.COMPLETE:
        sess = sessions[session_id]
        has_pdf = bool(sess.pdf_path and os.path.exists(sess.pdf_path))
        return {
            "analysis": sess.analysis_result.model_dump(),
            "download_url": f"/api/download/{session_id}" if has_pdf else None,
            "pbm_name": sess.analysis_result.contract_overview.parties,
            "uploaded_at": None,
        }

    # Fall back to database
    row = get_contract_by_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found.")

    analysis_json = row.get("analysis_json")
    if not analysis_json:
        raise HTTPException(
            status_code=404,
            detail="Full analysis not available for this contract (pre-dates history feature).",
        )

    analysis = PBMAnalysisReport(**json.loads(analysis_json))

    # Restore in-memory session so download/chat/negotiate still work
    sessions[session_id] = SessionData()
    sessions[session_id].status = SessionStatus.COMPLETE
    sessions[session_id].analysis_result = analysis
    pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")
    if os.path.exists(pdf_path):
        sessions[session_id].pdf_path = pdf_path

    has_pdf = bool(sessions[session_id].pdf_path)
    return {
        "analysis": analysis.model_dump(),
        "download_url": f"/api/download/{session_id}" if has_pdf else None,
        "pbm_name": row.get("pbm_name"),
        "uploaded_at": row.get("uploaded_at"),
    }


# ── Contract Comparison ───────────────────────────────────────────────────────

@app.get("/api/compare")
async def compare_contracts(
    a: str = Query(..., description="Session ID of contract A"),
    b: str = Query(..., description="Session ID of contract B"),
):
    """Return side-by-side comparison data for two contracts from the library."""
    row_a = get_contract_by_session(a)
    row_b = get_contract_by_session(b)
    if not row_a:
        raise HTTPException(status_code=404, detail=f"Contract {a} not found.")
    if not row_b:
        raise HTTPException(status_code=404, detail=f"Contract {b} not found.")

    def _to_compare(row: dict) -> dict:
        try:
            concerns = json.loads(row.get("key_concerns") or "[]")
        except Exception:
            concerns = []
        return {
            "session_id": row["session_id"],
            "pbm_name": row.get("pbm_name") or "Unknown PBM",
            "uploaded_at": row.get("uploaded_at", ""),
            "overall_grade": row.get("overall_grade", "?"),
            "brand_retail": row.get("brand_retail") or "N/A",
            "generic_retail": row.get("generic_retail") or "N/A",
            "specialty": row.get("specialty") or "N/A",
            "retail_dispensing_fee": row.get("retail_dispensing_fee") or "N/A",
            "admin_fees": row.get("admin_fees") or "N/A",
            "rebate_guarantee": row.get("rebate_guarantee") or "N/A",
            "key_concerns": concerns,
        }

    return {"a": _to_compare(row_a), "b": _to_compare(row_b)}


# ── Interactive Q&A ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


@app.post("/api/chat/{session_id}")
async def chat_with_contract(session_id: str, request: ChatRequest):
    """Stream an answer to a broker question about the contract."""
    row = get_contract_by_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found in library.")

    contract_text = (row.get("contract_text") or "")[:70000]
    analysis_summary = ""
    if row.get("analysis_json"):
        try:
            data = json.loads(row["analysis_json"])
            analysis_summary = (
                f"Grade: {data.get('overall_grade', '?')}\n"
                f"Key Concerns: {', '.join(data.get('key_concerns', []))}\n"
                f"Negotiation Guidance (first 3): "
                + "; ".join(data.get("negotiation_guidance", [])[:3])
            )
        except Exception:
            pass

    system = (
        "You are an expert PBM contract analyst. "
        "Answer the broker's question specifically about the contract text provided. "
        "Be concise and cite specific contract language when relevant. "
        "If the answer cannot be found in the contract, say so clearly.\n\n"
        f"CONTRACT ANALYSIS SUMMARY:\n{analysis_summary}\n\n"
        f"CONTRACT TEXT:\n{contract_text}"
    )

    messages = []
    for msg in request.history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request.question})

    async def generate():
        try:
            async_client = _anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            async with async_client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2000,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── RFP Export ────────────────────────────────────────────────────────────────

@app.post("/api/rfp/{session_id}")
async def generate_rfp_export_endpoint(session_id: str):
    """Generate a prioritized RFP question bank XLSX for the given analysis."""
    from services.rfp import generate_rfp_export

    analysis = _get_analysis(session_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Complete the analysis first.")

    loop = asyncio.get_event_loop()
    xlsx_bytes = await loop.run_in_executor(None, generate_rfp_export, analysis)

    grade = analysis.overall_grade
    filename = f"PBM_RFP_Questions_Grade{grade}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "sessions_active": len(sessions),
        "leads_captured": count_leads(),
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_analysis(session_id: str) -> Optional[PBMAnalysisReport]:
    """Return the PBMAnalysisReport for a session, checking memory then the DB."""
    if session_id in sessions and sessions[session_id].status == SessionStatus.COMPLETE:
        return sessions[session_id].analysis_result

    row = get_contract_by_session(session_id)
    if row and row.get("analysis_json"):
        analysis = PBMAnalysisReport(**json.loads(row["analysis_json"]))
        # Restore session so subsequent calls (download, chat) work without DB hit
        sessions[session_id] = SessionData()
        sessions[session_id].status = SessionStatus.COMPLETE
        sessions[session_id].analysis_result = analysis
        pdf_path = os.path.join(REPORTS_DIR, f"{session_id}.pdf")
        if os.path.exists(pdf_path):
            sessions[session_id].pdf_path = pdf_path
        return analysis

    return None
