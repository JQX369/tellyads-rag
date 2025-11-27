AGENT-SETUP
agent: product/trend-researcher
memory.loaded:
  - agents/_memory/product-vision.md
plan:
  - confirm objective
  - surface constraints & glossary items relevant to task
  - execute deliverable
  - update decisions.log.md + agent memory (append-only)
guardrails:
  - Do not edit product-vision.md without explicit "APPROVE: VISION CHANGE".
END

# RAG Architecture & Best Practices Review (2025)

## 1. Findings from Research
To ensure the TellyAds RAG is "perfect" and future-proof, we validated the current stack against late 2024/2025 SOTA practices.

### Strengths (Keep)
- **Gemini 1.5 Pro for Vision**: Excellent choice. It has a massive context window (1M+ tokens) and native video understanding, making it superior to frame-by-frame captioning for "story" understanding.
- **Supabase/pgvector**: Solid foundation. It scales well for ~20k ads and keeps the stack simple (no separate vector DB).

### Gaps (Must Add)
- **Hybrid Search**: Relying solely on embeddings (Cosine Similarity) is weak for specific entities (e.g., "ads for the 'X5' model"). We *must* implement Hybrid Search (Keyword `tsvector` + Semantic `vector`).
  - *Recommendation*: Use Reciprocal Rank Fusion (RRF) in a Supabase Postgres function.
- **Re-ranking**: This is the single biggest "easy win" for quality. Fetching 50 candidates and re-ranking the top 10 using a specialized model (e.g., BGE-Reranker or Cohere) drastically reduces hallucinations.
- **Evaluation**: We cannot claim "perfection" without measurement. We need an automated eval script (`evaluate_rag.py`) that runs a set of 50 questions with known-good answers and scores the system.

## 2. Proposed Architecture Updates
1.  **Database**: Update `search_ads` RPC function to perform Hybrid Search.
2.  **Indexing**: Ensure we are indexing explicit keywords (brand, product, claims) into a Postgres `tsvector` column alongside the embeddings.
3.  **Query Pipeline**:
    -   Step 1: Retrieve 50 candidates via Hybrid Search.
    -   Step 2: Re-rank top 50 -> top 10 using a Cross-Encoder (local or API).
    -   Step 3: Generate answer using GPT-4o with the top 10 chunks.

## 3. Next Steps (Plan)
1.  **Approve** this refined architecture.
2.  **Implement** Hybrid Search in Supabase (SQL migration).
3.  **Add** Re-ranking logic to the Python query handler.

