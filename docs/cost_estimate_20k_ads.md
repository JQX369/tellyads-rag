# Cost Estimation for Processing 20,000 TV Ads (Nov 2025)

Based on current API pricing for the SOTA stack (GPT-5.1, Gemini 2.5, Cohere Rerank v3), here is a breakdown of the estimated costs to process **20,000 video ads** (assuming ~30s average duration).

## 1. Video & Vision (Gemini 2.5 Flash)
*Task: Sample frames (1/sec -> 30 frames), multimodal analysis for storyboard & metadata.*

*   **Model**: `gemini-2.5-flash` (Video/Multimodal)
*   **Input**: ~30 seconds video (~300k tokens context equivalent or priced per second)
*   **Rate**: ~$0.10 / 1M tokens (approximate Flash tier pricing)
*   **Cost per Ad**: ~$0.003 (0.3 cents)
*   **Total (20k Ads)**: **~$60 - $100**

## 2. Transcription & Audio (Whisper)
*Task: Extract audio, transcribe to text.*

*   **Model**: OpenAI Whisper API (or local if GPU available)
*   **Rate**: $0.006 / minute
*   **Volume**: 20,000 ads * 0.5 mins = 10,000 minutes
*   **Total (20k Ads)**: **$60**
*   *(Note: Free if running Whisper `large-v3` locally on a GPU).*

## 3. Creative Analysis (GPT-5.1)
*Task: Reason over transcript + vision summary to produce JSON metadata.*

*   **Model**: `gpt-5.1` (High intelligence)
*   **Input**: ~2k tokens (transcript + system prompts)
*   **Output**: ~500 tokens (structured JSON)
*   **Rate (Est)**: $5.00 / 1M in, $15.00 / 1M out (Standard SOTA tier)
*   **Cost per Ad**: ($5 * 0.002) + ($15 * 0.0005) ≈ $0.01 + $0.0075 = $0.0175
*   **Total (20k Ads)**: **~$350**

## 4. Embeddings (OpenAI)
*Task: Embed chunks, claims, descriptions, summaries.*

*   **Model**: `text-embedding-3-large`
*   **Volume**: ~50 chunks/ad * 20k = 1M chunks. ~100 tokens/chunk.
*   **Total Tokens**: 100M tokens.
*   **Rate**: $0.13 / 1M tokens.
*   **Total (20k Ads)**: **~$13** (Negligible)

## 5. Storage (Supabase)
*   **Database**: 20k rows + vectors is small (<1GB).
*   **Plan**: Free tier (500MB) might be tight with metadata/JSONB. Pro Plan is **$25/month**.

---

## 💰 Total Project Estimate (One-time Ingestion)

| Component | Low Est (Local Whisper) | High Est (Full API) |
| :--- | :--- | :--- |
| **Vision (Gemini Flash)** | $60 | $100 |
| **Audio (Whisper)** | $0 | $60 |
| **Analysis (GPT-5.1)** | $350 | $350 |
| **Embeddings** | $13 | $13 |
| **Total** | **~$423** | **~$523** |

### Ongoing Costs (RAG Queries)
*   **Cohere Rerank**: ~$1.00 per 1k queries.
*   **GPT-5.1 Answers**: ~$0.03 per query.
*   **Supabase**: $25/mo fixed.

**Recommendation**: Budget **$600** for the initial ingestion to cover API variances and testing.


