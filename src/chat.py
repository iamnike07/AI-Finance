"""
RAG chat over ingested reports, with hybrid retrieval, live market tools,
and conversation memory.

Usage:
    python src/chat.py "What was total revenue last quarter?"
    python src/chat.py                      # interactive mode, remembers context

Three things work together here:

1. Hybrid retrieval (dense + BM25 + RRF) — see module docstring detail
   below on retrieve().
2. Tool use — get_stock_price / get_company_news (src/tools.py) let the
   model answer live-market questions that the filing obviously can't
   cover. Gemini decides on its own whether a question needs a tool.
3. Conversation memory — the Interactions API stores conversation state
   server-side. We just thread `previous_interaction_id` through each
   call; we don't maintain history ourselves. This is what lets a
   follow-up like "what about the year before that?" resolve correctly —
   the model still has the whole prior exchange in view, even though our
   retrieval step below only searches on the raw follow-up text.
"""
import re
import sys

from dotenv import load_dotenv
from google import genai

from db import get_connection
from ingest import get_embedding_model
from tools import get_company_news, get_stock_price
from rank_bm25 import BM25Okapi

load_dotenv()

client = genai.Client()
MODEL_NAME = "gemini-3.6-flash"

TOOLS_BY_NAME = {"get_stock_price": get_stock_price, "get_company_news": get_company_news}

# The installed google-genai SDK (2.16.0) validates each tool against a strict
# schema requiring an explicit {"type": "function", ...} shape — passing bare
# Python callables directly (as some docs/examples suggest) fails Pydantic
# validation before the request is even sent. Declared explicitly here,
# verified against the SDK's actual request model rather than assumed.
TOOLS = [
    {
        "type": "function",
        "name": "get_stock_price",
        "description": (
            "Get the latest real-time price for a US-listed stock ticker. "
            "Use this for current/live price questions, not historical filing figures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "The stock ticker symbol, e.g. AAPL or MSFT."},
            },
            "required": ["ticker"],
        },
    },
    {
        "type": "function",
        "name": "get_company_news",
        "description": "Get recent news headlines for a company by ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "The stock ticker symbol, e.g. AAPL or MSFT."},
                "days": {"type": "integer", "description": "How many days back to search. Defaults to 7."},
            },
            "required": ["ticker"],
        },
    },
]

TOP_K = 5
CANDIDATE_K = 20
RRF_K = 3   # see prior tuning note — 60 (the textbook default) over-smooths at this scale

ANSWER_PROMPT = """Answer the user's question. Filing context is provided below when relevant.

If the question is about current/live stock price or recent news/developments,
use the available tools instead of the filing context — the filing reflects
a point in time, not live markets. If neither the filing context nor the
tools answer the question, say so plainly.

Filing context:
{context}

Question: {question}
"""

_TOKEN_RE = re.compile(r"[A-Za-z0-9$%.]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _load_all_chunks(report_id: int | None = None) -> list[tuple[int, str]]:
    conn = get_connection()
    if report_id is not None:
        rows = conn.execute(
            "SELECT id, content FROM chunks WHERE report_id = %s", (report_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, content FROM chunks").fetchall()
    conn.close()
    return rows


def _vector_search_ids(question: str, top_k: int, report_id: int | None = None) -> list[int]:
    model = get_embedding_model()
    query_embedding = model.encode([question], normalize_embeddings=True)[0].tolist()

    conn = get_connection()
    if report_id is not None:
        rows = conn.execute(
            """
            SELECT id FROM chunks WHERE report_id = %s
            ORDER BY embedding <=> %s::vector LIMIT %s
            """,
            (report_id, query_embedding, top_k),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id FROM chunks
            ORDER BY embedding <=> %s::vector LIMIT %s
            """,
            (query_embedding, top_k),
        ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def _bm25_search_ids(question: str, all_chunks: list[tuple[int, str]], top_k: int) -> list[int]:
    if not all_chunks:
        return []
    ids = [c[0] for c in all_chunks]
    corpus_tokens = [_tokenize(c[1]) for c in all_chunks]
    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(_tokenize(question))
    ranked = sorted(zip(ids, scores), key=lambda pair: pair[1], reverse=True)
    return [chunk_id for chunk_id, _ in ranked[:top_k]]


def _reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda p: p[1], reverse=True)]


def retrieve(question: str, top_k: int = TOP_K, report_id: int | None = None) -> list[str]:
    all_chunks = _load_all_chunks(report_id)
    if not all_chunks:
        return []
    lookup = dict(all_chunks)

    vector_ids = _vector_search_ids(question, CANDIDATE_K, report_id)
    bm25_ids = _bm25_search_ids(question, all_chunks, CANDIDATE_K)

    fused_ids = _reciprocal_rank_fusion([vector_ids, bm25_ids])[:top_k]
    return [lookup[cid] for cid in fused_ids if cid in lookup]


def _resolve_function_calls(interaction):
    """Loop until the model stops asking for tool calls and returns text.
    Handles multiple parallel function calls in a single turn."""
    function_calls = [o for o in (interaction.steps or []) if getattr(o, "type", None) == "function_call"]

    while function_calls:
        results = []
        for fc in function_calls:
            fn = TOOLS_BY_NAME.get(fc.name)
            try:
                result = fn(**fc.arguments) if fn else {"error": f"Unknown tool '{fc.name}'"}
            except Exception as e:  # tool failures shouldn't crash the chat
                result = {"error": str(e)}
            results.append({
                "type": "function_result",
                "call_id": fc.id,
                "name": fc.name,
                "result": result,
            })

        interaction = client.interactions.create(
            model=MODEL_NAME,
            input=results,
            tools=TOOLS,
            previous_interaction_id=interaction.id,
        )
        function_calls = [o for o in (interaction.steps or []) if getattr(o, "type", None) == "function_call"]

    return interaction


def answer(question: str, previous_interaction_id: str | None = None, report_id: int | None = None) -> tuple[str, str]:
    """Returns (answer_text, interaction_id). Pass the returned interaction_id
    back in as previous_interaction_id on the next call to continue the same
    conversation with full memory of prior turns. Pass report_id to scope
    retrieval to a single ingested report instead of searching across all of
    them."""
    chunks = retrieve(question, report_id=report_id)
    context = "\n\n---\n\n".join(chunks) if chunks else "(no matching filing content found)"
    prompt = ANSWER_PROMPT.format(context=context, question=question)

    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=prompt,
        tools=TOOLS,
        previous_interaction_id=previous_interaction_id,
    )
    interaction = _resolve_function_calls(interaction)
    return interaction.output_text, interaction.id


if __name__ == "__main__":
    if len(sys.argv) == 2:
        text, _ = answer(sys.argv[1])
        print(text)
    elif len(sys.argv) == 1:
        print("Interactive mode — conversation memory is on. Type 'exit' to quit.\n")
        prev_id = None
        while True:
            try:
                question = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if question.lower() in ("exit", "quit"):
                break
            if not question:
                continue
            text, prev_id = answer(question, previous_interaction_id=prev_id)
            print(text, "\n")
    else:
        print('Usage: python src/chat.py ["your question"]')
        sys.exit(1)
