# TV Ads RAG Pipeline

End-to-end local indexing pipeline for ~20k TV ads. The CLI scans local or S3
videos, extracts audio, transcribes via Whisper, runs an LLM for structured
analysis, stores everything in Supabase Postgres + pgvector, and exposes a
simple similarity-search demo.

## Requirements

- Python 3.11+
- `ffmpeg` + `ffprobe` available on `PATH`
- Supabase (or self-managed Postgres) with [`pgvector`](https://supabase.com/docs/guides/database/extensions/pgvector)
- AWS credentials (only if indexing directly from S3)
- Optional storyboard pass: Google Gemini access + `google-genai` (already listed in `requirements.txt`)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate on macOS/Linux
pip install -r tvads_rag/requirements.txt
cp .env.example .env  # fill in your values
```

**Get your API keys:**
- **OpenAI API Key**: Required for text analysis, embeddings, and Whisper transcription. Get from https://platform.openai.com/api-keys
- **Google API Key**: Required for vision/storyboard analysis. Get from https://aistudio.google.com/app/apikey
- **Cohere API Key**: Optional, for reranking. Get from https://dashboard.cohere.com/api-keys
- **Supabase Credentials**: Already configured in `.env.example` - just add your database password from Supabase dashboard

Apply the database schema (via Supabase SQL editor or CLI):

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema.sql
```

**Configuration Options:**
- Edit `.env` directly, OR
- Use the dashboard (`streamlit run dashboard.py`) which provides a UI for editing `.env`
- Both methods work - the dashboard just provides a convenient UI

Key environment variables:

- `SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (from Supabase dashboard)
- `OPENAI_API_KEY` (from https://platform.openai.com/api-keys)
- `TEXT_LLM_MODEL` (default: `gpt-5.1`), `EMBEDDING_MODEL` (default: `text-embedding-3-large`)
- `VIDEO_SOURCE_TYPE` (`local` or `s3`)
- `LOCAL_VIDEO_DIR` *or* `S3_BUCKET` + `S3_PREFIX`
- `VISION_PROVIDER` (`none` or `google`), `VISION_MODEL_FAST` (default: `gemini-2.5-flash`), `VISION_MODEL_QUALITY` (default: `gemini-3.0-pro`), `GOOGLE_API_KEY`, `VISION_DEFAULT_TIER` (`fast` or `quality`)
- `RERANK_PROVIDER` (`none` or `cohere`), `RERANK_MODEL`, `COHERE_API_KEY`
- `USE_DUMMY_ASR=1` to skip real Whisper calls during dry runs
- `LOG_LEVEL`, `INDEX_SOURCE_DEFAULT`
- `INGEST_PARALLEL_WORKERS` - Number of parallel ad processing workers (default: `3`). Increase for faster ingestion if your API rate limits allow.

## Optional storyboard / visual analysis (Gemini)

The text pipeline continues to rely on GPT-style models. To add an *additional* visual storyboard pass:

1. Set `VISION_PROVIDER=google`, `VISION_MODEL_NAME` (e.g. `gemini-2.0-pro-exp`), and `GOOGLE_API_KEY`.
2. Adjust `FRAME_SAMPLE_SECONDS` (default `1.0`) to control how often frames are sampled.
3. Ensure `google-genai` is installed (included in `requirements.txt`).
4. Re-run `schema.sql` so the new `ad_storyboards` table + `storyboard_id` FK are present.

When enabled, `index_ads.py` will:

- Sample frames via `ffmpeg`.
- Call Gemini to group frames into shots and write them into `ad_storyboards`.
- Insert additional `storyboard_shot` embeddings so storyboard search works alongside transcript/claim search.

### Deep Extract overall score

When the Gemini \"Hero\" / Deep Extract pass runs, it now also returns an `overall_score`
(float 0–100; higher = stronger creative impact). The score is stored inside
`ads.hero_analysis.overall_score` so you can query it directly from Supabase
or use it later for ranking/analytics. Existing rows without a score will simply
have the field omitted/`null`.

## Indexing ads

Local directory ingestion:

```bash
python -m tvads_rag.index_ads --source local --limit 50
```

S3 ingestion (downloads each object to a temp file first):

```bash
python -m tvads_rag.index_ads --source s3 --limit 100
```

Helpful flags:

- `--offset N` – skip the first `N` files/keys
- `--single-path /path/to/ad.mp4` – process exactly one local file
- `--single-key ads/sample.mp4` – process exactly one S3 key

The CLI automatically:

1. Skips ads already present (matching `external_id` or `s3_key`)
2. Probes media metadata with `ffprobe`
3. Extracts mono 16 kHz WAV audio via `ffmpeg`
4. Runs `transcribe_audio()` (Whisper API or stub)
5. Sends transcripts to `analyse_ad_transcript()` for structured JSON
6. Inserts ads + child tables + embeddings

## Query demo

```bash
python -m tvads_rag.query_demo --query "ads promising free trials" --top-k 5
```

The script embeds the query, performs `pgvector` similarity search across
`transcript_chunk`, `segment_summary`, and `claim` items, and prints friendly
results with brand/product context. Use `--item-types` to tweak the search set.

## Testing

```bash
pytest
```

The suite covers JSON parsing resilience, media helper edge cases, and storyboard parsing utilities. Add new tests alongside modules before expanding functionality (TDD-friendly).

## Operational tips

- `EMBED_BATCH_SIZE` tunes embedding throughput (default `64`).
- Set `LOG_LEVEL=DEBUG` for verbose CLI output.
- When iterating prompts locally, set `USE_DUMMY_ASR=1` to avoid ASR costs and
  combine with smaller `--limit` slices.
- **Parallel ingestion**: By default, 3 ads are processed concurrently. Adjust via
  `INGEST_PARALLEL_WORKERS` (e.g., `INGEST_PARALLEL_WORKERS=5`). Higher values = faster
  throughput but may hit API rate limits. Expected speedup: ~2.5-3x with 3 workers.

