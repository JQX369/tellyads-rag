# PR: Fix Search Embeddings Source of Truth

## Summary

**Problem**: Search and similar ads APIs were querying `ads.embedding` which **does not exist** in the schema. This caused both features to fail silently.

**Root cause**: The schema stores embeddings in `embedding_items` table with `item_type='ad_summary'` for ad-level embeddings, but the API routes were incorrectly written to query a non-existent `ads.embedding` column.

**Fix**: Updated search and similar APIs to query `embedding_items` table with proper joins and filters.

## Changes

### Files Modified

| File | Change |
|------|--------|
| `frontend/app/api/search/route.ts` | Query `embedding_items ei` instead of `ads.embedding` |
| `frontend/app/api/ads/[external_id]/similar/route.ts` | Query `embedding_items ei` instead of `ads.embedding` |
| `tvads_rag/migrations/005_embedding_search_fix.sql` | Add unique constraint, HNSW index, helper functions |
| `frontend/lib/__tests__/search-embeddings.test.ts` | Tests verifying correct table/column usage |

### No Changes Needed

| Component | Reason |
|-----------|--------|
| `tvads_rag/tvads_rag/pipeline/stages/embeddings.py` | Already writes to `embedding_items` with `item_type='ad_summary'` |
| `tvads_rag/schema.sql` | `embedding_items` table already has correct structure |

## Design Decision

**Canonical source**: `embedding_items` table with `item_type='ad_summary'`

Reasons:
1. Pipeline already writes here (no write path changes needed)
2. `match_embedding_items_hybrid` function already uses this table
3. Proper FK constraints exist (`ad_id REFERENCES ads(id)`)
4. Enables future per-item embedding search (claims, segments, etc.)

## Verification Steps

### 1. Run migration
```bash
psql "$SUPABASE_DB_URL" -f tvads_rag/migrations/005_embedding_search_fix.sql
```

### 2. Verify ad_summary embeddings exist
```sql
-- Check count matches ads
SELECT
    (SELECT COUNT(*) FROM ads) as total_ads,
    (SELECT COUNT(*) FROM embedding_items WHERE item_type = 'ad_summary') as ads_with_embedding;
```

### 3. Verify no duplicate ad_summary per ad
```sql
SELECT ad_id, COUNT(*) as cnt
FROM embedding_items
WHERE item_type = 'ad_summary'
GROUP BY ad_id
HAVING COUNT(*) > 1;
-- Should return 0 rows
```

### 4. Verify HNSW index is used
```sql
EXPLAIN ANALYZE
SELECT a.id, a.external_id, 1 - (ei.embedding <=> '[0.1,0.2,...]'::vector) as similarity
FROM embedding_items ei
JOIN ads a ON a.id = ei.ad_id
WHERE ei.item_type = 'ad_summary'
ORDER BY ei.embedding <=> '[0.1,0.2,...]'::vector
LIMIT 10;
-- Should show "Index Scan using idx_embedding_items_ad_summary_embedding"
```

### 5. Test search API
```bash
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "free trial offer"}'
```

### 6. Test similar ads API
```bash
curl http://localhost:3000/api/ads/TA12345/similar
```

### 7. Run automated tests
```bash
cd frontend && npm test -- --testPathPattern="search-embeddings"
```

## Test Results

```
PASS lib/__tests__/search-embeddings.test.ts
  Search route SQL query
    ✓ should query embedding_items table, not ads.embedding
    ✓ should filter by item_type ad_summary
    ✓ should use cosine distance operator (<=>) on ei.embedding
    ✓ should order by ei.embedding distance
  Similar ads route SQL query
    ✓ should get source embedding from embedding_items, not ads
    ✓ should query embedding_items for similar ads
    ✓ should filter by item_type ad_summary for similar ads
    ✓ should exclude source ad from results
  Schema consistency
    ✓ should have migration for embedding_items indexes

Test Suites: 1 passed, 1 total
Tests:       9 passed, 9 total
```

## Migration Notes

The migration is idempotent and safe to run multiple times:
- All `CREATE INDEX` statements use `IF NOT EXISTS`
- Functions use `CREATE OR REPLACE`

## Rollback

If issues occur, rollback by:
1. Reverting the route file changes in git
2. No schema rollback needed (indexes don't break existing functionality)

## Performance Impact

- **Positive**: HNSW index on `embedding_items.embedding` enables fast nearest-neighbor search
- **Positive**: Partial index for `item_type='ad_summary'` makes ad-level search more efficient
- **Neutral**: JOIN from `embedding_items` to `ads` is indexed via FK

## Related Issues

- Fixes audit issue #1: "Search route uses direct embedding column on ads table"
- Addresses P1 severity bug identified in AUDIT_REPORT.md
