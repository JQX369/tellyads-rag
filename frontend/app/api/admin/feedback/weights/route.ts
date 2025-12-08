/**
 * Feedback Weights Config API Route
 *
 * GET /api/admin/feedback/weights - Get all weight configs
 * PUT /api/admin/feedback/weights - Update weight config
 *
 * Admin-only endpoints for managing scoring weights.
 */

import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminKey } from '@/lib/admin-auth';
import { queryAll, queryOne, query } from '@/lib/db';

export const runtime = 'nodejs';

interface WeightConfig {
  id: string;
  config_key: string;
  name: string;
  description: string | null;
  is_active: boolean;
  weight_views: number;
  weight_unique_views: number;
  weight_completions: number;
  weight_likes: number;
  weight_saves: number;
  weight_shares: number;
  weight_rating: number;
  weight_review: number;
  decay_half_life_days: number;
  recency_boost_days: number;
  recency_boost_multiplier: number;
}

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
    const configs = await queryAll<WeightConfig>(
      `SELECT * FROM feedback_weight_configs ORDER BY is_active DESC, created_at DESC`
    );

    return NextResponse.json({ configs });
  } catch (error) {
    console.error('Error fetching weight configs:', error);
    return NextResponse.json(
      { error: 'Failed to fetch weight configs' },
      { status: 500 }
    );
  }
}

export async function PUT(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');
  const auth = verifyAdminKey(adminKey);

  if (!auth.verified) {
    return NextResponse.json(
      { error: auth.error || 'Unauthorized' },
      { status: 401 }
    );
  }

  try {
    const body: Partial<WeightConfig> & { id?: string; config_key?: string } = await request.json();

    // Validate weights are in valid range
    const weightFields = [
      'weight_views', 'weight_unique_views', 'weight_completions',
      'weight_likes', 'weight_saves', 'weight_shares',
      'weight_rating', 'weight_review'
    ] as const;

    for (const field of weightFields) {
      if (body[field] !== undefined) {
        const value = Number(body[field]);
        if (isNaN(value) || value < 0 || value > 10) {
          return NextResponse.json(
            { error: `${field} must be between 0 and 10` },
            { status: 400 }
          );
        }
      }
    }

    // Update the config
    const configKey = body.config_key || 'default';

    const result = await queryOne<WeightConfig>(
      `UPDATE feedback_weight_configs SET
        name = COALESCE($2, name),
        description = COALESCE($3, description),
        is_active = COALESCE($4, is_active),
        weight_views = COALESCE($5, weight_views),
        weight_unique_views = COALESCE($6, weight_unique_views),
        weight_completions = COALESCE($7, weight_completions),
        weight_likes = COALESCE($8, weight_likes),
        weight_saves = COALESCE($9, weight_saves),
        weight_shares = COALESCE($10, weight_shares),
        weight_rating = COALESCE($11, weight_rating),
        weight_review = COALESCE($12, weight_review),
        decay_half_life_days = COALESCE($13, decay_half_life_days),
        recency_boost_days = COALESCE($14, recency_boost_days),
        recency_boost_multiplier = COALESCE($15, recency_boost_multiplier),
        updated_at = now()
      WHERE config_key = $1
      RETURNING *`,
      [
        configKey,
        body.name,
        body.description,
        body.is_active,
        body.weight_views,
        body.weight_unique_views,
        body.weight_completions,
        body.weight_likes,
        body.weight_saves,
        body.weight_shares,
        body.weight_rating,
        body.weight_review,
        body.decay_half_life_days,
        body.recency_boost_days,
        body.recency_boost_multiplier,
      ]
    );

    if (!result) {
      return NextResponse.json(
        { error: 'Config not found' },
        { status: 404 }
      );
    }

    return NextResponse.json({
      success: true,
      config: result,
      message: 'Weight config updated. Run refresh to apply to all ads.',
    });
  } catch (error) {
    console.error('Error updating weight config:', error);
    return NextResponse.json(
      { error: 'Failed to update weight config' },
      { status: 500 }
    );
  }
}
