/**
 * Dynamic Sitemap Generation
 *
 * SEO BEST PRACTICES:
 * - Only include canonical URLs (no query parameters)
 * - Only include pages that return 200 with self-referencing canonical
 * - Use canonical host (non-www)
 *
 * Generates sitemap.xml with:
 * - Static pages (home, browse, search, latest, about, brands)
 * - Dynamic advert pages from published editorial
 *
 * NOTE: Brand and decade URLs removed - they use query params which are not canonical.
 * When /brand/{slug} and /decade/{decade} hub pages are implemented, add them back.
 */

import { MetadataRoute } from 'next';
import { queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

// Revalidate sitemap every hour
export const revalidate = 3600;

// ALWAYS use non-www canonical host
const CANONICAL_HOST = 'https://tellyads.com';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Static pages with their priorities
  // Only include pages that exist and have unique content
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${CANONICAL_HOST}`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: `${CANONICAL_HOST}/browse`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${CANONICAL_HOST}/search`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${CANONICAL_HOST}/latest`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${CANONICAL_HOST}/brands`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.7,
    },
    {
      url: `${CANONICAL_HOST}/about`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.5,
    },
  ];

  // Dynamic advert pages from published editorial
  try {
    const editorialPages = await queryAll(
      `
      SELECT
        e.brand_slug,
        e.slug,
        GREATEST(e.updated_at, a.updated_at) as last_modified,
        e.is_featured
      FROM ad_editorial e
      JOIN ads a ON a.id = e.ad_id
      WHERE ${PUBLISH_GATE_CONDITION}
      ORDER BY e.is_featured DESC, e.updated_at DESC
      `
    );

    const advertPages: MetadataRoute.Sitemap = editorialPages.map((row) => ({
      url: `${CANONICAL_HOST}/advert/${row.brand_slug}/${row.slug}`,
      lastModified: row.last_modified ? new Date(row.last_modified) : new Date(),
      changeFrequency: 'weekly' as const,
      // Featured ads get higher priority
      priority: row.is_featured ? 0.9 : 0.8,
    }));

    // NOTE: Removed /search?brand= and /search?decade= URLs
    // Query parameter URLs should NOT be in sitemap because:
    // 1. They are not canonical URLs
    // 2. Search engines prefer path-based URLs
    // 3. They can cause duplicate content issues
    //
    // TODO: When implementing /brand/{slug} and /decade/{decade} hub pages,
    // add them here with unique content per page.

    return [...staticPages, ...advertPages];
  } catch (error) {
    console.error('Error generating sitemap:', error);
    // Return static pages only on error
    return staticPages;
  }
}
