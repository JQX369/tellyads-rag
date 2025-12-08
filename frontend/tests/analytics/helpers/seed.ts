/**
 * Analytics Test Seed Helper
 *
 * Creates deterministic test data for analytics tests.
 * Used to verify rollup correctness and API responses.
 */

export interface SeedEvent {
  event: string;
  path: string;
  session_id: string;
  props: Record<string, unknown>;
  ua_hash: string;
  event_date?: string;
}

/**
 * Generate a mini-dataset of 20 analytics events for testing.
 * Returns expected counts for verification.
 */
export function generateSeedData(testDate: string = '2024-01-15'): {
  events: SeedEvent[];
  expectedCounts: Record<string, number>;
} {
  const sessionId = 'test-session-seed-001';
  const uaHash = 'test-ua-hash-abc123';

  const events: SeedEvent[] = [];

  // 5 page.view events
  for (let i = 0; i < 5; i++) {
    events.push({
      event: 'page.view',
      path: `/test-page-${i}`,
      session_id: sessionId,
      props: { page_title: `Test Page ${i}` },
      ua_hash: uaHash,
      event_date: testDate,
    });
  }

  // 3 search.performed events (1 will be zero-results)
  for (let i = 0; i < 3; i++) {
    const isZeroResults = i === 2;
    events.push({
      event: 'search.performed',
      path: '/search',
      session_id: sessionId,
      props: {
        query: isZeroResults ? 'nonexistent query' : `test query ${i}`,
        results_count: isZeroResults ? 0 : 10 + i,
        latency_ms: 50 + i * 10,
      },
      ua_hash: uaHash,
      event_date: testDate,
    });
  }

  // 1 search.zero_results event (explicit)
  events.push({
    event: 'search.zero_results',
    path: '/search',
    session_id: sessionId,
    props: { query: 'nothing found here' },
    ua_hash: uaHash,
    event_date: testDate,
  });

  // 2 search.result_click events
  for (let i = 0; i < 2; i++) {
    events.push({
      event: 'search.result_click',
      path: '/search',
      session_id: sessionId,
      props: {
        query: `test query ${i}`,
        ad_id: `ad-${i}`,
        position: i + 1,
      },
      ua_hash: uaHash,
      event_date: testDate,
    });
  }

  // 5 advert.view events
  for (let i = 0; i < 5; i++) {
    events.push({
      event: 'advert.view',
      path: `/ads/test-ad-${i}`,
      session_id: sessionId,
      props: {
        ad_id: `test-ad-${i}`,
        brand: 'TestBrand',
        source: 'seed',
      },
      ua_hash: uaHash,
      event_date: testDate,
    });
  }

  // 2 advert.share events
  for (let i = 0; i < 2; i++) {
    events.push({
      event: 'advert.share',
      path: `/ads/test-ad-${i}`,
      session_id: sessionId,
      props: {
        ad_id: `test-ad-${i}`,
        platform: i === 0 ? 'twitter' : 'facebook',
      },
      ua_hash: uaHash,
      event_date: testDate,
    });
  }

  return {
    events,
    expectedCounts: {
      'page.view': 5,
      'search.performed': 3,
      'search.zero_results': 1,
      'search.result_click': 2,
      'advert.view': 5,
      'advert.share': 2,
      total: 18,
    },
  };
}

/**
 * Generate expected rollup results from seed data.
 */
export function getExpectedRollupResults(seedData: ReturnType<typeof generateSeedData>) {
  const { expectedCounts } = seedData;

  return {
    daily_events: [
      { event: 'page.view', count: expectedCounts['page.view'], unique_sessions: 1 },
      { event: 'search.performed', count: expectedCounts['search.performed'], unique_sessions: 1 },
      { event: 'search.zero_results', count: expectedCounts['search.zero_results'], unique_sessions: 1 },
      { event: 'search.result_click', count: expectedCounts['search.result_click'], unique_sessions: 1 },
      { event: 'advert.view', count: expectedCounts['advert.view'], unique_sessions: 1 },
      { event: 'advert.share', count: expectedCounts['advert.share'], unique_sessions: 1 },
    ],
    daily_search: [
      { query: 'test query 0', search_count: 1, click_count: 1, zero_results: false },
      { query: 'test query 1', search_count: 1, click_count: 1, zero_results: false },
      { query: 'nonexistent query', search_count: 1, click_count: 0, zero_results: true },
    ],
    daily_funnel: {
      sessions: 1,
      searches: 3,
      ad_views: 5,
      engagements: 2, // shares
      search_rate: 100, // 1 session that searched out of 1 total
      view_rate: 100, // 1 session that viewed ad out of 1 total
      engagement_rate: 100, // 1 session that engaged out of 1 total
    },
  };
}

/**
 * Valid event types for testing
 */
export const VALID_EVENTS = [
  'page.view',
  'page.scroll_depth',
  'page.exit',
  'search.performed',
  'search.result_click',
  'search.zero_results',
  'search.filter_applied',
  'advert.view',
  'advert.play',
  'advert.pause',
  'advert.complete',
  'advert.like',
  'advert.save',
  'advert.share',
  'advert.similar_click',
  'browse.era_click',
  'browse.brand_click',
  'browse.random_click',
  'outbound.click',
  'error.api',
  'error.client',
  'seo.404',
  'seo.legacy_redirect',
];

/**
 * Generate a valid capture payload for testing
 */
export function createValidPayload(overrides: Partial<{
  event: string;
  path: string;
  session_id: string;
  ua_hash: string;
  props: Record<string, unknown>;
}> = {}) {
  return {
    event: 'page.view',
    path: '/test',
    session_id: 'test-session-123',
    ua_hash: 'test-ua-abc',
    props: {},
    ...overrides,
  };
}
