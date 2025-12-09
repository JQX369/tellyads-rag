/**
 * Catalog CSV Upload API Route
 *
 * POST /api/admin/catalog/upload
 *
 * Admin-only endpoint that:
 * 1. Accepts CSV file upload (multipart)
 * 2. Stores file to S3
 * 3. Creates catalog_imports record
 * 4. Enqueues catalog_import job for worker processing
 *
 * The actual CSV parsing happens in the Railway worker, NOT in Vercel runtime.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { query, queryOne } from '@/lib/db';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { randomUUID } from 'crypto';

export const runtime = 'nodejs';

// Max file size: 50MB (for CSV files, should handle 20k+ rows)
// Note: App Router handles formData() natively, no config needed

// Initialize S3 client
function getS3Client() {
  return new S3Client({
    region: process.env.S3_REGION || process.env.AWS_REGION || 'us-east-1',
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID || '',
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY || '',
    },
    ...(process.env.S3_ENDPOINT_URL && { endpoint: process.env.S3_ENDPOINT_URL }),
  });
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
    // Parse multipart form data
    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json(
        { error: 'No file provided' },
        { status: 400 }
      );
    }

    // Validate file type
    const filename = file.name.toLowerCase();
    if (!filename.endsWith('.csv')) {
      return NextResponse.json(
        { error: 'Only CSV files are accepted' },
        { status: 400 }
      );
    }

    // Check file size (50MB limit)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      return NextResponse.json(
        { error: `File too large. Maximum size is ${maxSize / (1024 * 1024)}MB` },
        { status: 400 }
      );
    }

    // Generate unique S3 key
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const importId = randomUUID();
    const s3Key = `catalog-imports/${timestamp}_${importId}.csv`;

    // Read file content
    const buffer = Buffer.from(await file.arrayBuffer());

    // Upload to S3
    const bucket = process.env.S3_BUCKET_NAME || process.env.CATALOG_BUCKET_NAME;
    if (!bucket) {
      return NextResponse.json(
        { error: 'S3 bucket not configured' },
        { status: 500 }
      );
    }

    const s3Client = getS3Client();
    await s3Client.send(new PutObjectCommand({
      Bucket: bucket,
      Key: s3Key,
      Body: buffer,
      ContentType: 'text/csv',
      Metadata: {
        'original-filename': file.name,
        'import-id': importId,
      },
    }));

    // Create catalog_imports record
    const importResult = await queryOne<{ id: string }>(
      `INSERT INTO ad_catalog_imports (
        id, source_file_path, original_filename, initiated_by, status
      ) VALUES ($1, $2, $3, $4, 'UPLOADED')
      RETURNING id`,
      [importId, s3Key, file.name, 'admin']
    );

    if (!importResult) {
      return NextResponse.json(
        { error: 'Failed to create import record' },
        { status: 500 }
      );
    }

    // Enqueue catalog_import job
    const jobInput = {
      job_type: 'catalog_import',
      import_id: importId,
      file_path: s3Key,
      bucket: bucket,
      original_filename: file.name,
    };

    const idempotencyKey = `catalog_import:${importId}`;

    const jobResult = await queryOne<{ job_id: string; status: string; already_existed: boolean }>(
      'SELECT * FROM enqueue_job($1::jsonb, $2, $3, $4)',
      [JSON.stringify(jobInput), idempotencyKey, 10, 3] // Priority 10 (higher), max 3 attempts
    );

    if (!jobResult) {
      return NextResponse.json(
        { error: 'Failed to enqueue import job' },
        { status: 500 }
      );
    }

    // Update import record with job_id
    await query(
      'UPDATE ad_catalog_imports SET job_id = $1 WHERE id = $2',
      [jobResult.job_id, importId]
    );

    return NextResponse.json({
      success: true,
      import_id: importId,
      job_id: jobResult.job_id,
      s3_key: s3Key,
      filename: file.name,
      size_bytes: file.size,
      message: 'File uploaded successfully. Processing will begin shortly.',
    });
  } catch (error) {
    console.error('Catalog upload error:', error);
    return NextResponse.json(
      { error: 'Failed to upload catalog file' },
      { status: 500 }
    );
  }
}
