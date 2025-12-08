# Repository Cleanup Changes

## Summary

This document records all changes made during the repo cleanup on branch `chore/repo-cleanup`.

**Date**: 2025-12-08
**Branch**: `chore/repo-cleanup`

---

## Deleted Files

### Root-Level Temp Files (Batch A)

| File | Size | Reason |
|------|------|--------|
| `conflicts_20251204_175551.csv` | 2KB | Import artifact |
| `matched_20251204_110855.csv` | ~54KB | Import artifact |
| `matched_20251204_142116.csv` | ~54KB | Import artifact |
| `matched_20251204_175551.csv` | ~54KB | Import artifact |
| `unmatched_20251204_110855.csv` | ~1.7MB | Import artifact |
| `unmatched_20251204_142116.csv` | ~1.7MB | Import artifact |
| `unmatched_20251204_175551.csv` | ~1.7MB | Import artifact |
| `import_summary_20251204_110855.json` | ~300B | Import artifact |
| `import_summary_20251204_142116.json` | ~300B | Import artifact |
| `import_summary_20251204_175551.json` | ~300B | Import artifact |
| `nul` | 175B | Windows artifact |
| `pipeline.log` | ~100KB | Duplicate of tvads_rag/pipeline.log |
| `env.example.txt` | ~1KB | Duplicate of .env.example |

**Verification**: `rg -l "conflicts_20251204|matched_20251204|unmatched_20251204|import_summary_"` returned no code references.

### Obsolete Folders (Batch B)

| Path | Reason | Action |
|------|--------|--------|
| `api/` | Single README referencing deleted backend | Deleted entire folder |
| `requirements/` | Orphaned docs-index.md | Moved content to docs/, deleted folder |
| `templates/` | Single unused template | Moved content to docs/templates/, deleted folder |

---

## Moved Files

### Documentation Consolidation (Batch C)

| From | To | Reason |
|------|------|--------|
| `BUILD_FIX.md` | `docs/troubleshooting/BUILD_FIX.md` | Consolidate troubleshooting docs |
| `QUICK_FIX.md` | `docs/troubleshooting/QUICK_FIX.md` | Consolidate troubleshooting docs |
| `VERCEL_FIX.md` | `docs/troubleshooting/VERCEL_FIX.md` | Consolidate troubleshooting docs |
| `DEPLOYMENT.md` | `docs/DEPLOYMENT.md` | Move deployment docs to docs/ |
| `AUDIT_REPORT.md` | `docs/AUDIT_REPORT.md` | Move audit report to docs/ |
| `requirements/docs-index.md` | `docs/external-docs-index.md` | Rescue before folder deletion |
| `templates/activity-log-entry.md` | `docs/templates/activity-log-entry.md` | Rescue before folder deletion |

### Schema SQL Consolidation (Batch D)

16 ad-hoc schema migration files moved from `tvads_rag/` to `tvads_rag/migrations/archived/`:

| File | Purpose |
|------|---------|
| `schema_extraction_columns.sql` | Extraction columns migration |
| `schema_claims_supers_evidence.sql` | Claims/supers/evidence fields |
| `schema_clearance.sql` | Clearance assessment |
| `schema_toxicity_migration.sql` | Toxicity scoring |
| `schema_hero_analysis.sql` | Hero analysis |
| `schema_visual_identity.sql` | Visual identity |
| (+ 10 more) | Various ad-hoc migrations |

**Canonical schema remains**: `tvads_rag/schema.sql`
**Numbered migrations remain**: `tvads_rag/migrations/002-005*.sql`

---

## Code Updates (Required for Schema Move)

| File | Change | Reason |
|------|--------|--------|
| `tvads_rag/tests/test_clearance.py` | Updated 4 migration file paths | Point to migrations/archived/ |
| `tvads_rag/tests/test_evidence_aligner.py` | Updated 1 migration file path | Point to migrations/archived/ |
| `tvads_rag/tvads_rag/schema_check.py` | Updated MIGRATION_FILE constants | Point to migrations/archived/ |

---

## Validation Results

| Check | Status | Notes |
|-------|--------|-------|
| Python Tests | PASS | 75 tests passed |
| Frontend Lint | PRE-EXISTING WARNINGS | Not caused by cleanup |
| Frontend Typecheck | PRE-EXISTING ERRORS | test file type errors |
| Frontend Build | PRE-EXISTING ERRORS | `verifyAdmin` import bug in analytics routes |

**Note**: Frontend issues are pre-existing bugs in `app/api/admin/analytics/*` routes that import non-existent `verifyAdmin` (should be `verifyAdminKey`). These files were not touched by this cleanup.

---

## Files NOT Deleted (Verified In Use)

| File | Reason to Keep |
|------|----------------|
| `dashboard.py` | Documented in CLAUDE.md as `streamlit run dashboard.py` |
| `tvads_rag/schema.sql` | Canonical database schema |
| `tvads_rag/migrations/*.sql` | Numbered migrations (002-005) |
| `.env.example` | Primary env template |

---

## Structure After Cleanup

```
TellyAds RAG/
├── .github/workflows/        # CI/CD (unchanged)
├── docs/                     # All documentation
│   ├── repo_cleanup/         # This cleanup documentation
│   │   ├── REPO_MAP.md
│   │   ├── CLEANUP_PLAN.md
│   │   ├── CHANGES.md        # This file
│   │   └── STATUS.md
│   ├── troubleshooting/      # Moved from root
│   │   ├── BUILD_FIX.md
│   │   ├── QUICK_FIX.md
│   │   └── VERCEL_FIX.md
│   ├── templates/            # Moved from root templates/
│   │   └── activity-log-entry.md
│   ├── DEPLOYMENT.md         # Moved from root
│   ├── AUDIT_REPORT.md       # Moved from root
│   └── ...                   # Existing docs
├── frontend/                 # Next.js app (unchanged)
├── scripts/                  # Utility scripts (unchanged)
├── tvads_rag/                # Python package
│   ├── migrations/
│   │   ├── archived/         # NEW: Old schema_*.sql files
│   │   └── *.sql             # Numbered migrations
│   ├── schema.sql            # Canonical schema
│   └── ...
├── .env.example              # Primary env template
├── CLAUDE.md                 # Project instructions
└── README.md                 # Project readme
```

---

## Deleted Folders

- `api/` - Obsolete (only contained README)
- `requirements/` - Orphaned (content moved to docs/)
- `templates/` - Unused (content moved to docs/templates/)

---

## Bytes Saved

| Category | Approximate Size |
|----------|-----------------|
| Temp CSV files | ~5.4MB |
| Temp JSON files | ~1KB |
| Duplicate files | ~101KB |
| **Total Removed** | **~5.5MB** |

---

## How to Verify

```bash
# Check Python tests still pass
cd tvads_rag && pytest tests/ -v

# Verify schema files moved correctly
ls tvads_rag/migrations/archived/

# Verify docs structure
ls docs/troubleshooting/
ls docs/templates/
```
