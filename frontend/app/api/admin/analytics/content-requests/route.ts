/**
 * Admin Content Requests API
 *
 * GET /api/admin/analytics/content-requests
 * POST /api/admin/analytics/content-requests
 *
 * Manages content requests surfaced from zero-result searches.
 * Requires admin authentication.
 */

import { NextRequest, NextResponse } from 'next/server';
import { query, queryAll, queryOne } from '@/lib/db';
import { verifyAdmin } from '@/lib/admin-auth';

export const runtime = 'nodejs';

interface ContentRequest {
  id: string;
  query: string;
  status: 'new' | 'queued' | 'in_progress' | 'done' | 'rejected';
  priority: number;
  search_count: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * GET - List content requests
 * Query params:
 *   - status: Filter by status (default: all)
 *   - limit: Max results (default: 50)
 */
export async function GET(request: NextRequest) {
  const authResult = await verifyAdmin(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');
    const limit = Math.min(parseInt(searchParams.get('limit') || '50', 10), 200);

    // Check if table exists
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'content_requests'
      ) as exists`
    );

    if (!tableExists?.exists) {
      return NextResponse.json({
        requests: [],
        total: 0,
        message: 'Content requests table not found. Run 007_analytics_production.sql migration.',
      });
    }

    let sql = `
      SELECT
        id,
        query,
        status,
        priority,
        search_count,
        notes,
        created_at,
        updated_at
      FROM content_requests
    `;
    const params: (string | number)[] = [];

    if (status && ['new', 'queued', 'in_progress', 'done', 'rejected'].includes(status)) {
      sql += ` WHERE status = $1`;
      params.push(status);
    }

    sql += ` ORDER BY priority DESC, search_count DESC, created_at DESC LIMIT $${params.length + 1}`;
    params.push(limit);

    const requests = await queryAll(sql, params);

    // Get total counts by status
    const counts = await queryOne(`
      SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'new') as new_count,
        COUNT(*) FILTER (WHERE status = 'queued') as queued_count,
        COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
        COUNT(*) FILTER (WHERE status = 'done') as done_count,
        COUNT(*) FILTER (WHERE status = 'rejected') as rejected_count
      FROM content_requests
    `);

    return NextResponse.json({
      requests: requests.map(r => ({
        id: r.id,
        query: r.query,
        status: r.status,
        priority: r.priority,
        search_count: Number(r.search_count) || 0,
        notes: r.notes,
        created_at: r.created_at,
        updated_at: r.updated_at,
      })),
      counts: {
        total: Number(counts?.total) || 0,
        new: Number(counts?.new_count) || 0,
        queued: Number(counts?.queued_count) || 0,
        in_progress: Number(counts?.in_progress_count) || 0,
        done: Number(counts?.done_count) || 0,
        rejected: Number(counts?.rejected_count) || 0,
      },
    });
  } catch (error) {
    console.error('Content requests error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch content requests' },
      { status: 500 }
    );
  }
}

/**
 * POST - Create or update content request
 * Body:
 *   - query: The search query (required for create)
 *   - id: UUID of existing request (required for update)
 *   - status: New status
 *   - priority: Priority level (0-10)
 *   - notes: Admin notes
 */
export async function POST(request: NextRequest) {
  const authResult = await verifyAdmin(request);
  if (!authResult.success) {
    return NextResponse.json({ error: authResult.error }, { status: 401 });
  }

  try {
    const body = await request.json();

    // Check if table exists
    const tableExists = await queryOne(
      `SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'content_requests'
      ) as exists`
    );

    if (!tableExists?.exists) {
      return NextResponse.json(
        { error: 'Content requests table not found' },
        { status: 500 }
      );
    }

    // Update existing request
    if (body.id) {
      const updates: string[] = [];
      const params: (string | number)[] = [];
      let paramIndex = 1;

      if (body.status) {
        if (!['new', 'queued', 'in_progress', 'done', 'rejected'].includes(body.status)) {
          return NextResponse.json({ error: 'Invalid status' }, { status: 400 });
        }
        updates.push(`status = $${paramIndex++}`);
        params.push(body.status);
      }

      if (body.priority !== undefined) {
        const priority = Math.min(Math.max(parseInt(body.priority, 10), 0), 10);
        updates.push(`priority = $${paramIndex++}`);
        params.push(priority);
      }

      if (body.notes !== undefined) {
        updates.push(`notes = $${paramIndex++}`);
        params.push(body.notes?.slice(0, 1000) || null);
      }

      if (updates.length === 0) {
        return NextResponse.json({ error: 'No updates provided' }, { status: 400 });
      }

      updates.push('updated_at = NOW()');
      params.push(body.id);

      const result = await queryOne(
        `UPDATE content_requests
         SET ${updates.join(', ')}
         WHERE id = $${paramIndex}
         RETURNING *`,
        params
      );

      if (!result) {
        return NextResponse.json({ error: 'Request not found' }, { status: 404 });
      }

      return NextResponse.json({ request: result });
    }

    // Create new request
    if (!body.query || typeof body.query !== 'string') {
      return NextResponse.json({ error: 'Query is required' }, { status: 400 });
    }

    const query_text = body.query.slice(0, 500).trim().toLowerCase();

    // Check if already exists
    const existing = await queryOne(
      `SELECT id, search_count FROM content_requests WHERE query = $1`,
      [query_text]
    );

    if (existing) {
      // Increment search count instead of creating duplicate
      const updated = await queryOne(
        `UPDATE content_requests
         SET search_count = search_count + 1, updated_at = NOW()
         WHERE id = $1
         RETURNING *`,
        [existing.id]
      );
      return NextResponse.json({ request: updated, action: 'incremented' });
    }

    // Create new
    const newRequest = await queryOne(
      `INSERT INTO content_requests (query, status, priority, search_count)
       VALUES ($1, 'new', $2, 1)
       RETURNING *`,
      [query_text, body.priority || 0]
    );

    return NextResponse.json({ request: newRequest, action: 'created' }, { status: 201 });
  } catch (error) {
    console.error('Content request create/update error:', error);
    return NextResponse.json(
      { error: 'Failed to process content request' },
      { status: 500 }
    );
  }
}
