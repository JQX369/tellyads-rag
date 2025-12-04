/**
 * Status API Route Handler
 *
 * GET /api/status
 *
 * Health check endpoint.
 */

import { NextRequest, NextResponse } from 'next/server';
import { queryOne } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  try {
    // Test database connection
    const result = await queryOne('SELECT 1 as ok');

    return NextResponse.json({
      status: 'ok',
      database: result?.ok === 1 ? 'connected' : 'error',
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
    });
  } catch (error) {
    console.error('Health check failed:', error);
    return NextResponse.json({
      status: 'error',
      database: 'disconnected',
      error: error instanceof Error ? error.message : 'Unknown error',
      timestamp: new Date().toISOString(),
    }, { status: 503 });
  }
}
