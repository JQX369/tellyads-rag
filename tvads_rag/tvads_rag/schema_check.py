"""
Schema validation for extraction observability columns.

Ensures the database has the required columns for extraction warnings,
fill rates, and validation results. Fails loudly with clear instructions
if columns are missing.

Supports multiple tables with per-table caching.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# =============================================================================
# Required columns per table
# =============================================================================

# Required columns for extraction observability (ads table)
REQUIRED_EXTRACTION_COLUMNS = {
    "extraction_warnings",
    "extraction_fill_rate",
    "extraction_validation",
}

# Required columns for claims evidence grounding (ad_claims table)
REQUIRED_CLAIMS_EVIDENCE_COLUMNS = {
    "timestamp_start_s",
    "timestamp_end_s",
    "evidence",
    "confidence",
}

# Required columns for supers evidence grounding (ad_supers table)
# Note: start_time and end_time already exist, so we only require evidence columns
REQUIRED_SUPERS_EVIDENCE_COLUMNS = {
    "evidence",
    "confidence",
}

# =============================================================================
# Migration files per table
# =============================================================================

MIGRATION_FILE = "schema_extraction_columns.sql"
MIGRATION_FILE_CLAIMS_SUPERS = "schema_claims_supers_evidence.sql"

# Per-table migration file mapping
TABLE_MIGRATIONS: Dict[str, str] = {
    "ads": MIGRATION_FILE,
    "ad_claims": MIGRATION_FILE_CLAIMS_SUPERS,
    "ad_supers": MIGRATION_FILE_CLAIMS_SUPERS,
}

# Per-table required columns mapping
TABLE_REQUIRED_COLUMNS: Dict[str, Set[str]] = {
    "ads": REQUIRED_EXTRACTION_COLUMNS,
    "ad_claims": REQUIRED_CLAIMS_EVIDENCE_COLUMNS,
    "ad_supers": REQUIRED_SUPERS_EVIDENCE_COLUMNS,
}

# =============================================================================
# Caching - per-table validation state
# =============================================================================

# Cached validation result (legacy - for ads table)
_schema_validated: Optional[bool] = None

# Per-table validation cache
_table_validated: Dict[str, bool] = {}


# =============================================================================
# Exceptions
# =============================================================================

class SchemaMissingColumnsError(Exception):
    """Raised when required schema columns are missing."""

    def __init__(
        self,
        missing_columns: List[str],
        table_name: str = "ads",
        migration_file: str = MIGRATION_FILE
    ):
        self.missing_columns = missing_columns
        self.table_name = table_name
        self.migration_file = migration_file
        columns_str = ", ".join(sorted(missing_columns))
        message = (
            f"\n"
            f"{'='*70}\n"
            f"DATABASE SCHEMA ERROR: Missing required columns\n"
            f"{'='*70}\n"
            f"\n"
            f"The following columns are missing from the '{table_name}' table:\n"
            f"  {columns_str}\n"
            f"\n"
            f"To fix this, run the migration in Supabase SQL Editor:\n"
            f"  1. Open Supabase Dashboard > SQL Editor\n"
            f"  2. Paste the contents of: tvads_rag/{migration_file}\n"
            f"  3. Click 'Run'\n"
            f"\n"
            f"Or run via psql:\n"
            f"  psql $SUPABASE_DB_URL -f tvads_rag/{migration_file}\n"
            f"\n"
            f"{'='*70}\n"
        )
        super().__init__(message)


# =============================================================================
# Postgres (psycopg2) backend
# =============================================================================

def check_schema_columns_pg(conn) -> Set[str]:
    """
    Check which required columns exist in the ads table (Postgres backend).

    Args:
        conn: psycopg2 connection

    Returns:
        Set of missing column names
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'ads'
              AND column_name = ANY(%s)
        """, (list(REQUIRED_EXTRACTION_COLUMNS),))

        existing = {row["column_name"] for row in cur.fetchall()}

    missing = REQUIRED_EXTRACTION_COLUMNS - existing
    return missing


def check_table_columns_pg(conn, table_name: str, required_columns: Set[str]) -> Set[str]:
    """
    Check which required columns exist in any table (Postgres backend).

    Args:
        conn: psycopg2 connection
        table_name: Name of the table to check
        required_columns: Set of column names required

    Returns:
        Set of missing column names
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = ANY(%s)
        """, (table_name, list(required_columns)))

        existing = {row["column_name"] for row in cur.fetchall()}

    missing = required_columns - existing
    return missing


def validate_schema_pg(conn) -> None:
    """
    Validate schema has required columns (Postgres backend).

    Raises:
        SchemaMissingColumnsError: If columns are missing
    """
    global _schema_validated

    if _schema_validated:
        return

    missing = check_schema_columns_pg(conn)

    if missing:
        logger.error(
            "Schema validation failed: missing columns %s. "
            "Run migration: %s",
            sorted(missing), MIGRATION_FILE
        )
        raise SchemaMissingColumnsError(list(missing))

    logger.info("Schema validation passed: all extraction columns present")
    _schema_validated = True


def validate_table_schema_pg(conn, table_name: str) -> None:
    """
    Validate a specific table has required columns (Postgres backend).

    Args:
        conn: psycopg2 connection
        table_name: Name of the table to validate

    Raises:
        SchemaMissingColumnsError: If columns are missing
    """
    global _table_validated

    if _table_validated.get(table_name):
        return

    required_columns = TABLE_REQUIRED_COLUMNS.get(table_name)
    if not required_columns:
        logger.debug("No required columns defined for table '%s', skipping validation", table_name)
        _table_validated[table_name] = True
        return

    missing = check_table_columns_pg(conn, table_name, required_columns)

    if missing:
        migration_file = TABLE_MIGRATIONS.get(table_name, MIGRATION_FILE)
        logger.error(
            "Schema validation failed for table '%s': missing columns %s. "
            "Run migration: %s",
            table_name, sorted(missing), migration_file
        )
        raise SchemaMissingColumnsError(list(missing), table_name, migration_file)

    logger.info("Schema validation passed for table '%s': all required columns present", table_name)
    _table_validated[table_name] = True


# =============================================================================
# Supabase HTTP backend
# =============================================================================

def check_schema_columns_http(client) -> Set[str]:
    """
    Check which required columns exist in the ads table (Supabase HTTP backend).

    This uses a simple query to check if columns exist by selecting them.
    If a column doesn't exist, Supabase will return an error.

    Args:
        client: Supabase client

    Returns:
        Set of missing column names
    """
    missing = set()

    for col in REQUIRED_EXTRACTION_COLUMNS:
        try:
            # Try to select the column - will fail if it doesn't exist
            client.table("ads").select(col).limit(1).execute()
        except Exception as e:
            error_str = str(e).lower()
            if "column" in error_str and "does not exist" in error_str:
                missing.add(col)
            elif "undefined column" in error_str:
                missing.add(col)
            # Other errors we let pass (might be auth, network, etc.)

    return missing


def check_table_columns_http(client, table_name: str, required_columns: Set[str]) -> Set[str]:
    """
    Check which required columns exist in any table (Supabase HTTP backend).

    Args:
        client: Supabase client
        table_name: Name of the table to check
        required_columns: Set of column names required

    Returns:
        Set of missing column names
    """
    missing = set()

    for col in required_columns:
        try:
            # Try to select the column - will fail if it doesn't exist
            client.table(table_name).select(col).limit(1).execute()
        except Exception as e:
            error_str = str(e).lower()
            if "column" in error_str and "does not exist" in error_str:
                missing.add(col)
            elif "undefined column" in error_str:
                missing.add(col)
            # Other errors we let pass (might be auth, network, etc.)

    return missing


def validate_schema_http(client) -> None:
    """
    Validate schema has required columns (Supabase HTTP backend).

    Raises:
        SchemaMissingColumnsError: If columns are missing
    """
    global _schema_validated

    if _schema_validated:
        return

    missing = check_schema_columns_http(client)

    if missing:
        logger.error(
            "Schema validation failed: missing columns %s. "
            "Run migration: %s",
            sorted(missing), MIGRATION_FILE
        )
        raise SchemaMissingColumnsError(list(missing))

    logger.info("Schema validation passed: all extraction columns present")
    _schema_validated = True


def validate_table_schema_http(client, table_name: str) -> None:
    """
    Validate a specific table has required columns (Supabase HTTP backend).

    Args:
        client: Supabase client
        table_name: Name of the table to validate

    Raises:
        SchemaMissingColumnsError: If columns are missing
    """
    global _table_validated

    if _table_validated.get(table_name):
        return

    required_columns = TABLE_REQUIRED_COLUMNS.get(table_name)
    if not required_columns:
        logger.debug("No required columns defined for table '%s', skipping validation", table_name)
        _table_validated[table_name] = True
        return

    missing = check_table_columns_http(client, table_name, required_columns)

    if missing:
        migration_file = TABLE_MIGRATIONS.get(table_name, MIGRATION_FILE)
        logger.error(
            "Schema validation failed for table '%s': missing columns %s. "
            "Run migration: %s",
            table_name, sorted(missing), migration_file
        )
        raise SchemaMissingColumnsError(list(missing), table_name, migration_file)

    logger.info("Schema validation passed for table '%s': all required columns present", table_name)
    _table_validated[table_name] = True


# =============================================================================
# Cache management
# =============================================================================

def reset_validation_cache() -> None:
    """Reset all validation caches (for testing)."""
    global _schema_validated, _table_validated
    _schema_validated = None
    _table_validated = {}


def reset_table_validation_cache(table_name: str) -> None:
    """Reset validation cache for a specific table (for testing)."""
    global _table_validated
    if table_name in _table_validated:
        del _table_validated[table_name]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "REQUIRED_EXTRACTION_COLUMNS",
    "REQUIRED_CLAIMS_EVIDENCE_COLUMNS",
    "REQUIRED_SUPERS_EVIDENCE_COLUMNS",
    "MIGRATION_FILE",
    "MIGRATION_FILE_CLAIMS_SUPERS",
    "TABLE_MIGRATIONS",
    "TABLE_REQUIRED_COLUMNS",
    # Exception
    "SchemaMissingColumnsError",
    # Postgres functions
    "check_schema_columns_pg",
    "check_table_columns_pg",
    "validate_schema_pg",
    "validate_table_schema_pg",
    # HTTP functions
    "check_schema_columns_http",
    "check_table_columns_http",
    "validate_schema_http",
    "validate_table_schema_http",
    # Cache management
    "reset_validation_cache",
    "reset_table_validation_cache",
]
