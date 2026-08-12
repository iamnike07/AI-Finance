-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- One row per uploaded report
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Semantic chunks + embeddings for RAG retrieval
-- 384 dims matches bge-small; change to 1536 if you use OpenAI text-embedding-3-small
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Structured KPIs extracted by the LLM, one row per report
CREATE TABLE IF NOT EXISTS kpis (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    company_name TEXT,
    fiscal_year TEXT,
    revenue NUMERIC,
    net_income NUMERIC,
    operating_income NUMERIC,
    cash_flow_from_operations NUMERIC,
    total_assets NUMERIC,
    total_liabilities NUMERIC,
    top_risk_factors TEXT[],
    top_growth_drivers TEXT[],
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
