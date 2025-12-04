/**
 * Admin Verification API Route Handler
 *
 * POST /api/admin/verify
 *
 * Verifies X-Admin-Key header using timing-safe comparison.
 * Returns 200 if valid, 401 if invalid, 503 if not configured.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey, isAdminConfigured } from '@/lib/admin-auth';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');

  // Check if admin is configured at all
  if (!isAdminConfigured()) {
    return NextResponse.json(
      { error: 'Admin authentication not configured' },
      { status: 503 }
    );
  }

  const result = verifyAdminKey(adminKey);

  if (!result.verified) {
    return NextResponse.json(
      { error: result.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  return NextResponse.json({ verified: true });
}

// Reject other methods
export async function GET() {
  return NextResponse.json(
    { error: 'Method not allowed' },
    { status: 405 }
  );
}
