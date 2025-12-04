# TellyAds Migration Implementation Pack

## Overview

This document provides the complete implementation checklist for migrating TellyAds from Wix CMS to the new architecture with:
- Editorial sidecar table (human-authored content)
- User feedback system (likes, saves, tags)
- SEO-friendly URL routing

## Files Created

| File | Purpose |
|------|---------|
| `tvads_rag/schema_editorial_feedback.sql` | Schema migration DDL |
| `tvads_rag/schema_editorial_feedback_verify.sql` | QA validation queries |
| `backend/main.py` | Updated with feedback endpoints |
| `docs/MIGRATION_CHECKLIST.md` | This document |

---

## Phase 1: Database Migration

### Step 1.1: Apply Schema Migration

```bash
# Connect to Supabase and run migration
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback.sql
```

### Step 1.2: Verify Schema

```bash
# Run verification queries
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback_verify.sql
```

**Expected output:**
- All tables exist: `ad_editorial`, `ad_user_reactions`, `ad_user_tags`, `ad_feedback_agg`, `ad_rate_limits`
- All indexes exist
- All functions exist
- All triggers exist
- All views exist
- Test queries pass

### Step 1.3: Schema Checklist

- [ ] Tables created
- [ ] Indexes created
- [ ] Unique constraints active
- [ ] Trigger functions installed
- [ ] Views created
- [ ] Test toggle/view/tag functions work
- [ ] No orphaned records

---

## Phase 2: Excel Import

### Step 2.1: Prepare Excel Mapping

Map Wix CMS Excel columns to `ad_editorial` columns:

| Excel Column | Target Column | Notes |
|--------------|---------------|-------|
| `title` | `headline` | Human editorial headline |
| `link-tellyads-ads-title` | `slug` | URL slug (lowercase, hyphenated) |
| `brand_slug` | `brand_slug` | Derived from brand name |
| `description` | `editorial_summary` | Human description |
| `_id` | `wix_item_id` | For deduplication |
| `_createdDate` | `original_publish_date` | Original Wix publish date |

### Step 2.2: Create Import Script

```python
# scripts/import_wix_editorial.py

import pandas as pd
from slugify import slugify
from tvads_rag.tvads_rag import db_backend

def import_editorial(excel_path: str):
    df = pd.read_excel(excel_path)

    conn = db_backend.get_connection()
    with conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                # Find matching ad by external_id or title match
                cur.execute("""
                    SELECT id FROM ads
                    WHERE external_id = %s OR brand_name ILIKE %s
                    LIMIT 1
                """, (row.get('external_id'), row.get('brand_name')))

                ad_row = cur.fetchone()
                if not ad_row:
                    print(f"SKIP: No ad match for {row.get('title')}")
                    continue

                ad_id = ad_row['id']
                brand_slug = slugify(row.get('brand_name', ''))
                slug = slugify(row.get('title', ''))

                cur.execute("""
                    INSERT INTO ad_editorial (
                        ad_id, brand_slug, slug, headline, editorial_summary,
                        wix_item_id, original_publish_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (wix_item_id) DO UPDATE SET
                        headline = EXCLUDED.headline,
                        editorial_summary = EXCLUDED.editorial_summary,
                        updated_at = now()
                """, (
                    ad_id, brand_slug, slug,
                    row.get('title'),
                    row.get('description'),
                    row.get('_id'),
                    row.get('_createdDate')
                ))

            conn.commit()
```

### Step 2.3: Excel Import Checklist

- [ ] Excel file cleaned (remove duplicates)
- [ ] Brand slugs generated
- [ ] URL slugs generated and unique
- [ ] Wix IDs mapped for deduplication
- [ ] Import script tested on sample
- [ ] Full import completed
- [ ] Orphan check passed

---

## Phase 3: API Deployment

### Step 3.1: New Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/ads/{external_id}/view` | Record view |
| `POST` | `/api/ads/{external_id}/like` | Toggle like |
| `POST` | `/api/ads/{external_id}/save` | Toggle save |
| `GET` | `/api/ads/{external_id}/feedback` | Get feedback stats |
| `POST` | `/api/ads/{external_id}/tags` | Suggest tag |
| `GET` | `/api/ads/{external_id}/tags` | Get approved tags |
| `GET` | `/api/advert/{brand_slug}/{slug}` | SEO-friendly route |
| `GET` | `/api/admin/tags/pending` | Moderation queue |
| `PATCH` | `/api/admin/tags/{tag_id}` | Moderate tag |

### Step 3.2: Backend Deployment

```bash
# Redeploy backend
cd backend
# Railway/Render/Fly.io deployment command
```

### Step 3.3: API Checklist

- [ ] Backend redeployed
- [ ] `/api/status` returns online
- [ ] View recording works
- [ ] Like toggle works
- [ ] Save toggle works
- [ ] Feedback retrieval works
- [ ] Tag suggestion works
- [ ] SEO slug route works
- [ ] Rate limiting works (429 on excess)

---

## Phase 4: Frontend Wiring

### Step 4.1: Session ID Generation

Create a privacy-safe random UUID session ID (NO fingerprinting):

```typescript
// lib/session.ts

const SESSION_KEY = 'tellyads_anon_id';

export function getSessionId(): string {
  // Check localStorage first
  if (typeof window !== 'undefined') {
    let sessionId = localStorage.getItem(SESSION_KEY);
    if (sessionId) return sessionId;

    // Generate new random UUID
    sessionId = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
    return sessionId;
  }

  // SSR fallback (won't be used for API calls)
  return 'server-side-no-session';
}
```

**Privacy note**: We use a random UUID stored in localStorage, NOT browser fingerprinting. This is:
- GDPR-compliant (no PII, no cross-site tracking)
- User-resettable (clear localStorage)
- Privacy-respecting (no device identification)

### Step 4.2: Feedback Hooks

```typescript
// hooks/useFeedback.ts
import { useState, useEffect } from 'react';
import { getSessionId } from '@/lib/session';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useFeedback(externalId: string) {
  const [feedback, setFeedback] = useState(null);
  const [isLiked, setIsLiked] = useState(false);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    const sessionId = getSessionId();  // Sync function now
    fetch(`${API_URL}/api/ads/${externalId}/feedback?session_id=${sessionId}`)
      .then(res => res.json())
      .then(data => {
        setFeedback(data);
        setIsLiked(data.user_reaction?.is_liked || false);
        setIsSaved(data.user_reaction?.is_saved || false);
      });
  }, [externalId]);

  const toggleLike = async () => {
    const sessionId = getSessionId();
    const res = await fetch(`${API_URL}/api/ads/${externalId}/like`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    setIsLiked(data.is_liked);
  };

  const toggleSave = async () => {
    const sessionId = getSessionId();
    const res = await fetch(`${API_URL}/api/ads/${externalId}/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    setIsSaved(data.is_saved);
  };

  return { feedback, isLiked, isSaved, toggleLike, toggleSave };
}
```

### Step 4.3: Frontend Checklist

- [ ] Session ID utility created (`lib/session.ts`)
- [ ] Feedback hook created (`hooks/useFeedback.ts`)
- [ ] Like button wired
- [ ] Save button wired
- [ ] View tracking on page load
- [ ] Tag suggestion UI (optional)

**Note**: NO FingerprintJS needed. We use a simple random UUID in localStorage.

---

## Phase 5: URL Migration

### Step 5.1: Frontend Route

Add SEO-friendly route in Next.js:

```typescript
// app/advert/[brand_slug]/[slug]/page.tsx

export async function generateMetadata({ params }) {
  const { brand_slug, slug } = params;
  const ad = await fetch(`${API_URL}/api/advert/${brand_slug}/${slug}`).then(r => r.json());

  return {
    title: `${ad.headline} | ${ad.brand_name} | TellyAds`,
    description: ad.description,
  };
}

export default async function AdvertPage({ params }) {
  const { brand_slug, slug } = params;
  const ad = await fetch(`${API_URL}/api/advert/${brand_slug}/${slug}`).then(r => r.json());

  return <AdDetailView ad={ad} />;
}
```

### Step 5.2: Redirect Old URLs

Add redirects in `next.config.js`:

```javascript
// next.config.js
module.exports = {
  async redirects() {
    return [
      {
        source: '/ads/:external_id',
        destination: '/advert/:brand_slug/:slug',
        permanent: true,
        has: [{ type: 'query', key: 'legacy', value: 'true' }],
      },
    ];
  },
};
```

### Step 5.3: URL Migration Checklist

- [ ] New `/advert/[brand_slug]/[slug]` route created
- [ ] SEO metadata working
- [ ] Old URLs redirect (301)
- [ ] Sitemap updated
- [ ] Google Search Console reindex requested

---

## Phase 6: Moderation Setup

### Step 6.1: Admin UI

Create minimal admin page for tag moderation:

```typescript
// app/admin/tags/page.tsx
export default async function TagModerationPage() {
  const pendingTags = await fetch(`${API_URL}/api/admin/tags/pending`).then(r => r.json());

  return (
    <div>
      <h1>Tag Moderation Queue</h1>
      {pendingTags.tags.map(tag => (
        <TagModerationCard key={tag.id} tag={tag} />
      ))}
    </div>
  );
}
```

### Step 6.2: Moderation Checklist

- [ ] Admin page created
- [ ] Approve/reject buttons work
- [ ] Approved tags appear on ads
- [ ] Spam tags flagged for analysis

---

## Rollback Plan

### Database Rollback

```sql
-- Drop new tables (ORDER MATTERS due to FKs)
DROP VIEW IF EXISTS v_tag_moderation_queue;
DROP VIEW IF EXISTS v_ad_with_editorial;
DROP FUNCTION IF EXISTS fn_cleanup_rate_limits();
DROP FUNCTION IF EXISTS fn_suggest_tag(uuid, text, text);
DROP FUNCTION IF EXISTS fn_toggle_save(uuid, text);
DROP FUNCTION IF EXISTS fn_toggle_like(uuid, text);
DROP FUNCTION IF EXISTS fn_record_ad_view(uuid, text);
DROP TRIGGER IF EXISTS trg_tag_counts ON ad_user_tags;
DROP TRIGGER IF EXISTS trg_reaction_agg ON ad_user_reactions;
DROP FUNCTION IF EXISTS fn_update_tag_counts();
DROP FUNCTION IF EXISTS fn_update_feedback_agg_on_reaction();
DROP TABLE IF EXISTS ad_rate_limits;
DROP TABLE IF EXISTS ad_feedback_agg;
DROP TABLE IF EXISTS ad_user_tags;
DROP TABLE IF EXISTS ad_user_reactions;
DROP TABLE IF EXISTS ad_editorial;
```

### API Rollback

Revert `backend/main.py` to previous version via git.

---

## Phase 7: Micro-Reasons Feedback

### Step 7.1: Apply Micro-Reasons Migration

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons.sql
```

### Step 7.2: Verify Micro-Reasons Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons_verify.sql
```

**Expected output:**
- `ad_like_reasons` table exists
- New columns on `ad_feedback_agg`: `reason_counts`, `reason_total`, `blended_score`
- Indexes and triggers created
- Test queries pass

### Step 7.3: New Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/reason-labels` | Get predefined reason labels for UI |
| `POST` | `/api/ads/{external_id}/reasons` | Submit reasons for like/save |
| `GET` | `/api/ads/{external_id}/reasons` | Get reason counts + user's reasons |

### Step 7.4: Frontend UI Integration

After a user likes or saves an ad, show a follow-up prompt:

```typescript
// components/ReasonPrompt.tsx
import { useState } from 'react';
import { getSessionId } from '@/lib/session';

const REASONS = [
  { reason: 'funny', label: 'Funny' },
  { reason: 'clever_idea', label: 'Clever idea' },
  { reason: 'emotional', label: 'Emotional' },
  { reason: 'great_twist', label: 'Great twist/ending' },
  { reason: 'beautiful_visually', label: 'Beautiful visually' },
  { reason: 'memorable_music', label: 'Memorable music' },
  { reason: 'relatable', label: 'Relatable' },
  { reason: 'effective_message', label: 'Effective message' },
  { reason: 'nostalgic', label: 'Nostalgic' },
  { reason: 'surprising', label: 'Surprising' },
];

export function ReasonPrompt({ externalId, reactionType, onClose }) {
  const [selected, setSelected] = useState<string[]>([]);

  const submit = async () => {
    if (selected.length === 0) {
      onClose();
      return;
    }
    const sessionId = getSessionId();
    await fetch(`${API_URL}/api/ads/${externalId}/reasons`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        reasons: selected,
        reaction_type: reactionType,
      }),
    });
    onClose();
  };

  return (
    <div className="reason-prompt">
      <h4>Why did you {reactionType} this?</h4>
      <div className="reason-chips">
        {REASONS.map(r => (
          <button
            key={r.reason}
            className={selected.includes(r.reason) ? 'selected' : ''}
            onClick={() => setSelected(prev =>
              prev.includes(r.reason)
                ? prev.filter(x => x !== r.reason)
                : [...prev, r.reason]
            )}
          >
            {r.label}
          </button>
        ))}
      </div>
      <button onClick={submit}>Done</button>
      <button onClick={onClose}>Skip</button>
    </div>
  );
}
```

### Step 7.5: Micro-Reasons Checklist

- [ ] Schema migration applied
- [ ] Verification queries pass
- [ ] `/api/reason-labels` returns 10 labels
- [ ] `/api/ads/{id}/reasons` POST works
- [ ] `/api/ads/{id}/feedback` includes `reason_counts` and `blended_score`
- [ ] Rate limiting works (429 after 20 reasons/hour)
- [ ] Blended score increases with reasons

---

## Phase 8: Scoring V2 (AI + User Blended)

### Step 8.1: Apply Scoring V2 Migration

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2.sql
```

### Step 8.2: Verify Scoring V2 Schema

```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2_verify.sql
```

**Expected output:**
- New columns: `ai_score`, `user_score`, `final_score`, `distinct_reason_sessions`, `confidence_weight`
- Functions: `fn_compute_ai_score`, `fn_compute_user_score`, `fn_compute_confidence_weight`
- Anti-gaming tests pass (distinct sessions, not raw counts)
- Threshold display tests pass

### Step 8.3: Scoring Formula

```
final_score = ai_score * (1 - confidence_weight) + user_score * confidence_weight
```

**Components:**

| Component | Range | Source |
|-----------|-------|--------|
| `ai_score` | 0-100 | Average of impact_scores fields (pulse, echo, hook_power, etc.) |
| `user_score` | 0-100 | Engagement (70 max) + Reason bonus (30 max) |
| `confidence_weight` | 0.0-0.6 | Linear ramp: `min(0.6, total_signals/50 * 0.6)` |

**Behavior:**
- At 0 engagement: `final_score = ai_score` (AI dominates 100%)
- At 50+ signals: `final_score = ai_score*0.4 + user_score*0.6` (user gets max 60%)

### Step 8.4: Anti-Gaming Changes

| Before | After |
|--------|-------|
| `reason_total` (raw count) | `distinct_reason_sessions` (unique users) |
| Reason bonus per row | Reason bonus per unique session |
| Public reason_counts always | Hidden until 10+ distinct sessions |

### Step 8.5: Updated API Response

`GET /api/ads/{external_id}/feedback` now returns:

```json
{
  "view_count": 150,
  "like_count": 25,
  "save_count": 10,
  "ai_score": 72.5,
  "user_score": 45.2,
  "confidence_weight": 0.42,
  "final_score": 60.8,
  "reason_counts": {"funny": 8, "emotional": 5},
  "distinct_reason_sessions": 12,
  "reason_threshold_met": true
}
```

### Step 8.6: Scoring V2 Checklist

- [ ] Schema migration applied
- [ ] Backfill script ran for existing ads
- [ ] AI scores computed from impact_scores
- [ ] Distinct session counting works
- [ ] Duplicate reasons rejected (UNIQUE constraint)
- [ ] reason_counts hidden below threshold (10 sessions)
- [ ] Final score blends correctly at different engagement levels
- [ ] Verification queries pass

---

## Thresholds Reference

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Ranking boost threshold (likes) | 5+ | Requires meaningful engagement |
| Ranking boost threshold (saves) | 3+ | Saves indicate higher intent |
| Engagement score min views | 10 | Prevents score inflation on low traffic |
| Rate limit: likes/hour | 50 | Prevents spam |
| Rate limit: tags/hour | 10 | Prevents tag flooding |
| Rate limit: views/ad/hour | 10 | Prevents view inflation |
| Rate limit: reasons/hour | 20 | Prevents reason flooding |
| Reason diversity bonus | +0.5 per type | Max +5 for all 10 types |
| Reason volume bonus | +0.1 per submission | Max +10, capped |

---

## Environment Variables

Add these to your `.env`:

```bash
# Required for admin endpoints
ADMIN_API_KEY=your-secure-random-key-here

# Generate a secure key:
# openssl rand -hex 32
```

---

## Summary

This migration adds:

1. **Editorial Sidecar** (`ad_editorial`) - Human content separate from extractor
2. **User Reactions** (`ad_user_reactions`) - State-based likes/saves
3. **User Tags** (`ad_user_tags`) - Moderated community tags
4. **Feedback Aggregation** (`ad_feedback_agg`) - Derived metrics for ranking
5. **Rate Limiting** (`ad_rate_limits`) - Anti-gaming protection
6. **SEO Routes** - `/advert/{brand}/{slug}` URL structure
7. **Micro-Reasons** (`ad_like_reasons`) - "Why did you like this?" feedback for enhanced ranking

All corrections applied:
- A) Likes use state table (not event log)
- B) No duplicate tag storage
- C) Proper Postgres partial unique indexes
- D) Views use counter increment
- E) Ranking boosts only after thresholds
- F) Blended score formula integrates reason diversity + volume
