# Utility Scripts

This directory contains utility scripts for maintenance, debugging, and data repair.

## Scripts

### `check_extraction.py`
Quick script to check extraction v2.0 results for recently ingested ads.

### `check_s3_files.py`
Verifies S3 bucket connectivity and lists available video files.

### `check_status.py`
Checks the overall status of the ingestion pipeline and database.

### `deduplicate_ads.py`
Identifies and optionally removes duplicate ad entries from the database.

### `investigate_and_retry.py`
Investigates failed ads and retries processing for specific entries.

### `repair_embeddings.py`
Repairs ads that are missing embedding vectors. Useful for partial failures.

### `repair_storyboards.py`
Repairs ads that are missing storyboard analysis. Runs vision pipeline on incomplete ads.

### `verify_completeness.py`
Verifies that all ads have complete data (embeddings, storyboards, extraction v2.0, etc.).

### `backfill_video_urls.py`
Backfills the `video_url` column in the `ads` table from CSV metadata. Matches ads by `external_id` (with fallbacks to `record_id` and `movie_filename`).

**Usage:**
```bash
# Dry run to see what would be updated
python scripts/backfill_video_urls.py --csv "TELLY+ADS (2).csv" --dry-run

# Update only ads missing video_url
python scripts/backfill_video_urls.py --csv "TELLY+ADS (2).csv" --only-missing

# Update all ads (overwrites existing video_url)
python scripts/backfill_video_urls.py --csv "TELLY+ADS (2).csv"

# Test with limited number of ads
python scripts/backfill_video_urls.py --csv "TELLY+ADS (2).csv" --limit 10 --dry-run
```

## Usage

Run scripts from the project root:

```bash
# Example: Check extraction results
python scripts/check_extraction.py

# Example: Repair missing embeddings
python scripts/repair_embeddings.py

# Example: Verify all ads are complete
python scripts/verify_completeness.py
```

## Notes

- Most scripts require environment variables to be set (see `env.example.txt`)
- Scripts use `DB_BACKEND` env var to determine database connection method
- Run `python tvads_rag/apply_schema.py` first if database schema is out of date


