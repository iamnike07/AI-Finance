<div align="center">
          
# 💹 Binance — AI-Powered Finance Platform

**Real-time corporate insights, KPI extraction, and intelligent financial analysis**

<img width="1543" height="784" alt="image" src="https://github.com/user-attachments/assets/58a1e333-a436-4d18-aad9-d5c21be00a24" />

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini_AI-3.6_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_+_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Finnhub](https://img.shields.io/badge/Finnhub-Real--Time_Data-2ECC71?style=for-the-badge)](https://finnhub.io)

</div>

---

## 🎯 Overview

Binance is an end-to-end AI finance platform that lets you **upload SEC 10-K filings**, automatically **extract key financial KPIs**, and **chat with an AI analyst** that has deep context on your documents — plus access to **real-time stock prices and breaking news** via Finnhub.

### ✨ Key Features

| Feature | Description |
|---|---|
| 📄 **PDF Ingestion** | Upload 10-K filings → automatic Markdown conversion, semantic chunking, and vector embedding |
| 📊 **KPI Extraction** | AI-powered extraction of Revenue, Net Income, Operating Income, Cash Flow, Assets, Liabilities, Risk Factors & Growth Drivers |
| 📈 **Interactive Charts** | Bar and Radar chart visualizations for comparing KPI metrics (Chart.js) |
| 🤖 **AI Chat Analyst** | RAG-powered Q&A with hybrid retrieval (dense vectors + BM25 + Reciprocal Rank Fusion) |
| 💬 **Conversation Memory** | Multi-turn chat with full context retention via Gemini's Interactions API |
| 📡 **Real-Time Market Data** | Live stock quotes and breaking company news via Finnhub API |
| 🎨 **Premium UI** | Glassmorphism, animated KPI counters, typing indicators, markdown chat rendering |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vanilla JS)                │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  KPI Cards   │  │  Chart.js    │  │  AI Chat      │  │
│  │  + Counters  │  │  Bar / Radar │  │  + Markdown   │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
└─────────┼─────────────────┼──────────────────┼──────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI REST API (:8001)                 │
│                                                          │
│  POST /api/reports     → Ingest PDF                      │
│  GET  /api/reports     → List reports                    │
│  GET  /api/reports/:id/kpis → Get KPIs                   │
│  POST /api/chat        → AI Q&A                          │
└──────┬──────────────────┬───────────────────┬────────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌─────────────┐  ┌────────────────┐  ┌────────────────────┐
│  PostgreSQL │  │  Gemini 3.6    │  │  Finnhub API       │
│  + pgvector │  │  Flash (RAG +  │  │  • Stock Quotes    │
│  • chunks   │  │   Tool Calling │  │  • Company News    │
│  • reports  │  │   + Memory)    │  │                    │
│  • kpis     │  └────────────────┘  └────────────────────┘
└─────────────┘
```

### Hybrid RAG Pipeline

```
User Query
    │
    ├──► Dense Vector Search (BAAI/bge-small-en-v1.5 → pgvector cosine)
    │        → Top 20 candidates
    │
    ├──► Sparse Keyword Search (BM25Okapi)
    │        → Top 20 candidates
    │
    └──► Reciprocal Rank Fusion (k=3)
             → Top 5 final chunks → Gemini context
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Docker** (for PostgreSQL + pgvector)
- **API Keys**: [Gemini](https://aistudio.google.com/apikey) + [Finnhub](https://finnhub.io/register) (free tier)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/investor-platform.git
cd investor-platform
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://investor:investor_dev_password@localhost:5433/investor_platform
GEMINI_API_KEY=your_gemini_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here
```

### 3. Start the Database

```bash
docker compose up -d
```

This spins up PostgreSQL 16 with the pgvector extension on port **5433**, and automatically runs the schema migration.

### 4. Install Dependencies

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 5. Run the Server

```bash
uvicorn api.main:app --reload --port 8001
```

Open **http://localhost:8001** in your browser.

---

## 📁 Project Structure

```
investor-platform/
├── api/
│   └── main.py              # FastAPI app — routes, CORS, static mount
├── src/
│   ├── chat.py              # RAG hybrid retrieval + Gemini chat + tool calling
│   ├── db.py                # PostgreSQL connection + pgvector registration
│   ├── ingest.py            # PDF → Markdown → chunks → embeddings → DB
│   └── tools.py             # Finnhub API wrappers (stock price, news)
├── frontend/
│   ├── index.html           # Dashboard UI with Chart.js
│   ├── app.js               # Interactive frontend logic
│   ├── style.css            # Glassmorphism theme + animations
│   └── finance-bg.jpg       # Background asset
├── db/
│   └── schema.sql           # PostgreSQL schema (reports, chunks, kpis)
├── data/                    # Uploaded PDF storage
├── docker-compose.yml       # PostgreSQL + pgvector container
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata
└── .env                     # API keys (not committed)
```

---

## 🔌 API Reference

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/reports` | Upload a 10-K PDF — triggers ingestion pipeline (parse → chunk → embed → extract KPIs) |
| `GET` | `/api/reports` | List all ingested reports with company name and fiscal year |
| `GET` | `/api/reports/{id}/kpis` | Get extracted KPIs for a specific report |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Ask questions about ingested reports with optional company filter |

**Request body:**
```json
{
  "question": "What are Apple's main risk factors?",
  "report_id": 3,
  "previous_interaction_id": "optional-for-follow-ups"
}
```

**Response:**
```json
{
  "answer": "Based on Apple's 10-K filing...",
  "interaction_id": "abc123-for-threading"
}
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML / CSS / JavaScript | Dashboard UI with glassmorphism design |
| **Charts** | Chart.js 4.4 | Interactive bar & radar KPI visualizations |
| **API** | FastAPI + Uvicorn | REST API server |
| **LLM** | Google Gemini 3.6 Flash | KPI extraction, chat, tool calling |
| **Embeddings** | BAAI/bge-small-en-v1.5 | 384-dim sentence embeddings (local) |
| **Vector DB** | PostgreSQL 16 + pgvector | Cosine similarity vector search |
| **Sparse Search** | rank-bm25 | BM25Okapi keyword ranking |
| **PDF Parsing** | PyMuPDF4LLM | PDF → structured Markdown |
| **Chunking** | LangChain Text Splitters | Markdown-aware semantic chunking |
| **Market Data** | Finnhub API | Real-time stock quotes & company news |

---

## 💡 Usage

### Upload a 10-K Filing

Click the **Upload 10-K** button in the top-right corner and select a PDF. The system will:
1. Convert the PDF to structured Markdown
2. Split into semantic chunks (800 tokens, 100 overlap)
3. Generate vector embeddings using `bge-small-en-v1.5`
4. Store chunks + embeddings in PostgreSQL/pgvector
5. Extract financial KPIs via Gemini
6. Display results on the dashboard

### Chat with AI Analyst

Use the chat sidebar to ask questions like:
- *"What drove revenue growth this year?"*
- *"Compare Apple's risk factors to Tesla's"*
- *"What's the current stock price of AAPL?"*
- *"Show me recent news about Tesla"*

The AI has access to your uploaded documents **and** real-time market data.

---

## 📝 License

This project is for educational and personal use.

---

<div align="center">

**Built using Gemini AI, FastAPI, and PostgreSQL**

</div>
