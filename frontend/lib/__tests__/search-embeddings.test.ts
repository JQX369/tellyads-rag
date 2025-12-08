/**
 * Tests for search embedding queries
 *
 * Verifies:
 * 1. Search query uses embedding_items table (not ads.embedding)
 * 2. Similar ads query uses embedding_items table
 * 3. Correct item_type filter ('ad_summary')
 * 4. Correct distance operator (<=> for cosine)
 */

import { readFileSync } from 'fs';
import { join } from 'path';

// Read route files to inspect SQL queries
const searchRoutePath = join(__dirname, '../../app/api/search/route.ts');
const similarRoutePath = join(__dirname, '../../app/api/ads/[external_id]/similar/route.ts');

describe('Search route SQL query', () => {
  let searchRouteContent: string;

  beforeAll(() => {
    searchRouteContent = readFileSync(searchRoutePath, 'utf-8');
  });

  it('should query embedding_items table, not ads.embedding', () => {
    // Should NOT contain ads.embedding
    expect(searchRouteContent).not.toMatch(/FROM ads.*WHERE.*a\.embedding/s);
    expect(searchRouteContent).not.toMatch(/a\.embedding\s*<=>/);

    // Should contain embedding_items join
    expect(searchRouteContent).toMatch(/FROM embedding_items ei/);
    expect(searchRouteContent).toMatch(/JOIN ads a ON a\.id = ei\.ad_id/);
  });

  it('should filter by item_type ad_summary', () => {
    expect(searchRouteContent).toMatch(/item_type\s*=\s*['"]ad_summary['"]/);
  });

  it('should use cosine distance operator (<=>) on ei.embedding', () => {
    expect(searchRouteContent).toMatch(/ei\.embedding\s*<=>/);
  });

  it('should order by ei.embedding distance', () => {
    expect(searchRouteContent).toMatch(/ORDER BY ei\.embedding\s*<=>/);
  });
});

describe('Similar ads route SQL query', () => {
  let similarRouteContent: string;

  beforeAll(() => {
    similarRouteContent = readFileSync(similarRoutePath, 'utf-8');
  });

  it('should get source embedding from embedding_items, not ads', () => {
    // Should NOT select embedding directly from ads
    expect(similarRouteContent).not.toMatch(/SELECT.*embedding FROM ads/i);

    // Should join to embedding_items to get source embedding
    expect(similarRouteContent).toMatch(/embedding_items ei ON ei\.ad_id = a\.id/);
    expect(similarRouteContent).toMatch(/item_type\s*=\s*['"]ad_summary['"]/);
  });

  it('should query embedding_items for similar ads', () => {
    // Should use embedding_items for similarity search
    expect(similarRouteContent).toMatch(/FROM embedding_items ei/);
    expect(similarRouteContent).toMatch(/ei\.embedding\s*<=>/);
  });

  it('should filter by item_type ad_summary for similar ads', () => {
    // The WHERE clause should filter to ad_summary
    expect(similarRouteContent).toMatch(/WHERE\s+ei\.item_type\s*=\s*['"]ad_summary['"]/);
  });

  it('should exclude source ad from results', () => {
    expect(similarRouteContent).toMatch(/a\.id\s*!=\s*\$2/);
  });
});

describe('Schema consistency', () => {
  it('should have migration for embedding_items indexes', () => {
    const migrationPath = join(__dirname, '../../../tvads_rag/migrations/005_embedding_search_fix.sql');
    const migrationContent = readFileSync(migrationPath, 'utf-8');

    // Should create unique index for ad_summary
    expect(migrationContent).toMatch(/CREATE UNIQUE INDEX.*ad_summary/i);

    // Should create HNSW index
    expect(migrationContent).toMatch(/USING hnsw.*embedding.*vector_cosine_ops/i);

    // Should have search function
    expect(migrationContent).toMatch(/CREATE OR REPLACE FUNCTION search_ads_by_embedding/);
  });
});
