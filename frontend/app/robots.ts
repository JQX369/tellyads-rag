/**
 * Dynamic robots.txt Generation
 *
 * CRITICAL SEO MIGRATION NOTE:
 * During migration, we MUST allow crawling of legacy paths (/items/, /post/, /advert/)
 * so search engines can discover the 301 redirects and update their index.
 * Only block truly private paths.
 *
 * Allows:
 * - All public content including legacy URLs (so redirects are discovered)
 * - Ad pages at canonical /advert/*
 *
 * Blocks:
 * - /api/ (server-side only)
 * - /admin/ (private)
 * - /_next/ (internal)
 * - Query parameter artifacts from Wix
 */

import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  // ALWAYS use non-www canonical (tellyads.com, not www.tellyads.com)
  const canonicalHost = 'https://tellyads.com';

  return {
    rules: [
      // Default rules for all bots
      {
        userAgent: '*',
        allow: [
          '/',
          // EXPLICITLY allow legacy paths so Google can follow redirects
          '/items/',
          '/post/',
          '/advert/',
        ],
        disallow: [
          // Only block truly private/internal paths
          '/api/',
          '/_next/',
          '/admin/',

          // Query parameter artifacts (Wix)
          '/*?lightbox=',
          '/*?d=',
          '/*?wix-vod-video-id=',
        ],
      },

      // Block GPTBot (AI scraping)
      {
        userAgent: 'GPTBot',
        disallow: ['/'],
      },

      // Block CCBot (Common Crawl for AI training)
      {
        userAgent: 'CCBot',
        disallow: ['/'],
      },

      // Block PetalBot (aggressive crawler)
      {
        userAgent: 'PetalBot',
        disallow: ['/'],
      },

      // Crawl-delay for aggressive bots
      {
        userAgent: 'dotbot',
        crawlDelay: 10,
        allow: '/',
      },
      {
        userAgent: 'AhrefsBot',
        crawlDelay: 10,
        allow: '/',
      },
    ],
    // IMPORTANT: Use canonical host for sitemap reference
    sitemap: `${canonicalHost}/sitemap.xml`,
  };
}
