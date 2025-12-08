/**
 * Catalog Imports API Route
 *
 * GET /api/admin/catalog/imports - List import jobs
 *
 * Admin-only endpoint for viewing catalog import status.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(parseInt(searchParams.get('limit') || '20', 10), 100);
    const offset = parseInt(searchParams.get('offset') || '0', 10);

    const imports = await queryAll(
      `SELECT
        i.id, i.created_at, i.updated_at, i.status,
        i.source_file_path, i.original_filename,
        i.rows_total, i.rows_ok, i.rows_failed,
        i.last_error, i.job_id, i.initiated_by,
        j.status as job_status, j.stage as job_stage, j.progress as job_progress
      FROM ad_catalog_imports i
      LEFT JOIN ingestion_jobs j ON j.id = i.job_id
      ORDER BY i.created_at DESC
      LIMIT $1 OFFSET $2`,
      [limit, offset]
    );

    return NextResponse.json({ imports });
  } catch (error) {
    console.error('Error fetching catalog imports:', error);
    return NextResponse.json(
      { error: 'Failed to fetch imports' },
      { status: 500 }
    );
  }
}
