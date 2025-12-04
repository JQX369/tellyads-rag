# RAG Extraction Pipeline Explanation

## Overview
This application implements a **Retrieval-Augmented Generation (RAG)** pipeline for TV advertisements. It extracts structured metadata from video ads, generates embeddings, and stores them in a vector database for semantic search and retrieval.

## Pipeline Architecture

### 1. **Video Ingestion** (`index_ads.py`, `media.py`)
- **Input Sources**: Local directory or S3 bucket
- **Process**: 
  - Lists video files (`.mp4`, `.mov`, `.mkv`, `.avi`, `.m4v`, `.mpg`, `.mpeg`)
  - For S3: Downloads each video to a temporary file
  - Checks for duplicates using `external_id` or `s3_key` (idempotent processing)
- **Output**: Video file path ready for processing

### 2. **Media Probing** (`media.py::probe_media()`)
- **Tool**: `ffprobe` (FFmpeg)
- **Extracts**:
  - Duration (seconds)
  - Resolution (width × height)
  - Frame rate (fps)
  - Aspect ratio
- **Purpose**: Technical metadata stored in `ads` table

### 3. **Audio Extraction** (`media.py::extract_audio()`)
- **Tool**: `ffmpeg`
- **Process**: 
  - Extracts audio track from video
  - Converts to mono 16kHz WAV format (optimal for ASR)
  - Saves to temporary directory
- **Output**: Audio file path for transcription

### 4. **Automatic Speech Recognition (ASR)** (`asr.py::transcribe_audio()`)
- **Service**: OpenAI Whisper API (`whisper-1` model)
- **Input**: Mono 16kHz WAV audio file
- **Output**: JSON transcript with:
  - Full text transcription
  - Timestamped segments (`start`, `end`, `text`)
- **Fallback**: Dummy stub mode for testing (`USE_DUMMY_ASR=1`)

### 5. **LLM-Powered Transcript Analysis** (`analysis.py::analyse_ad_transcript()`)
- **Service**: GPT-4 (or compatible model via `LLM_MODEL_NAME`)
- **Input**: Transcript text + segments
- **Process**:
  - Sends structured prompt to LLM requesting JSON output
  - LLM analyzes transcript and extracts:
    - **Ad Metadata**: Brand, product, category, objective, funnel stage, creative attributes
    - **Segments**: Structural sections (hook/problem/solution/proof/offer/CTA) with AIDA stages, emotion focus, summaries
    - **Chunks**: Smaller transcript pieces with tags and AIDA stages
    - **Claims**: Key promises/statements (price, quality, speed, guarantees) with comparative flags
    - **Supers**: On-screen text (legal disclaimers, price offers, eligibility)
- **Output**: Structured JSON dictionary
- **Resilience**: JSON repair logic if LLM output is malformed

### 6. **Optional Visual Storyboard Analysis** (`visual_analysis.py`)
- **Service**: Google Gemini Vision API (optional, enabled via `VISION_PROVIDER=google`)
- **Process**:
  - Samples frames from video using `ffmpeg` (configurable interval via `FRAME_SAMPLE_SECONDS`, default 1.0s)
  - Limits to 24 frames max (Gemini constraint)
  - Sends frames + prompt to Gemini
  - Gemini groups frames into coherent **shots** (continuous camera moments)
  - Extracts: shot labels, descriptions, camera style, location hints, key objects, mood, on-screen text
- **Output**: List of storyboard shot dictionaries
- **Storage**: `ad_storyboards` table

### 7. **Database Storage** (`db.py`)
- **Database**: Supabase Postgres with `pgvector` extension
- **Tables**:
  - `ads`: Master table with metadata and raw JSON
  - `ad_segments`: Structural segments
  - `ad_chunks`: Transcript chunks
  - `ad_claims`: Marketing claims
  - `ad_supers`: On-screen text
  - `ad_storyboards`: Visual storyboard shots (optional)
  - `embedding_items`: Vector embeddings for semantic search
- **Process**:
  1. Insert ad record → get `ad_id`
  2. Insert child records (segments, chunks, claims, supers, storyboards) → get IDs
  3. Prepare embedding items from all text sources
  4. Generate embeddings (see step 8)
  5. Insert embedding items with vectors

### 8. **Embedding Generation** (`embeddings.py::embed_texts()`)
- **Service**: OpenAI Embeddings API (`text-embedding-3-small` by default, 1536 dimensions)
- **Input**: Text strings from:
  - Transcript chunks
  - Segment summaries
  - Claims
  - Supers
  - Storyboard shot descriptions (if enabled)
  - Ad summary (one-line + story summary)
- **Process**:
  - Batches texts (default batch size: 64)
  - Calls embedding API
  - Returns vectors in same order as input
- **Output**: 1536-dimensional vectors stored in `embedding_items.embedding` (pgvector type)

### 9. **Query/Retrieval** (`query_demo.py`)
- **Process**:
  1. User provides natural language query
  2. Query text is embedded using same embedding model
  3. Vector similarity search using pgvector `<->` operator (cosine distance)
  4. Results ranked by similarity score
  5. Returns top-K matches with context (brand, product, summary)
- **Searchable Item Types**:
  - `transcript_chunk`: Raw transcript pieces
  - `segment_summary`: High-level segment summaries
  - `claim`: Marketing claims
  - `super`: On-screen text
  - `storyboard_shot`: Visual descriptions (if enabled)
  - `ad_summary`: Overall ad summaries

## Data Flow Diagram

```
Video File (local/S3)
    ↓
[Media Probing] → Technical Metadata
    ↓
[Audio Extraction] → Mono 16kHz WAV
    ↓
[ASR (Whisper)] → Transcript + Timestamps
    ↓
[LLM Analysis (GPT)] → Structured JSON
    ├─→ Ad Metadata
    ├─→ Segments
    ├─→ Chunks
    ├─→ Claims
    └─→ Supers
    ↓
[Optional: Visual Analysis (Gemini)] → Storyboard Shots
    ↓
[Embedding Generation] → Vector Embeddings (1536-dim)
    ↓
[Database Storage] → Supabase Postgres + pgvector
    ↓
[Query Interface] → Semantic Search Results
```

## Key Design Decisions

1. **Dual-Model Approach**: GPT for text analysis, Gemini for vision (keeps providers separated)
2. **Idempotent Processing**: Skips already-indexed ads (checks `external_id`/`s3_key`)
3. **Structured Extraction**: LLM extracts structured JSON rather than free-form text
4. **Multi-Granularity Embeddings**: Embeds at multiple levels (chunks, segments, claims, summaries) for flexible retrieval
5. **Optional Visual Pass**: Vision analysis is opt-in to avoid unnecessary costs
6. **Batch Embedding**: Processes embeddings in batches for efficiency
7. **JSON Resilience**: Handles malformed LLM JSON output with repair logic
8. **Temporary File Management**: Cleans up audio files and frame samples after processing

## Current Limitations & Considerations

1. **Sequential Processing**: Processes ads one at a time (no parallelization)
2. **Frame Sampling**: Fixed interval sampling (may miss important moments)
3. **Gemini Frame Limit**: Max 24 frames per video (may truncate long ads)
4. **Single Embedding Model**: Uses one model for all text types
5. **No Chunking Strategy**: Transcript chunks come from LLM, not fixed-size windows
6. **No Re-ranking**: Simple vector similarity without cross-encoder re-ranking
7. **No Hybrid Search**: Pure semantic search, no keyword/BM25 combination

## Performance Characteristics

- **Per-Ad Processing Time**: ~30-120 seconds (depends on video length, API latency)
- **Bottlenecks**: 
  - ASR transcription (Whisper API)
  - LLM analysis (GPT API)
  - Visual analysis (Gemini API, if enabled)
  - Embedding generation (OpenAI Embeddings API)
- **Storage**: ~1-5 MB per ad (depending on transcript length and number of embeddings)











