/**
 * Catalog Enqueue Ingestion API Route
 *
 * POST /api/admin/catalog/enqueue
 *
 * Admin-only endpoint that creates ingestion jobs for selected catalog entries.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll, queryOne } from '@/lib/db';

export const runtime = 'nodejs';

interface EnqueueRequest {
  catalog_ids?: string[];
  filter?: 'unmapped' | 'not_ingested';
  limit?: number;
}

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const body: EnqueueRequest = await request.json();
    const { catalog_ids, filter, limit = 100 } = body;

    // Get catalog entries to enqueue
    let entries: Array<{ id: string; external_id: string; s3_key?: string; video_url?: string }>;

    if (catalog_ids && catalog_ids.length > 0) {
      // Specific IDs - allow any with valid video source
      entries = await queryAll(
        `SELECT id, external_id, s3_key, video_url
         FROM ad_catalog
         WHERE id = ANY($1::uuid[])
           AND is_ingested = false
           AND (s3_key IS NOT NULL OR video_url IS NOT NULL)`,
        [catalog_ids]
      );
    } else if (filter === 'not_ingested') {
      // All not ingested with valid video source
      entries = await queryAll(
        `SELECT id, external_id, s3_key, video_url
         FROM ad_catalog
         WHERE is_ingested = false
           AND (s3_key IS NOT NULL OR video_url IS NOT NULL)
         ORDER BY created_at DESC
         LIMIT $1`,
        [Math.min(limit, 500)]
      );
    } else {
      return NextResponse.json(
        { error: 'Must provide catalog_ids or filter=not_ingested' },
        { status: 400 }
      );
    }

    if (entries.length === 0) {
      return NextResponse.json({
        success: true,
        enqueued: 0,
        message: 'No eligible catalog entries found',
      });
    }

    // Enqueue jobs for each entry
    const results = {
      enqueued: 0,
      skipped: 0,
      errors: [] as string[],
    };

    for (const entry of entries) {
      try {
        const sourceType = entry.s3_key ? 's3' : 'url';
        const jobInput = {
          source_type: sourceType,
          s3_key: entry.s3_key,
          url: entry.video_url,
          external_id: entry.external_id,
          metadata: {
            catalog_id: entry.id,
            from_catalog: true,
          },
        };

        const idempotencyKey = `catalog:${entry.external_id}`;

        const result = await queryOne<{ job_id: string; already_existed: boolean }>(
          'SELECT * FROM enqueue_job($1::jsonb, $2, $3, $4)',
          [JSON.stringify(jobInput), idempotencyKey, 0, 5]
        );

        if (result?.already_existed) {
          results.skipped++;
        } else {
          results.enqueued++;
        }
      } catch (error) {
        results.errors.push(`${entry.external_id}: ${error}`);
      }
    }

    return NextResponse.json({
      success: true,
      ...results,
      total_processed: entries.length,
    });
  } catch (error) {
    console.error('Error enqueueing catalog entries:', error);
    return NextResponse.json(
      { error: 'Failed to enqueue catalog entries' },
      { status: 500 }
    );
  }
}
