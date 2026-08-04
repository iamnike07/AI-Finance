"""
Ingestion pipeline.

Usage:
    python src/ingest.py path/to/report.pdf

Steps:
    1. Convert PDF -> markdown (pymupdf4llm)
    2. Split markdown into semantic chunks
    3. Embed each chunk (local sentence-transformers model)
    4. Store report + chunks + embeddings in Postgres
"""
import sys
from pathlib import Path

import pymupdf4llm
from langchain_text_splitters import MarkdownTextSplitter
from sentence_transformers import SentenceTransformer

from db import get_connection

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 384-dim, matches schema.sql
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_model = None


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def pdf_to_markdown(pdf_path: str) -> str:
    return pymupdf4llm.to_markdown(pdf_path)


def chunk_markdown(markdown_text: str) -> list[str]:
    splitter = MarkdownTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return splitter.split_text(markdown_text)


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(chunks, normalize_embeddings=True).tolist()


def store_report(conn, filename: str) -> int:
    cur = conn.execute(
        "INSERT INTO reports (filename) VALUES (%s) RETURNING id",
        (filename,),
    )
    return cur.fetchone()[0]


def store_chunks(conn, report_id: int, chunks: list[str], embeddings: list[list[float]]):
    with conn.cursor() as cur:
        for i, (text, embedding) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """
                INSERT INTO chunks (report_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s)
                """,
                (report_id, i, text, embedding),
            )


def ingest(pdf_path: str, display_filename: str | None = None):
    filename = display_filename or Path(pdf_path).name
    print(f"[1/4] Converting {filename} to markdown...")
    markdown_text = pdf_to_markdown(pdf_path)

    print("[2/4] Chunking...")
    chunks = chunk_markdown(markdown_text)
    print(f"      -> {len(chunks)} chunks")

    print("[3/4] Embedding...")
    embeddings = embed_chunks(chunks)

    print("[4/4] Storing in Postgres...")
    conn = get_connection()
    report_id = store_report(conn, filename)
    store_chunks(conn, report_id, chunks, embeddings)
    conn.close()

    print(f"Done. report_id={report_id}")
    return report_id, markdown_text


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python src/ingest.py path/to/report.pdf")
        sys.exit(1)
    ingest(sys.argv[1])
