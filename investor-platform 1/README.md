# AI-powered investor intelligence platform (Azure-free)

Local/self-hosted version of the architecture: Postgres + pgvector does double
duty as both the vector store and the structured KPI database.

## Stack

| Piece | Tool |
|---|---|
| PDF -> markdown | `pymupdf4llm` |
| Chunking | `langchain-text-splitters` |
| Embeddings | `sentence-transformers` (bge-small, local, free) |
| Vector store + KPI DB | Postgres + pgvector (one instance) |
| Extraction + chat | Google Gemini API (free tier — no credit card needed) |

## Setup

1. Start Postgres:
   ```bash
   docker compose up -d
   ```
   This creates the `investor_platform` database and runs `db/schema.sql`
   automatically on first boot.

2. Install Python dependencies:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your Gemini API key. Get a free
   key (no credit card required) at https://ai.google.dev — click "Get API
   key" and copy it into `GEMINI_API_KEY`.

## Usage

Ingest a report (PDF -> markdown -> chunks -> embeddings -> Postgres):
```bash
python src/ingest.py data/uploads/report.pdf
```

Extract structured KPIs (runs ingest, then asks the LLM to fill the schema):
```bash
python src/extract_kpis.py data/uploads/report.pdf
```

Ask a question over ingested reports (RAG):
```bash
python src/chat.py "What was the company's total revenue?"
```

## Dashboard (backend + frontend)

Start the API (from the project root, with your venv active):
```bash
uvicorn api.main:app --reload --port 8000
```

Serve the frontend as static files (separate terminal):
```bash
cd frontend
python -m http.server 5500
```

Open **http://localhost:5500** in your browser. You can:
- Upload a 10-K PDF directly from the page (runs the full ingest + KPI
  extraction pipeline)
- Switch between ingested reports and see their KPI ledger
- Ask questions in the chat panel (RAG over whatever's been ingested)

The API docs (interactive, auto-generated) are at **http://localhost:8000/docs**
once the backend is running.

## Next steps

- The upload endpoint runs ingest + extraction synchronously, so a large PDF
  will make the browser wait. For anything beyond a demo, move this to a
  background task (FastAPI's `BackgroundTasks`, or a proper queue like Celery)
  and poll for status instead.
- Chat currently searches across all ingested reports at once. Add a
  `report_id` filter to `/api/chat` and the frontend if you want per-report
  Q&A instead.
- CORS is wide open (`allow_origins=["*"]`) for local dev — tighten this to
  your actual frontend origin before deploying anywhere real.
