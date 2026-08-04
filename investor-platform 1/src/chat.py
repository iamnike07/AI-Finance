"""
RAG chat over ingested reports, using hybrid retrieval.

Usage:
    python src/chat.py "What was total revenue last quarter?"

Retrieval strategy:
    Dense (pgvector cosine similarity) is good at semantic similarity but
    weak on exact tokens — ticker symbols, precise dollar figures, defined
    terms. Sparse (BM25) is the opposite: exact-term matching, weak on
    paraphrase. We run both and merge results with Reciprocal Rank Fusion
    (RRF), which just rewards chunks that rank well in *either* list without
    needing to calibrate the two very different scoring scales against
    each other.

    BM25 is computed in-process over all chunks in the database. That's
    fine up to a few thousand chunks (a handful of ingested reports) — the
    index gets rebuilt on every question, which is wasteful at larger
    scale. If your corpus grows past that, swap this for Postgres full-text
    search (tsvector + GIN index) so the keyword side lives in the database
    too, instead of re-tokenizing everything in Python per query.
"""
import re
import sys

from dotenv import load_dotenv
from google import genai
from rank_bm25 import BM25Okapi

from db import get_connection
from ingest import get_embedding_model

load_dotenv()

client = genai.Client()
MODEL_NAME = "gemini-3.6-flash"

TOP_K = 5              # final number of chunks sent to the LLM
CANDIDATE_K = 20        # how many each retrieval method contributes before fusion
RRF_K = 3                # damping constant, tuned small for this small candidate pool
                          # (the standard k=60 from the RRF paper assumes ranked lists
                          # of ~1000 results; at our scale it over-smooths and can bury
                          # a genuine exact-match hit outside the final top-5 — verified
                          # empirically before picking this value)

ANSWER_PROMPT = """Answer the user's question using only the context below.
If the context doesn't contain the answer, say so plainly.

Context:
{context}

Question: {question}
"""

_TOKEN_RE = re.compile(r"[A-Za-z0-9$%.]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase word/number/symbol tokenizer. Keeps $, %, . so things like
    '$391,035' and '3.6%' survive as meaningful tokens for BM25."""
    return _TOKEN_RE.findall(text.lower())


def _load_all_chunks() -> list[tuple[int, str]]:
    conn = get_connection()
    rows = conn.execute("SELECT id, content FROM chunks").fetchall()
    conn.close()
    return rows


def _vector_search_ids(question: str, top_k: int) -> list[int]:
    model = get_embedding_model()
    query_embedding = model.encode([question], normalize_embeddings=True)[0].tolist()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
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
    """Merge several ranked ID lists into one, by RRF score.
    A chunk that appears near the top of *either* list scores well;
    appearing in both compounds the score further."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda p: p[1], reverse=True)]


def retrieve(question: str, top_k: int = TOP_K) -> list[str]:
    all_chunks = _load_all_chunks()
    if not all_chunks:
        return []
    lookup = dict(all_chunks)

    vector_ids = _vector_search_ids(question, CANDIDATE_K)
    bm25_ids = _bm25_search_ids(question, all_chunks, CANDIDATE_K)

    fused_ids = _reciprocal_rank_fusion([vector_ids, bm25_ids])[:top_k]
    return [lookup[cid] for cid in fused_ids if cid in lookup]


def answer(question: str) -> str:
    chunks = retrieve(question)
    context = "\n\n---\n\n".join(chunks)
    prompt = ANSWER_PROMPT.format(context=context, question=question)

    interaction = client.interactions.create(model=MODEL_NAME, input=prompt)
    return interaction.output_text


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python src/chat.py "your question"')
        sys.exit(1)
    print(answer(sys.argv[1]))
