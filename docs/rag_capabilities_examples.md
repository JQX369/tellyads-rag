# RAG Database Capabilities & Examples

## ✅ What You CAN Do (Current Configuration)

### 1. **Semantic & Keyword Hybrid Search**
Your RAG combines **vector similarity** (semantic understanding) with **keyword matching** (exact terms), so you get both conceptual matches and precise brand/product lookups.

**Example Queries:**
- ✅ "Find ads that use nostalgia to sell family products"
- ✅ "Show me car commercials with road trip scenes"
- ✅ "Ads mentioning 'limited time offer' or price discounts"
- ✅ "Commercials with celebrity endorsements"
- ✅ "Find ads targeting security/status emotions"

**What You Get:**
- Ranked results with **RRF scores** (Reciprocal Rank Fusion)
- **Rerank scores** (if Cohere enabled) for precision
- Full context: brand, product, transcript snippets, metadata

---

### 2. **Creative Structure Analysis**
Every ad is broken down into **segments** (hook, problem, solution, proof, offer, CTA) with **AIDA stages** (Attention, Interest, Desire, Action) and **emotion focus** (security, status, belonging, urgency).

**Example Queries:**
- ✅ "Show me ads where the hook happens in the first 3 seconds"
- ✅ "Find commercials that use 'desire' stage for luxury products"
- ✅ "Ads with 'urgency' emotion focus"
- ✅ "Commercials structured as problem → solution narratives"

**What You Get:**
- Timestamped segments (`start_time`, `end_time`)
- Segment summaries and transcript snippets
- AIDA stage mapping per segment
- Emotion classification

---

### 3. **Claims & Substantiation Tracking**
Every **claim** (price promises, quality statements, guarantees) is extracted with flags for **comparative claims** and **likely needs substantiation**.

**Example Queries:**
- ✅ "Find all price claims across automotive ads"
- ✅ "Show me comparative claims (brand X vs brand Y)"
- ✅ "Ads with guarantees or warranties"
- ✅ "Claims that likely need regulatory substantiation"

**What You Get:**
- Claim text + classification (`claim_type`: price/quality/speed/guarantee/comparison/risk)
- Boolean flags: `is_comparative`, `likely_needs_substantiation`
- Linked to parent ad for context

---

### 4. **On-Screen Text (Supers) Extraction**
All **on-screen legal/offer text** is captured with timestamps and classification.

**Example Queries:**
- ✅ "Find ads with legal disclaimers"
- ✅ "Show me commercials with eligibility requirements on screen"
- ✅ "Ads with price supers (on-screen pricing)"

**What You Get:**
- Super text + timestamps (`start_time`, `end_time`)
- Classification: `super_type` (price/legal/eligibility/other)

---

### 5. **Visual Storyboard Search** (If Vision Enabled)
When `VISION_PROVIDER=google`, you get **shot-by-shot visual analysis** with camera style, location hints, key objects, and mood.

**Example Queries:**
- ✅ "Find ads shot in kitchens"
- ✅ "Commercials with 'handheld close-up' camera style"
- ✅ "Ads featuring product packs prominently"
- ✅ "Visuals with 'warm & nostalgic' mood"

**What You Get:**
- Shot-level descriptions (`shot_label`, `description`)
- Camera style (`camera_style`)
- Location hints (`location_hint`)
- Key objects array (`key_objects`)
- Mood classification (`mood`)

---

### 6. **Metadata Filtering & Aggregation**
Rich metadata on every ad: brand, product category, year, country, format type, music style, editing pace, color mood.

**Example Queries:**
- ✅ "All 2024 automotive ads"
- ✅ "UK ads with 'fast' editing pace"
- ✅ "Ads with 'energetic' music style"
- ✅ "Commercials in 'warm' color mood"

**What You Get:**
- Structured metadata fields (brand_name, product_category, year, country, etc.)
- Creative attributes (music_style, editing_pace, colour_mood)
- Format classification (format_type)

---

### 7. **Multi-Granularity Search**
You can search at different levels: **chunks** (short transcript snippets), **segments** (structural sections), **claims**, **supers**, **storyboard shots**, or **ad summaries**.

**Example Queries:**
- ✅ "Search only in claims" → Find specific promises
- ✅ "Search only in storyboard shots" → Visual-only queries
- ✅ "Search in segment summaries" → High-level narrative search

**What You Get:**
- Filterable by `item_type` in the hybrid search function
- Each level has different granularity (chunks = detailed, summaries = overview)

---

## ❌ What You CAN'T Do (But Could With Different Config)

### 1. **Multi-Language Support**
**Current:** English-only (`to_tsvector('english', ...)` in schema).

**Could Enable:**
- Change `to_tsvector('english', ...)` to `to_tsvector('simple', ...)` for language-agnostic keyword search
- Use multilingual embedding models (e.g., `text-embedding-3-large` supports 100+ languages, but you'd need to configure language detection)
- Add `language` field filtering in queries

**Example Use Cases:**
- ❌ "Find Spanish-language ads"
- ✅ **Could:** "Search across all languages" or "Filter by language field"

---

### 2. **Temporal Trend Analysis**
**Current:** `year` field exists, but no time-series aggregation or trend detection.

**Could Enable:**
- Add SQL views/functions for year-over-year comparisons
- Aggregate by month/quarter if you add `created_at` metadata
- Build trend dashboards (e.g., "How did 'urgency' emotion usage change 2020-2025?")

**Example Use Cases:**
- ❌ "Show me trends in celebrity usage over time"
- ✅ **Could:** "Compare 2023 vs 2024 ad structures" (if you add aggregation queries)

---

### 3. **Competitive Analysis (Brand Comparisons)**
**Current:** You can search by brand, but no built-in comparison tools.

**Could Enable:**
- Add SQL functions to compare two brands side-by-side
- Aggregate claims/emotions by brand
- Build "brand X vs brand Y" comparison views

**Example Use Cases:**
- ❌ "Compare BMW vs Mercedes ad strategies"
- ✅ **Could:** "Show me all BMW ads" + "Show me all Mercedes ads" → Manual comparison

---

### 4. **Audio Analysis (Music, Voice, Sound Effects)**
**Current:** Only transcript text is analyzed. No audio feature extraction.

**Could Enable:**
- Add audio analysis pipeline (music genre detection, voice gender/age, sound effects)
- Use Whisper's language detection + speaker diarization
- Store audio features in metadata

**Example Use Cases:**
- ❌ "Find ads with upbeat music"
- ❌ "Commercials with female voiceover"
- ✅ **Could:** Add `music_genre`, `voice_gender` fields if you extend the analysis prompt

---

### 5. **Sentiment Analysis at Scale**
**Current:** Emotion focus is captured (security/status/belonging/urgency), but not granular sentiment (positive/negative/neutral).

**Could Enable:**
- Add sentiment scoring to chunks/segments
- Use a sentiment analysis model in the pipeline
- Store sentiment scores in metadata

**Example Use Cases:**
- ❌ "Find ads with negative sentiment in problem segments"
- ✅ **Could:** Add sentiment field to `ad_segments` table + analysis prompt

---

### 6. **Product Category Hierarchies**
**Current:** Flat `product_category` and `product_subcategory` fields.

**Could Enable:**
- Build a taxonomy/hierarchy table
- Enable parent-child category queries
- Add category similarity search

**Example Use Cases:**
- ❌ "Find all automotive ads (including subcategories)"
- ✅ **Could:** "Find all 'automotive' ads" (manual filtering)

---

### 7. **A/B Testing & Variant Detection**
**Current:** No variant grouping (same campaign, different cuts).

**Could Enable:**
- Add `campaign_id` or `variant_group` field
- Group ads by campaign for comparison
- Detect similar ads (same brand/product, different creative)

**Example Use Cases:**
- ❌ "Show me all variants of the Nike 'Just Do It' campaign"
- ✅ **Could:** Add `campaign_id` field + grouping queries

---

### 8. **Regulatory Compliance Checking**
**Current:** `regulator_sensitive` flag exists, but no automated compliance rules.

**Could Enable:**
- Add compliance rule engine (e.g., "If price claim → must have super")
- Flag ads missing required disclaimers
- Cross-reference with regulatory databases

**Example Use Cases:**
- ❌ "Find ads with price claims but no price super"
- ✅ **Could:** SQL query: `WHERE has_price_claims = true AND has_supers = false`

---

### 9. **Performance Metrics Integration**
**Current:** No performance data (views, engagement, conversions).

**Could Enable:**
- Import performance data from analytics platforms
- Join ads table with performance metrics
- Enable queries like "Show me top-performing ads by engagement"

**Example Use Cases:**
- ❌ "Find high-performing ads (by views/CTR)"
- ✅ **Could:** Add `performance_metrics` JSONB column + import script

---

### 10. **Real-Time Ingestion & Updates**
**Current:** Batch ingestion via CLI.

**Could Enable:**
- Webhook-based ingestion (new ad uploaded → auto-index)
- Incremental updates (re-analyze changed ads only)
- Real-time search index updates

**Example Use Cases:**
- ❌ "Auto-index new ads as they're uploaded"
- ✅ **Could:** Add webhook endpoint + background job queue

---

## 🎯 Summary: Current vs. Potential

| Capability | Current | Could Enable |
| :--- | :--- | :--- |
| **Hybrid Search** | ✅ Semantic + Keyword | ✅ Already optimal |
| **Visual Analysis** | ✅ If Vision enabled | ✅ Already optimal |
| **Multi-Language** | ❌ English only | ✅ Change tsvector config |
| **Trend Analysis** | ❌ No aggregation | ✅ Add SQL views |
| **Audio Features** | ❌ Text only | ✅ Extend analysis prompt |
| **Sentiment Scoring** | ❌ Emotion only | ✅ Add sentiment model |
| **Category Hierarchies** | ❌ Flat structure | ✅ Add taxonomy table |
| **A/B Variants** | ❌ No grouping | ✅ Add campaign_id |
| **Compliance Rules** | ❌ Flag only | ✅ Add rule engine |
| **Performance Data** | ❌ Not stored | ✅ Import + join |
| **Real-Time Updates** | ❌ Batch only | ✅ Webhook + queue |

**Bottom Line:** Your current setup is **excellent** for semantic search, creative analysis, and structured metadata queries. The "could enable" items are **add-ons** that require schema changes, additional models, or integration work—but the foundation is solid.





