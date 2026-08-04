"""
FastAPI backend for the investor intelligence dashboard.

Run with:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET  /api/reports              List all ingested reports
    GET  /api/reports/{id}/kpis    KPIs for a specific report
    POST /api/reports              Upload a PDF, ingest it, extract KPIs
    POST /api/chat                 Ask a question over ingested reports
"""
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chat import answer as rag_answer  # noqa: E402
from db import get_connection  # noqa: E402
from extract_kpis import extract_kpis_from_text, store_kpis  # noqa: E402
from ingest import ingest  # noqa: E402

app = FastAPI(title="Investor Intelligence API")

# Dev-friendly CORS: allow the static frontend served from any local port.
# Tighten this to a specific origin before deploying anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


@app.get("/api/reports")
def list_reports():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename, uploaded_at FROM reports ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "filename": r[1], "uploaded_at": r[2].isoformat()} for r in rows
    ]


@app.get("/api/reports/{report_id}/kpis")
def get_kpis(report_id: int):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT revenue, net_income, operating_income, cash_flow_from_operations,
               total_assets, total_liabilities, top_risk_factors, top_growth_drivers
        FROM kpis WHERE report_id = %s
        ORDER BY extracted_at DESC LIMIT 1
        """,
        (report_id,),
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="No KPIs found for this report")
    keys = [
        "revenue", "net_income", "operating_income", "cash_flow_from_operations",
        "total_assets", "total_liabilities", "top_risk_factors", "top_growth_drivers",
    ]
    return dict(zip(keys, row))


@app.post("/api/reports")
async def upload_report(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        report_id, markdown_text = ingest(tmp_path, display_filename=file.filename)
        kpis = extract_kpis_from_text(markdown_text)
        conn = get_connection()
        store_kpis(conn, report_id, kpis)
        conn.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"report_id": report_id, "kpis": kpis}


@app.post("/api/chat")
def chat(req: ChatRequest):
    return {"answer": rag_answer(req.question)}
