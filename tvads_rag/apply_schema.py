"""
Helper script to apply the database schema from schema.sql.

Note: Schema application requires direct Postgres access (port 5432). If your
machine cannot reach the database directly, apply the schema via the Supabase
web UI SQL editor instead.
"""

import logging
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from tvads_rag.config import get_db_config

logger = logging.getLogger(__name__)


def apply_schema(schema_path: str = "tvads_rag/schema.sql") -> None:
    """Read and execute the SQL schema file."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found at {path}")

    sql_content = path.read_text(encoding="utf-8")
    
    if psycopg2 is None:
        logger.error("psycopg2-binary is required for schema application but not installed.")
        logger.info("Install it with: pip install psycopg2-binary")
        logger.info("Alternatively, apply the schema via Supabase web UI:")
        logger.info("  1. Open your Supabase project dashboard")
        logger.info("  2. Go to SQL Editor -> New query")
        logger.info("  3. Paste the contents of %s", path)
        logger.info("  4. Click Run")
        sys.exit(1)
    
    cfg = get_db_config()
    logger.info("Applying schema from %s...", path)
    logger.info("Connecting to database...")
    
    try:
        conn = psycopg2.connect(cfg.url, cursor_factory=None)
        try:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            conn.commit()
            logger.info("Schema applied successfully.")
        finally:
            conn.close()
    except psycopg2.OperationalError as exc:
        logger.error("Failed to connect to database: %s", exc)
        logger.info("")
        logger.info("Schema application requires direct Postgres access (port 5432).")
        logger.info("If your machine cannot reach the database, apply the schema via Supabase web UI:")
        logger.info("  1. Open your Supabase project dashboard")
        logger.info("  2. Go to SQL Editor -> New query")
        logger.info("  3. Paste the contents of %s", path)
        logger.info("  4. Click Run")
        logger.info("")
        logger.info("Schema SQL is ready at: %s", path.absolute())
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_schema()


