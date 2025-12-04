# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TellyAds RAG is a semantic search platform for TV commercials with three tiers:
- **frontend/** - Next.js 16 React app with TypeScript and Tailwind CSS
- **backend/** - FastAPI REST API for search and ad retrieval
- **tvads_rag/** - Python RAG ingestion pipeline (AI analysis, embeddings, database)

## Commands

### Frontend (Next.js)
```bash
cd frontend
npm run dev          # Development server on localhost:3000
npm run build        # Production build
npm run lint         # ESLint check
```

### Backend (FastAPI)
```bash
python -m uvicorn backend.main:app --port 8000 --reload   # Development
uvicorn backend.main:app --host 0.0.0.0 --port $PORT      # Production
```

### RAG Pipeline
```bash
# Indexing
python -m tvads_rag.index_ads --source local --limit 50
python -m tvads_rag.index_ads --source s3 --limit 100
python -m tvads_rag.index_ads --source local --single-path /path/to/video.mp4

# Query demo
python -m tvads_rag.query_demo --query "ads with free trials" --top-k 5

# Config dashboard
streamlit run dashboard.py

# Tests
pytest tvads_rag/tests/ -v
```

### Database Schema
```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema.sql
```

## Architecture

### RAG Pipeline Flow (9 stages)
1. Video ingestion (local/S3)
2. Media probing (ffprobe metadata)
3. Audio extraction (ffmpeg → WAV)
4. ASR transcription (Whisper)
5. LLM analysis (GPT structured extraction)
6. Visual analysis (Gemini, optional)
7. Embedding generation (text-embedding-3-large, 1536-dim)
8. Database storage (Postgres + pgvector)
9. Query/retrieval (semantic search + optional Cohere reranking)

### Database Backend Routing
- `tvads_rag/db_backend.py` routes between direct Postgres (`db.py`) and Supabase HTTP client (`supabase_db.py`)
- Set `DB_BACKEND=postgres` or `DB_BACKEND=http` in `.env`
- Automatic fallback: HTTP → Postgres if Supabase unavailable

### Parallel Processing
- Thread pool executor in `index_ads.py` (configurable via `INGEST_PARALLEL_WORKERS`, default 3)
- Modular pipeline stages in `tvads_rag/pipeline/stages/`

### Frontend Structure
- Next.js App Router (`app/` directory)
- Components in `frontend/components/`
- TypeScript types in `frontend/lib/types.ts` (SearchResult, AdDetail interfaces)
- SEO utilities in `frontend/lib/seo.ts`
- Dark mode by default (Tailwind + CSS variables)

### API Endpoints (backend/main.py)
- `GET /api/search` - Semantic search with reranking
- `GET /api/ads/{external_id}` - Single ad detail
- `GET /api/ads/{external_id}/similar` - Similar ads
- `GET /api/recent` - Recently indexed ads
- `GET /api/brands` - Brand listing
- `GET /api/stats` - Database statistics
- `GET /api/status` - Health check

## Key Configuration

### Model Defaults
- Text LLM: `gpt-5.1`
- Embeddings: `text-embedding-3-large`
- Vision (fast): `gemini-2.5-flash`
- Vision (quality): `gemini-3.0-pro`
- Reranking: `rerank-english-v3.0` (Cohere, optional - set `RERANK_PROVIDER=none` to disable)

### Environment Variables
Copy `.env.example` to `.env`. Key variables:
- `SUPABASE_DB_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - Required for embeddings and LLM
- `GOOGLE_API_KEY` - Required for vision analysis
- `COHERE_API_KEY` - Optional for reranking
- `VIDEO_SOURCE_TYPE` - `local` or `s3`
- `NEXT_PUBLIC_API_URL` - Backend URL for frontend

### Testing
- Use `USE_DUMMY_ASR=1` for faster local testing (skips Whisper)
- Use `--limit N` flag to process subset of videos
- Tests use monkeypatch for environment variables; config cache is cleared between tests

## Utility Scripts

The `scripts/` directory contains maintenance utilities:
- `verify_completeness.py` - Check processing status
- `repair_embeddings.py` - Fix missing embeddings
- `backfill_video_urls.py` - Update URLs from CSV
- `data_quality_check.py` - Validate data integrity
- `migrate_processing_notes.py` - Schema migrations

## Deployment

### Vercel (Full-Stack - Recommended)

The frontend now runs as a full-stack Next.js app with built-in API routes. No separate backend required.

**Build Settings:**
- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `.next`
- Install command: `npm install`

**Required Environment Variables:**
```
SUPABASE_DB_URL=postgresql://...  # Postgres connection string
OPENAI_API_KEY=sk-...              # For semantic search embeddings
NEXT_PUBLIC_SITE_URL=https://tellyads.com
```

**Optional Environment Variables:**
```
ADMIN_API_KEY=...                  # For admin endpoints (tag moderation)
```

**Deployment Steps:**
1. Connect your GitHub repo to Vercel
2. Set root directory to `frontend`
3. Add environment variables in Vercel dashboard
4. Deploy

**After Deployment:**
- Verify `/api/status` returns `{"status":"ok"}`
- Check `/sitemap.xml` lists published ads
- Test search at `/search`

### Legacy Backend (FastAPI)

The FastAPI backend in `backend/` is now optional. It can still be deployed separately if needed:
- Deploy to Railway, Render, or Fly.io
- Use: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### RAG Pipeline

The ingestion pipeline runs offline/manually and does not need to be deployed:
```bash
# Run locally when indexing new ads
python -m tvads_rag.index_ads --source s3 --limit 100
```

## API Routes (Next.js Route Handlers)

The frontend includes these API routes in `frontend/app/api/`:

| Route | Method | Description |
|-------|--------|-------------|
| `/api/status` | GET | Health check |
| `/api/search` | POST | Semantic search with embeddings |
| `/api/recent` | GET | Recently indexed ads |
| `/api/brands` | GET | Brand listing |
| `/api/stats` | GET | Database statistics |
| `/api/advert/[brand]/[slug]` | GET | SEO ad detail (publish-gated) |
| `/api/ads/[id]` | GET | Ad by external_id |
| `/api/ads/[id]/similar` | GET | Similar ads by embedding |
| `/api/ads/[id]/feedback` | GET | Feedback metrics |
| `/api/ads/[id]/view` | POST | Record view |
| `/api/ads/[id]/like` | POST | Toggle like |
| `/api/ads/[id]/save` | POST | Toggle save |
| `/api/ads/[id]/reasons` | GET/POST | Why people like this ad |
| `/api/legacy-redirect` | GET | Redirect old Wix URLs |

## SEO Features

- **Dynamic sitemap.xml**: Auto-generated from published editorial pages
- **robots.txt**: Configured for search engines
- **Legacy URL redirects**: Middleware handles `/post/*` redirects to new canonical URLs
- **Publish gating**: Only ads with `status='published' AND is_hidden=false AND (publish_date IS NULL OR publish_date <= NOW())` are visible
