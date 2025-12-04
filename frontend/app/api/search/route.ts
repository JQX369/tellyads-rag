/**
 * Search API Route Handler
 *
 * POST /api/search
 *
 * Performs semantic search using embeddings.
 * Returns matching ads with relevance scores.
 *
 * Rate limited to prevent OpenAI cost explosion.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';
import { checkRateLimit, getRateLimitKey } from '@/lib/rate-limit';
import OpenAI from 'openai';

export const runtime = 'nodejs';

// Rate limit: 20 requests per minute per session/IP
const RATE_LIMIT_CONFIG = {
  windowMs: 60 * 1000, // 1 minute
  max: 20,
};

// Query constraints
const MIN_QUERY_LENGTH = 2;
const MAX_QUERY_LENGTH = 300;

// Initialize OpenAI client for embeddings
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

interface SearchRequest {
  query: string;
  top_k?: number;
  session_id?: string;
  filters?: {
    brand_name?: string;
    year?: number;
    product_category?: string;
    has_supers?: boolean;
  };
}

export async function POST(request: NextRequest) {
  try {
    const body: SearchRequest = await request.json();
    const { query, top_k = 20, session_id, filters = {} } = body;

    // Validate query presence
    if (!query || typeof query !== 'string') {
      return NextResponse.json(
        { error: 'query is required and must be a string' },
        { status: 400 }
      );
    }

    const trimmedQuery = query.trim();

    // Validate query length
    if (trimmedQuery.length === 0) {
      return NextResponse.json(
        { error: 'query cannot be empty' },
        { status: 400 }
      );
    }

    if (trimmedQuery.length < MIN_QUERY_LENGTH) {
      return NextResponse.json(
        { error: `query must be at least ${MIN_QUERY_LENGTH} characters` },
        { status: 400 }
      );
    }

    if (trimmedQuery.length > MAX_QUERY_LENGTH) {
      return NextResponse.json(
        { error: `query must not exceed ${MAX_QUERY_LENGTH} characters` },
        { status: 400 }
      );
    }

    // Rate limiting
    const rateLimitKey = getRateLimitKey(request, session_id);
    const rateLimitResult = checkRateLimit(rateLimitKey, RATE_LIMIT_CONFIG);

    if (!rateLimitResult.success) {
      const retryAfterSeconds = Math.ceil((rateLimitResult.resetAt - Date.now()) / 1000);
      return NextResponse.json(
        {
          error: 'Too many requests. Please try again later.',
          retry_after: retryAfterSeconds,
        },
        {
          status: 429,
          headers: {
            'Retry-After': retryAfterSeconds.toString(),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': rateLimitResult.resetAt.toString(),
          },
        }
      );
    }

    // Generate embedding for query
    const embeddingResponse = await openai.embeddings.create({
      model: 'text-embedding-3-large',
      input: trimmedQuery,
      dimensions: 1536,
    });

    const queryEmbedding = embeddingResponse.data[0].embedding;

    // Build filter conditions
    const conditions: string[] = [];
    const params: any[] = [`[${queryEmbedding.join(',')}]`];
    let paramIndex = 2;

    if (filters.brand_name) {
      conditions.push(`a.brand_name ILIKE $${paramIndex}`);
      params.push(`%${filters.brand_name}%`);
      paramIndex++;
    }

    if (filters.year) {
      conditions.push(`a.year = $${paramIndex}`);
      params.push(filters.year);
      paramIndex++;
    }

    if (filters.product_category) {
      conditions.push(`a.product_category ILIKE $${paramIndex}`);
      params.push(`%${filters.product_category}%`);
      paramIndex++;
    }

    if (filters.has_supers !== undefined) {
      conditions.push(`a.has_supers = $${paramIndex}`);
      params.push(filters.has_supers);
      paramIndex++;
    }

    params.push(top_k);

    const whereClause = conditions.length > 0
      ? `AND ${conditions.join(' AND ')}`
      : '';

    // Semantic search with pgvector
    const results = await queryAll(
      `
      SELECT
        a.id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.format_type,
        a.year,
        a.duration_seconds,
        a.thumbnail_url,
        a.video_url,
        a.has_supers,
        a.has_price_claims,
        a.impact_scores,
        e.brand_slug,
        e.slug,
        e.headline,
        e.curated_tags,
        e.is_featured,
        1 - (a.embedding <=> $1::vector) as similarity
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      WHERE a.embedding IS NOT NULL
        ${whereClause}
      ORDER BY a.embedding <=> $1::vector
      LIMIT $${paramIndex}
      `,
      params
    );

    // Format response
    const formattedResults = results.map((row) => ({
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      brand_slug: row.brand_slug,
      slug: row.slug,
      headline: row.headline || row.one_line_summary,
      one_line_summary: row.one_line_summary,
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      thumbnail_url: row.thumbnail_url,
      video_url: row.video_url,
      has_supers: row.has_supers,
      has_price_claims: row.has_price_claims,
      impact_scores: row.impact_scores,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      similarity: row.similarity,
      // Generate canonical URL if editorial exists
      canonical_url: row.brand_slug && row.slug
        ? `/advert/${row.brand_slug}/${row.slug}`
        : `/ads/${row.external_id}`,
    }));

    return NextResponse.json(
      {
        query: trimmedQuery,
        total: formattedResults.length,
        results: formattedResults,
      },
      {
        headers: {
          'X-RateLimit-Remaining': rateLimitResult.remaining.toString(),
          'X-RateLimit-Reset': rateLimitResult.resetAt.toString(),
        },
      }
    );
  } catch (error) {
    console.error('Search error:', error);
    return NextResponse.json(
      { error: 'Search failed' },
      { status: 500 }
    );
  }
}
