# Repository Map

## Stack Detection

### Frontend
- **Framework**: Next.js 16.0.5 (App Router)
- **Language**: TypeScript 5.x
- **Styling**: Tailwind CSS 3.4.1
- **Runtime**: Node.js 20.x
- **Location**: `frontend/`

### Backend/Pipeline
- **Language**: Python 3.11
- **Framework**: Custom RAG pipeline (no web framework - FastAPI backend was deleted)
- **Database**: PostgreSQL with pgvector (via Supabase)
- **Location**: `tvads_rag/tvads_rag/`

### Infrastructure
- **Deployment**: Vercel (frontend), Railway (worker)
- **CI/CD**: GitHub Actions (`.github/workflows/ci.yml`)
- **Error Tracking**: Sentry (frontend + worker)

---

## Base Commands

### Frontend (from `frontend/` directory)
```bash
# Install
npm ci

# Development
npm run dev

# Lint
npm run lint

# Type check
npm run typecheck

# Unit tests
npm test

# Build
npm run build
```

### Python/RAG Pipeline (from root or `tvads_rag/`)
```bash
# Install
pip install -r tvads_rag/requirements.txt

# Lint (Ruff)
ruff check . --ignore E501

# Tests
cd tvads_rag && pytest tests/ -v

# Worker
python -m tvads_rag.worker

# Indexing
python -m tvads_rag.index_ads --source local --limit 50
```

---

## Directory Structure (Top 3 Levels)

```
TellyAds RAG/
├── .claude/                    # Claude Code settings
├── .cursor/                    # Cursor AI agent configs
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI
├── api/                        # OBSOLETE - just README
├── docs/                       # Project documentation
│   ├── seo/
│   ├── ui/
│   └── repo_cleanup/           # This cleanup documentation
├── frontend/                   # Next.js application
│   ├── app/                    # App Router pages & API routes
│   ├── components/             # React components
│   ├── lib/                    # Utilities, types, DB client
│   └── public/                 # Static assets
├── requirements/               # OBSOLETE - just one docs file
├── scripts/                    # Utility scripts (Python)
│   └── seo/
├── templates/                  # OBSOLETE - just one template
├── tvads_rag/                  # Python RAG package
│   ├── migrations/             # SQL migration files
│   ├── output/                 # Processing output
│   ├── tests/                  # Python tests
│   └── tvads_rag/              # Main package code
│       ├── pipeline/           # Pipeline stages
│       └── prompts/            # LLM prompts
└── [root files]                # Config, docs, temp files
```

---

## Folder Purpose Summary

| Folder | Purpose | Status |
|--------|---------|--------|
| `frontend/` | Next.js web app + API routes | Active |
| `tvads_rag/` | Python RAG ingestion pipeline | Active |
| `scripts/` | Maintenance/utility scripts | Active |
| `docs/` | Project documentation | Active |
| `.github/` | CI/CD workflows | Active |
| `api/` | Old Vercel API config | **OBSOLETE** |
| `requirements/` | Old docs index | **OBSOLETE** |
| `templates/` | Activity log template | **OBSOLETE** |

---

## Entrypoints

### Frontend
- `frontend/app/page.tsx` - Home page
- `frontend/app/api/**/route.ts` - API routes

### Python
- `tvads_rag/tvads_rag/worker.py` - Queue worker (`python -m tvads_rag.worker`)
- `tvads_rag/tvads_rag/index_ads.py` - CLI indexer (`python -m tvads_rag.index_ads`)
- `tvads_rag/tvads_rag/query_demo.py` - Query demo (`python -m tvads_rag.query_demo`)

### Scripts
- `scripts/*.py` - Various maintenance scripts (standalone)

---

## Configuration Files

| File | Purpose |
|------|---------|
| `frontend/package.json` | Node dependencies & scripts |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/tailwind.config.ts` | Tailwind CSS config |
| `frontend/next.config.ts` | Next.js config |
| `tvads_rag/requirements.txt` | Python dependencies |
| `.github/workflows/ci.yml` | CI/CD pipeline |
| `CLAUDE.md` | Claude Code instructions |
