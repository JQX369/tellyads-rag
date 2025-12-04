/**
 * Dynamic Sitemap Generation
 *
 * Generates sitemap.xml with all published editorial pages.
 * Uses ISR with revalidation.
 */

import { MetadataRoute } from 'next';
import { queryAll, PUBLISH_GATE_CONDITION } from '@/lib/db';

export const runtime = 'nodejs';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://tellyads.com';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/browse`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/search`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
  ];

  // Dynamic advert pages from published editorial
  try {
    const editorialPages = await queryAll(
      `
      SELECT
        e.brand_slug,
        e.slug,
        GREATEST(e.updated_at, a.updated_at) as last_modified
      FROM ad_editorial e
      JOIN ads a ON a.id = e.ad_id
      WHERE ${PUBLISH_GATE_CONDITION}
      ORDER BY e.updated_at DESC
      `
    );

    const advertPages: MetadataRoute.Sitemap = editorialPages.map((row) => ({
      url: `${BASE_URL}/advert/${row.brand_slug}/${row.slug}`,
      lastModified: row.last_modified ? new Date(row.last_modified) : new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.8,
    }));

    return [...staticPages, ...advertPages];
  } catch (error) {
    console.error('Error generating sitemap:', error);
    return staticPages;
  }
}
