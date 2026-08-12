"""
KPI extraction.

Usage:
    python src/extract_kpis.py path/to/report.pdf

Runs the full ingest pipeline first (so chunks + embeddings also get stored),
then asks the LLM to extract structured KPIs from the full markdown text
and writes them to the kpis table.
"""
import json
import sys

from dotenv import load_dotenv
from google import genai

from db import get_connection
from ingest import ingest

load_dotenv()

# genai.Client() automatically reads the GEMINI_API_KEY environment variable
client = genai.Client()
MODEL_NAME = "gemini-3.6-flash"

KPI_PROMPT = """You are a financial analyst extracting KPIs from an investor report.
Read the report below and extract the requested fields. Use null for any
figure not clearly stated in the report. Numbers should be plain numbers
(no currency symbols or commas). Report text follows:

---
{report_text}
---
"""

KPI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": ["string", "null"]},
        "fiscal_year": {"type": ["string", "null"]},
        "revenue": {"type": ["number", "null"]},
        "net_income": {"type": ["number", "null"]},
        "operating_income": {"type": ["number", "null"]},
        "cash_flow_from_operations": {"type": ["number", "null"]},
        "total_assets": {"type": ["number", "null"]},
        "total_liabilities": {"type": ["number", "null"]},
        "top_risk_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "top_growth_drivers": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": [
        "company_name", "fiscal_year", "revenue", "net_income", "operating_income",
        "cash_flow_from_operations", "total_assets", "total_liabilities",
        "top_risk_factors", "top_growth_drivers",
    ],
}


def extract_kpis_from_text(markdown_text: str) -> dict:
    prompt = KPI_PROMPT.format(report_text=markdown_text[:100_000])
    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": KPI_RESPONSE_SCHEMA,
        },
    )
    return json.loads(interaction.output_text)


def store_kpis(conn, report_id: int, kpis: dict):
    conn.execute(
        """
        INSERT INTO kpis (
            report_id, company_name, fiscal_year, revenue, net_income, operating_income,
            cash_flow_from_operations, total_assets, total_liabilities,
            top_risk_factors, top_growth_drivers
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            report_id,
            kpis.get("company_name"),
            kpis.get("fiscal_year"),
            kpis.get("revenue"),
            kpis.get("net_income"),
            kpis.get("operating_income"),
            kpis.get("cash_flow_from_operations"),
            kpis.get("total_assets"),
            kpis.get("total_liabilities"),
            kpis.get("top_risk_factors", []),
            kpis.get("top_growth_drivers", []),
        ),
    )


def run(pdf_path: str):
    report_id, markdown_text = ingest(pdf_path)

    print("[extract] Asking Gemini for structured KPIs...")
    kpis = extract_kpis_from_text(markdown_text)
    print(json.dumps(kpis, indent=2))

    conn = get_connection()
    store_kpis(conn, report_id, kpis)
    conn.close()
    print(f"Stored KPIs for report_id={report_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/extract_kpis.py path/to/report.pdf")
        sys.exit(1)
    run(sys.argv[1])
