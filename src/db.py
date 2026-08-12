"""Shared Postgres connection helper."""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://investor:investor_dev_password@localhost:5432/investor_platform",
)


def get_connection():
    """Open a new Postgres connection with pgvector adapters registered."""
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    _register_vector(conn)
    return conn


def _register_vector(conn):
    """Register the pgvector type so Python lists <-> vector columns work."""
    from pgvector.psycopg import register_vector

    register_vector(conn)
