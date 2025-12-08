# Cleanup Plan

## Executive Summary

This document outlines the proposed cleanup actions for the TellyAds RAG repository. The goal is to remove dead code, consolidate redundant files, and improve organization without changing functionality.

---

## Phase 1: Identified Smells

### 1. Root-Level Temporary Files (HIGH PRIORITY)

| File | Size | Purpose | Recommendation |
|------|------|---------|----------------|
| `conflicts_20251204_175551.csv` | 2KB | Import artifact | DELETE |
| `matched_20251204_*.csv` (3 files) | 160KB total | Import artifacts | DELETE |
| `unmatched_20251204_*.csv` (3 files) | 5.2MB total | Import artifacts | DELETE |
| `import_summary_*.json` (3 files) | 1KB total | Import artifacts | DELETE |
| `TELLY+ADS (2).csv` | 7MB | Source data | MOVE to `data/` or ADD to .gitignore |
| `nul` | 175B | Windows artifact | DELETE |
| `pipeline.log` | 100KB | Duplicate log | DELETE (duplicate of tvads_rag/pipeline.log) |

**Risk**: None - these are temporary artifacts not referenced by code
**Verification**: `rg -l "conflicts_20251204\|matched_20251204\|unmatched_20251204\|import_summary_"` returns no results

### 2. Obsolete Folders (HIGH PRIORITY)

| Folder | Contents | Recommendation |
|--------|----------|----------------|
| `api/` | Single README mentioning deleted backend | DELETE |
| `requirements/` | Single docs-index.md file | MOVE content to `docs/`, DELETE folder |
| `templates/` | Single activity-log-entry.md template | MOVE to `docs/templates/`, DELETE folder |

**Risk**: None - folders contain only documentation
**Verification**: No imports reference these folders

### 3. Schema SQL File Proliferation (MEDIUM PRIORITY)

The `tvads_rag/` folder has 17 schema SQL files:
- `schema.sql` - Main schema (canonical)
- `migrations/` - Numbered migrations (002-005)
- `schema_*.sql` - Ad-hoc migrations (16 files)

**Recommendation**:
- Keep `schema.sql` as canonical
- Keep `migrations/` for numbered migrations
- MOVE `schema_*.sql` files to `migrations/archived/` for reference

### 4. Documentation Consolidation Opportunity (LOW PRIORITY)

Root-level markdown files that could move to `docs/`:
- `BUILD_FIX.md` → `docs/troubleshooting/`
- `DEPLOYMENT.md` → `docs/deployment/`
- `QUICK_FIX.md` → `docs/troubleshooting/`
- `VERCEL_FIX.md` → `docs/troubleshooting/`
- `AUDIT_REPORT.md` → `docs/`

**Note**: Keep `README.md` and `CLAUDE.md` at root (convention)

### 5. Nested Python Package Structure (INFORMATIONAL)

Current structure: `tvads_rag/tvads_rag/`
This is standard Python packaging but creates deep nesting.
**Recommendation**: Leave as-is (changing would break imports)

---

## Phase 2: Dead Code Analysis

### Candidate Files

| File | Reason | Proof Method | Confidence |
|------|--------|--------------|------------|
| `api/README.md` | References deleted backend | Folder obsolete | HIGH |
| `requirements/docs-index.md` | Orphaned documentation | No imports | HIGH |
| `templates/activity-log-entry.md` | Unused template | `rg -l activity-log-entry` | HIGH |
| `env.example.txt` | Duplicate of `.env.example` | Same purpose | HIGH |
| `dashboard.py` | Streamlit dashboard | Check if still used | MEDIUM |

### Verification Commands

```bash
# Check for references to deleted backend
rg -l "from backend\|import backend"

# Check template usage
rg -l "activity-log-entry"

# Check dashboard usage
rg -l "dashboard.py\|streamlit run"
```

---

## Phase 3: Target Structure

### Proposed Structure (Minimal Changes)

```
TellyAds RAG/
├── .github/workflows/          # CI/CD (keep as-is)
├── docs/                       # All documentation
│   ├── repo_cleanup/           # This cleanup docs
│   ├── troubleshooting/        # BUILD_FIX, QUICK_FIX, VERCEL_FIX
│   ├── templates/              # Moved from root templates/
│   └── ...                     # Existing docs
├── frontend/                   # Next.js app (keep as-is)
├── scripts/                    # Utility scripts (keep as-is)
├── tvads_rag/                  # Python package (keep as-is)
│   ├── migrations/
│   │   ├── archived/           # Old schema_*.sql files
│   │   └── *.sql               # Numbered migrations
│   └── ...
├── .env.example                # Keep (remove env.example.txt duplicate)
├── CLAUDE.md                   # Keep
└── README.md                   # Keep
```

### Deleted Folders
- `api/` (obsolete)
- `requirements/` (content moved to docs)
- `templates/` (content moved to docs)

---

## Phase 4: Execution Batches

### Batch A: Delete Root Temp Files
```bash
rm -f conflicts_20251204_175551.csv
rm -f matched_20251204_*.csv
rm -f unmatched_20251204_*.csv
rm -f import_summary_*.json
rm -f nul
rm -f pipeline.log
```

### Batch B: Delete Obsolete Folders
```bash
rm -rf api/
mv requirements/docs-index.md docs/external-docs-index.md
rm -rf requirements/
mv templates/activity-log-entry.md docs/templates/
rm -rf templates/
```

### Batch C: Consolidate Docs
```bash
mkdir -p docs/troubleshooting
mv BUILD_FIX.md docs/troubleshooting/
mv QUICK_FIX.md docs/troubleshooting/
mv VERCEL_FIX.md docs/troubleshooting/
mv AUDIT_REPORT.md docs/
```

### Batch D: Schema Consolidation
```bash
mkdir -p tvads_rag/migrations/archived
mv tvads_rag/schema_*.sql tvads_rag/migrations/archived/
# Keep tvads_rag/schema.sql as canonical
```

### Batch E: Cleanup Duplicates
```bash
rm -f env.example.txt  # Duplicate of .env.example
```

---

## Risk Assessment

| Action | Risk Level | Mitigation |
|--------|------------|------------|
| Delete temp CSV/JSON | None | Not referenced anywhere |
| Delete api/ folder | None | Only contains README |
| Move docs | Low | Update any doc links |
| Move schema_*.sql | Low | Already have canonical schema.sql |
| Delete env.example.txt | None | Duplicate |

---

## Verification Plan

After each batch:
1. `cd frontend && npm run lint` - Frontend lint
2. `cd frontend && npm run typecheck` - TypeScript check
3. `cd frontend && npm test` - Frontend tests
4. `cd frontend && npm run build` - Build check
5. `cd tvads_rag && pytest tests/ -v` - Python tests
