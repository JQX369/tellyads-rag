# TellyAds Release Captain Verification Runbook

**Date:** 2025-12-04
**Version:** 1.0.0

---

## 1. Canonical "Run These" Files

### Migration + Verify SQL (in order)

| Step | File | Purpose |
|------|------|---------|
| 1 | `tvads_rag/schema_editorial_feedback.sql` | Editorial sidecar + feedback tables |
| 2 | `tvads_rag/schema_editorial_feedback_verify.sql` | Verify step 1 |
| 3 | `tvads_rag/schema_micro_reasons.sql` | Micro-reasons tables + blended score |
| 4 | `tvads_rag/schema_micro_reasons_verify.sql` | Verify step 3 |
| 5 | `tvads_rag/schema_scoring_v2.sql` | AI+User blended scoring |
| 6 | `tvads_rag/schema_scoring_v2_verify.sql` | Verify step 5 |
| 7 | `tvads_rag/schema_import_helpers.sql` | Legacy URL tracking + review views |

### Import + Documentation

| File | Purpose |
|------|---------|
| `scripts/import_editorial.py` | Excel/Wix import script |
| `docs/GO_LIVE_PACK.md` | Master go-live documentation |
| `docs/MIGRATION_CHECKLIST.md` | Phase-by-phase checklist |

### Frontend Files

| File | Purpose |
|------|---------|
| `frontend/lib/session.ts` | Anonymous session ID helper |
| `frontend/app/advert/[brand]/[slug]/page.tsx` | SEO route page |
| `frontend/app/sitemap.ts` | Sitemap (needs enhancement) |

---

## 2. Staging Verification Runbook

### Environment Setup

```bash
# Set staging database URL
export SUPABASE_DB_URL="postgresql://..."  # Your staging DB

# Set API URL
export API_URL="https://staging-api.tellyads.com"  # Or localhost:8000

# Set admin key
export ADMIN_API_KEY="your-staging-admin-key"
```

---

### A) Database Migrations (in order)

```bash
# 1. Backup first
pg_dump "$SUPABASE_DB_URL" > backup_staging_$(date +%Y%m%d_%H%M%S).sql

# 2. Apply migrations in order
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2.sql
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_import_helpers.sql
```

**STOP/GO:** If any migration fails with ERROR, STOP immediately.

---

### B) Verify SQL Scripts

```bash
# Run each verify script and capture output
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_editorial_feedback_verify.sql 2>&1 | tee verify_editorial.log
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_micro_reasons_verify.sql 2>&1 | tee verify_micro_reasons.log
psql "$SUPABASE_DB_URL" -f tvads_rag/schema_scoring_v2_verify.sql 2>&1 | tee verify_scoring_v2.log
```

**Review logs for:**
- All `PASS` or `EXISTS` messages
- No `FAIL` or `MISSING` messages
- No ERROR lines

```bash
# Quick check for failures
grep -E "FAIL|MISSING|ERROR" verify_*.log
```

**STOP/GO:** If any `FAIL` or `MISSING` found, STOP and investigate.

---

### C) Dry-Run Import

```bash
# Create test data directory if needed
mkdir -p data

# Run dry-run import
python scripts/import_editorial.py --input data/wix_export.xlsx --dry-run

# Review outputs
ls -la data/*.csv data/*.json
```

**Review these files:**
- `data/matched_*.csv` - Should have records
- `data/unmatched_*.csv` - Review for missing matches
- `data/conflicts_*.csv` - Investigate duplicates
- `data/import_summary_*.json` - Check match_rate >= 80%

```bash
# Check match rate
cat data/import_summary_*.json | grep match_rate
```

**STOP/GO:** If `conflicts.csv` has > 0 rows OR match_rate < 80%, STOP and resolve.

---

### D) Apply Import

```bash
# Only after dry-run review is satisfactory
python scripts/import_editorial.py --input data/wix_export.xlsx --apply

# Verify in database
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) as editorial_count FROM ad_editorial"
psql "$SUPABASE_DB_URL" -c "SELECT * FROM v_import_stats"
```

**STOP/GO:** If inserted_count == 0, STOP and check logs.

---

### E) Backend Smoke Tests

#### E.1: Get a test ad external_id

```bash
# Get first ad for testing
TEST_EXTERNAL_ID=$(curl -s "$API_URL/api/recent?limit=1" | jq -r '.[0].external_id')
echo "Test external_id: $TEST_EXTERNAL_ID"
```

#### E.2: SEO Route Gating

```bash
# First, check if any editorial exists
psql "$SUPABASE_DB_URL" -c "SELECT brand_slug, slug, status FROM ad_editorial LIMIT 5"

# Test published ad returns 200 (replace with actual brand_slug/slug)
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$API_URL/api/advert/specsavers/test-slug"

# Test nonexistent returns 404
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$API_URL/api/advert/nonexistent/fake-slug"
# Expected: HTTP 404
```

#### E.3: Feedback Endpoint

```bash
# Get feedback without session (public view)
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/feedback" | jq '{view_count, like_count, ai_score, user_score, confidence_weight, final_score, reason_threshold_met}'

# Get feedback with session (user-specific state)
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/feedback?session_id=test-session-123" | jq '{user_reaction}'
```

#### E.4: Like Toggle + Verify State

```bash
# Toggle like ON
curl -X POST "$API_URL/api/ads/$TEST_EXTERNAL_ID/like" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test-session"}'
# Expected: {"is_liked": true}

# Verify state persists
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/feedback?session_id=smoke-test-session" | jq '.user_reaction.is_liked'
# Expected: true

# Toggle like OFF
curl -X POST "$API_URL/api/ads/$TEST_EXTERNAL_ID/like" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "smoke-test-session"}'
# Expected: {"is_liked": false}
```

#### E.5: Reason Submission + Rate Limit

```bash
# Submit reasons
curl -X POST "$API_URL/api/ads/$TEST_EXTERNAL_ID/reasons" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "reason-test-session", "reasons": ["funny", "emotional"], "reaction_type": "like"}'
# Expected: {"inserted": 2}

# Verify reasons stored
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/reasons?session_id=reason-test-session" | jq '.user_reasons'

# Test rate limiting (run 25 times)
for i in $(seq 1 25); do
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/ads/$TEST_EXTERNAL_ID/reasons" \
    -H "Content-Type: application/json" \
    -d "{\"session_id\": \"rate-limit-test-$i\", \"reasons\": [\"funny\"], \"reaction_type\": \"like\"}")
  echo "Attempt $i: HTTP $RESULT"
done
# Expected: First ~20 succeed (200), then 429 rate limit
```

#### E.6: Reason Threshold Check

```bash
# Check that reason_counts is hidden when < 10 sessions
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/feedback" | jq '{distinct_reason_sessions, reason_threshold_met, reason_counts}'
# Expected: reason_threshold_met: false, reason_counts: {}
```

#### E.7: Scoring V2 Verification

```bash
# Verify confidence_weight is present and reasonable
curl -s "$API_URL/api/ads/$TEST_EXTERNAL_ID/feedback" | jq '{ai_score, user_score, confidence_weight, final_score}'
# Expected: All fields present, confidence_weight between 0 and 0.6

# Verify in database that confidence_weight excludes views
psql "$SUPABASE_DB_URL" -c "
  SELECT
    ad_id,
    view_count,
    like_count + save_count + distinct_reason_sessions as engagement_signals,
    confidence_weight,
    -- Manually verify: weight = min(0.6, signals/50 * 0.6)
    LEAST(0.6, (like_count + save_count + distinct_reason_sessions)::numeric / 50.0 * 0.6) as expected_weight
  FROM ad_feedback_agg
  LIMIT 5;
"
```

**STOP/GO:** If `confidence_weight` differs from `expected_weight`, STOP - formula is wrong.

---

### F) Frontend Checks

#### F.1: SEO Route Renders

```bash
# Check if frontend dev server is running, or use deployed staging URL
FRONTEND_URL="http://localhost:3000"  # or staging URL

# Test ad page renders (use known brand_slug/slug from database)
curl -s "$FRONTEND_URL/advert/specsavers/test-slug" | head -50

# Check for canonical tag
curl -s "$FRONTEND_URL/advert/specsavers/test-slug" | grep -i canonical
```

#### F.2: Sitemap Check

```bash
# Current sitemap (static routes only for now)
curl -s "$FRONTEND_URL/sitemap.xml"
```

**Note:** Dynamic editorial routes not yet in sitemap - documented as TODO.

#### F.3: Legacy Redirect (NOT YET IMPLEMENTED)

The `resolve-legacy` endpoint and Next.js middleware are documented in GO_LIVE_PACK.md but **not yet implemented**. This is Phase 2 work.

---

## 3. Admin Review Checklist

### Admin Authentication

**Headers required:**
- `X-Admin-Key: <your-admin-key>` OR
- `Authorization: Bearer <your-admin-key>`

**Environment variables to set on backend:**
- `ADMIN_API_KEY=single-key` OR
- `ADMIN_API_KEYS=key1,key2,key3` (for rotation)

---

### Admin API Commands

#### List Pending Tags

```bash
curl -s "$API_URL/api/admin/tags/pending" \
  -H "X-Admin-Key: $ADMIN_API_KEY" | jq '.'
```

**Expected:** List of pending tag suggestions with ad info

#### Approve a Tag

```bash
TAG_ID="<uuid-from-pending-list>"
curl -X PATCH "$API_URL/api/admin/tags/$TAG_ID" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "approved"}'
```

**Expected:** `{"status": "updated", "new_status": "approved"}`

#### Reject a Tag

```bash
TAG_ID="<uuid-from-pending-list>"
curl -X PATCH "$API_URL/api/admin/tags/$TAG_ID" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "rejected", "reason": "Not relevant"}'
```

#### Mark Tag as Spam

```bash
curl -X PATCH "$API_URL/api/admin/tags/$TAG_ID" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "spam"}'
```

#### Verify Auth Enforcement

```bash
# Should return 401 without key
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/admin/tags/pending"
# Expected: 401

# Should return 403 with wrong key
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/admin/tags/pending" \
  -H "X-Admin-Key: wrong-key"
# Expected: 403
```

**STOP/GO:** If admin endpoints return 200 without valid key, STOP - auth is broken.

---

### Admin SQL Queries

#### Recently Imported Editorial

```sql
SELECT
  e.brand_slug,
  e.slug,
  e.headline,
  e.status,
  e.wix_item_id,
  e.created_at
FROM ad_editorial e
ORDER BY e.created_at DESC
LIMIT 20;
```

#### Ads Missing Editorial (Need Import or Manual)

```sql
SELECT * FROM v_ads_missing_editorial LIMIT 50;
```

#### Redirect Coverage

```sql
SELECT * FROM v_legacy_url_coverage;
```

#### Import Statistics Dashboard

```sql
SELECT * FROM v_import_stats;
```

#### Duplicate Slugs (URL Conflicts)

```sql
SELECT * FROM v_editorial_dup_slugs;
```

#### Orphan Editorial Records

```sql
SELECT * FROM v_editorial_orphans;
```

#### Feedback Aggregates Integrity

```sql
-- Check if aggregate counts match raw data
SELECT
    f.ad_id,
    f.like_count as agg_likes,
    (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_liked = true) as actual_likes,
    f.save_count as agg_saves,
    (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_saved = true) as actual_saves,
    f.distinct_reason_sessions as agg_reason_sessions,
    (SELECT COUNT(DISTINCT session_id) FROM ad_like_reasons WHERE ad_id = f.ad_id) as actual_reason_sessions,
    CASE
        WHEN f.like_count = (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_liked = true)
         AND f.save_count = (SELECT COUNT(*) FROM ad_user_reactions WHERE ad_id = f.ad_id AND is_saved = true)
         AND f.distinct_reason_sessions = (SELECT COUNT(DISTINCT session_id) FROM ad_like_reasons WHERE ad_id = f.ad_id)
        THEN 'OK'
        ELSE 'DRIFT'
    END as integrity_status
FROM ad_feedback_agg f
LIMIT 30;
```

**STOP/GO:** If any row shows `DRIFT`, investigate trigger issues.

#### 404 Tracking (After Implementation)

```sql
-- Top missed legacy URLs (once implemented)
SELECT * FROM v_top_404s;
```

---

## 4. Stop/Go Gates Summary

| Stage | Gate | Action if Fail |
|-------|------|----------------|
| Migrations | Any ERROR in psql output | STOP - fix SQL syntax |
| Verify Scripts | Any FAIL or MISSING | STOP - migration incomplete |
| Dry-Run Import | conflicts.csv > 0 | STOP - resolve duplicates |
| Dry-Run Import | match_rate < 80% | STOP - improve matching |
| Apply Import | inserted_count == 0 | STOP - check permissions |
| SEO Gating | Published ad returns 404 | STOP - query/index issue |
| SEO Gating | Unpublished ad returns 200 | STOP - gating not enforced |
| Feedback Endpoint | Missing score fields | STOP - schema incomplete |
| Rate Limiting | 200 after 20 reasons | STOP - rate limit broken |
| Reason Threshold | reason_counts visible < 10 sessions | STOP - threshold not enforced |
| Confidence Weight | Includes views in calculation | STOP - formula wrong |
| Admin Auth | 200 without valid key | STOP - auth broken |
| Integrity Check | Any DRIFT status | STOP - trigger issue |

---

## 5. Production Deployment

After all staging gates pass:

1. **Backup production**
   ```bash
   pg_dump "$PROD_SUPABASE_DB_URL" > backup_prod_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Apply migrations** (same order as staging)

3. **Run verify scripts** (same as staging)

4. **Import editorial data** (with reviewed Excel)

5. **Deploy backend** with `ADMIN_API_KEY` set

6. **Run smoke tests** against production API

7. **Deploy frontend**

8. **Monitor** for 24-48 hours

---

## 6. Known TODOs (Not Blocking Go-Live)

| Item | Status | Priority |
|------|--------|----------|
| `/api/resolve-legacy` endpoint | Not implemented | P2 |
| Next.js redirect middleware | Not implemented | P2 |
| Dynamic sitemap for editorial | Not implemented | P2 |
| `legacy_url_misses` 404 tracking | Schema only, no API | P3 |
| `/api/editorial/sitemap` endpoint | Not implemented | P2 |

These are documented in GO_LIVE_PACK.md Section 3 and can be added post-launch.

---

**Document version:** 1.0.0
**Last updated:** 2025-12-04
**Author:** Claude Code (Release Captain)
