/**
 * Database connection utility for Next.js Route Handlers
 *
 * Uses pg (node-postgres) for direct Postgres/Supabase connection.
 * This replaces the FastAPI db_backend for serverless deployment.
 */

import { Pool, PoolClient, QueryResult, QueryResultRow } from 'pg';

// Connection pool - reused across requests in serverless
let pool: Pool | null = null;

function getPool(): Pool {
  if (!pool) {
    const connectionString = process.env.SUPABASE_DB_URL || process.env.DATABASE_URL;

    if (!connectionString) {
      throw new Error('Database connection string not configured. Set SUPABASE_DB_URL or DATABASE_URL.');
    }

    pool = new Pool({
      connectionString,
      max: 10, // Max connections in pool
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 10000,
      ssl: connectionString.includes('supabase') ? { rejectUnauthorized: false } : undefined,
    });

    // Handle pool errors
    pool.on('error', (err) => {
      console.error('Unexpected database pool error:', err);
    });
  }

  return pool;
}

/**
 * Execute a query and return results
 */
export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: any[]
): Promise<QueryResult<T>> {
  const pool = getPool();
  const start = Date.now();

  try {
    const result = await pool.query<T>(text, params);
    const duration = Date.now() - start;

    if (process.env.NODE_ENV === 'development' && duration > 100) {
      console.log(`Slow query (${duration}ms):`, text.slice(0, 100));
    }

    return result;
  } catch (error) {
    console.error('Database query error:', error);
    throw error;
  }
}

/**
 * Get a client from the pool for transactions
 */
export async function getClient(): Promise<PoolClient> {
  const pool = getPool();
  return pool.connect();
}

/**
 * Execute a transaction with automatic rollback on error
 */
export async function transaction<T>(
  callback: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await getClient();

  try {
    await client.query('BEGIN');
    const result = await callback(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

/**
 * Helper to get a single row or null
 */
export async function queryOne<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: any[]
): Promise<T | null> {
  const result = await query<T>(text, params);
  return result.rows[0] || null;
}

/**
 * Helper to get all rows
 */
export async function queryAll<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: any[]
): Promise<T[]> {
  const result = await query<T>(text, params);
  return result.rows;
}

// Publish gating condition for editorial content
export const PUBLISH_GATE_CONDITION = `
  status = 'published'
  AND is_hidden = false
  AND (publish_date IS NULL OR publish_date <= NOW())
`;

// Common ad fields to select (avoids selecting huge JSONB columns)
export const AD_SELECT_FIELDS = `
  id, external_id, brand_name, brand_slug, product_name, product_category,
  one_line_summary, format_type, year, duration_seconds,
  s3_key, thumbnail_url, video_url,
  has_supers, has_price_claims,
  impact_scores, emotional_metrics, effectiveness,
  created_at, updated_at
`;

// Editorial fields
export const EDITORIAL_SELECT_FIELDS = `
  id, ad_id, brand_slug, slug, headline, editorial_summary,
  curated_tags, status, publish_date, is_hidden, is_featured,
  seo_title, seo_description, legacy_url,
  created_at, updated_at
`;
