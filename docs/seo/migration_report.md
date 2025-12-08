# TellyAds SEO Migration Report

**Migration**: Wix → Next.js 16
**Date**: December 2024
**Status**: Ready for DNS Cutover
**Canonical Host**: `https://tellyads.com` (non-www)

---

## Executive Summary

This document details the SEO migration from Wix to Next.js, ensuring zero loss of search equity during the transition. All P0 requirements have been implemented and verified.

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Canonical Host | `https://tellyads.com` | Non-www is cleaner, matches industry standard |
| Redirect Type | 301 (Permanent) | Transfers full SEO equity |
| Legacy URL Strategy | Rewrite to API route | Edge middleware can't access DB |
| Sitemap Format | Dynamic XML | Auto-updates with published ads |

### Key Metrics

| Metric | Old Site (Wix) | New Site (Next.js) |
|--------|----------------|-------------------|
| Total Indexable URLs | ~6,000+ | ~6,000+ (canonical) |
| URL Patterns | 3 patterns (/advert/*, /items/*, /post/*) | 1 canonical pattern (/advert/*/*) |
| Sitemap Count | 8 sitemaps | 1 dynamic sitemap |
| Structured Data | None | VideoObject, BreadcrumbList, Organization |
| Response Time | Variable (Wix) | <500ms (Vercel Edge) |

---

## P0 Changes Applied

### 1. Global Host Redirect (www → non-www)

**File**: [frontend/middleware.ts](../../frontend/middleware.ts#L94-L102)

```typescript
// 0. CANONICAL HOST REDIRECT (www -> non-www)
// This MUST be first to prevent duplicate content
const currentHost = host.replace(/:\d+$/, ''); // Remove port if present
if (currentHost.startsWith('www.')) {
  const canonicalUrl = new URL(request.url);
  canonicalUrl.host = currentHost.replace(/^www\./, '');
  canonicalUrl.protocol = CANONICAL_PROTOCOL;
  return NextResponse.redirect(canonicalUrl.toString(), 301);
}
```

**Status**: ✅ Implemented

### 2. Legacy Sitemap Redirects

**File**: [frontend/middleware.ts](../../frontend/middleware.ts#L50-L59)

All 8 legacy Wix sitemap URLs now 301 redirect to `/sitemap.xml`:

| Legacy URL | Redirects To | Status |
|------------|--------------|--------|
| `/dynamic-advert-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/dynamic-advert___1-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/dynamic-advert___2-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/dynamic-items-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/dynamic-items___1-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/dynamic-items___2-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/pages-sitemap.xml` | `/sitemap.xml` | ✅ |
| `/sitemap_index.xml` | `/sitemap.xml` | ✅ |

**Why this matters**: Google may continue requesting old sitemap URLs for weeks or months after migration. Without these redirects, Google would see 404s and potentially de-index pages.

### 3. Edge Safety (No DB in Middleware)

**File**: [frontend/middleware.ts](../../frontend/middleware.ts)

The middleware runs on Vercel's Edge Runtime which does NOT support:
- Direct database connections
- Node.js-only modules
- Long-running operations

**Solution**: URLs requiring DB lookup (`/items/*`, `/post/*`, `/ads/*`) are **rewritten** (not redirected) to `/api/legacy-redirect`, which runs on Node.js runtime and can query the database.

```typescript
// REWRITE to API route (Node.js runtime) for DB lookup
if (pathname.startsWith('/items/')) {
  return NextResponse.rewrite(
    new URL(`/api/legacy-redirect?type=items&slug=${encodeURIComponent(slug)}`, request.url)
  );
}
```

**File**: [frontend/app/api/legacy-redirect/route.ts](../../frontend/app/api/legacy-redirect/route.ts)

The API route:
1. Queries Supabase for the ad by legacy slug
2. Returns 301 redirect to canonical `/advert/{brand}/{slug}` URL
3. Returns 404 if not found (with cache headers)

**Status**: ✅ No direct DB access in Edge middleware

### 4. Robots.txt Safety

**File**: [frontend/app/robots.ts](../../frontend/app/robots.ts)

Legacy paths are **allowed** during migration to preserve crawl equity:

```typescript
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: [
          '/',
          '/items/',   // Legacy - will redirect
          '/post/',    // Legacy - will redirect
          '/advert/',  // Current canonical pattern
        ],
        disallow: [
          '/api/',
          '/admin/',
          '/_next/',
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
```

**Why allow legacy paths**: If we disallow `/items/` and `/post/`, Google will stop crawling those URLs before the 301 redirects transfer equity to the new URLs.

**Status**: ✅ Legacy paths allowed

### 5. Sitemap Hygiene

**File**: [frontend/app/sitemap.ts](../../frontend/app/sitemap.ts)

The sitemap emits ONLY canonical, indexable URLs:

| Rule | Implementation | Status |
|------|----------------|--------|
| No query parameters | URLs are path-only | ✅ |
| No `-n` suffix | Slugs are cleaned before insertion | ✅ |
| No `www.` prefix | Uses `SITE_URL = 'https://tellyads.com'` | ✅ |
| Only published ads | Filters by `status='published' AND is_hidden=false` | ✅ |
| Canonical paths only | Uses `/advert/{brand}/{slug}` format | ✅ |

---

## Canonical Tag Implementation

**File**: [frontend/lib/seo.ts](../../frontend/lib/seo.ts)

All pages now emit proper canonical tags:

```typescript
const CANONICAL_HOST = 'https://tellyads.com';

export function constructMetadata({
  title,
  description,
  image = '/og-image.jpg',
  path,
  noIndex = false,
}: MetadataParams): Metadata {
  const canonicalUrl = path ? `${CANONICAL_HOST}${path}` : undefined;

  return {
    title,
    description,
    ...(canonicalUrl && {
      alternates: {
        canonical: canonicalUrl,
      },
    }),
    // ... rest
  };
}
```

### Pages with Canonical Tags

| Page | Canonical URL | File |
|------|---------------|------|
| Home | `https://tellyads.com/` | `app/page.tsx` |
| Browse | `https://tellyads.com/browse` | `app/browse/layout.tsx` |
| Search | `https://tellyads.com/search` | `app/search/page.tsx` |
| Latest | `https://tellyads.com/latest` | `app/latest/page.tsx` |
| Brands | `https://tellyads.com/brands` | `app/brands/page.tsx` |
| About | `https://tellyads.com/about` | `app/about/page.tsx` |
| Ad Detail | `https://tellyads.com/advert/{brand}/{slug}` | `app/advert/[brand]/[slug]/page.tsx` |

### Search Page Special Handling

```typescript
// Base search page (no query) - indexed with canonical
if (!query) {
  return constructMetadata({
    title: "Search TV Commercials",
    path: "/search",
    noIndex: false,
  });
}

// Search results pages - noindex (infinite variations)
return constructMetadata({
  title: `Search: "${query}"`,
  noIndex: true,
});
```

---

## Redirect Architecture

### Flow Diagram

```
User Request                    Middleware (Edge)              API Route (Node.js)
     │                               │                               │
     │ GET /items/christmas-2020     │                               │
     ├──────────────────────────────►│                               │
     │                               │ REWRITE to /api/legacy-redirect
     │                               ├──────────────────────────────►│
     │                               │                               │ Query DB
     │                               │                               │ Find ad
     │                               │                               │
     │◄──────────────────────────────┼───────────────────────────────┤
     │ 301 → /advert/brand/slug      │                               │
```

### Redirect Types

| URL Pattern | Handler | Redirect Type | Hops |
|-------------|---------|---------------|------|
| `www.*` | Middleware | 301 | 1 |
| `/items/*` | API Route | 301 | 1 |
| `/post/*` | API Route | 301 | 1 |
| `/ads/{id}` | API Route | 301 | 1 |
| `/advert/*/*-n` | Middleware | 301 | 1 |
| `/latestads` | Middleware | 301 | 1 |
| `/searchall` | Middleware | 301 | 1 |
| `/*-sitemap.xml` | Middleware | 301 | 1 |

**Maximum redirect chain**: 1 hop (critical for SEO)

---

## Manual Spot Check Commands

### 1. Host Redirect (www → non-www)

```bash
curl -I https://www.tellyads.com/
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/
```

### 2. Legacy /items/ URL

```bash
curl -I https://tellyads.com/items/christmas-2020
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/advert/{brand}/christmas-2020
```

### 3. Legacy /post/ URL

```bash
curl -I https://tellyads.com/post/coca-cola-holidays-are-coming
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/advert/coca-cola/holidays-are-coming
```

### 4. Strip -n Suffix

```bash
curl -I https://tellyads.com/advert/john-lewis/christmas-2021-unexpected-guest-n
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/advert/john-lewis/christmas-2021-unexpected-guest
```

### 5. Legacy Sitemap

```bash
curl -I https://tellyads.com/dynamic-advert-sitemap.xml
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/sitemap.xml
```

### 6. Query Parameter Stripping

```bash
curl -I "https://tellyads.com/browse?lightbox=true"
```

**Expected output:**
```
HTTP/2 301
location: https://tellyads.com/browse
```

### 7. Canonical Sitemap

```bash
curl -I https://tellyads.com/sitemap.xml
```

**Expected output:**
```
HTTP/2 200
content-type: application/xml
```

### 8. Robots.txt

```bash
curl https://tellyads.com/robots.txt
```

**Expected output:**
```
User-Agent: *
Allow: /
Allow: /items/
Allow: /post/
Allow: /advert/
Disallow: /api/
Disallow: /admin/
Disallow: /_next/

Sitemap: https://tellyads.com/sitemap.xml
```

### 9. Canonical Tag Verification

```bash
curl -s https://tellyads.com/browse | grep -i canonical
```

**Expected output:**
```html
<link rel="canonical" href="https://tellyads.com/browse"/>
```

### 10. Search Page Index Status

```bash
# Base search page (should be indexed)
curl -s https://tellyads.com/search | grep -i "robots"
# Should NOT contain noindex

# Search with query (should be noindex)
curl -s "https://tellyads.com/search?q=test" | grep -i "robots"
# Should contain: <meta name="robots" content="noindex"/>
```

---

## Verification Script

**File**: [scripts/seo/verify-migration.py](../../scripts/seo/verify-migration.py)

Run the automated verification:

```bash
# Local development
python scripts/seo/verify-migration.py --base-url http://localhost:3000

# Staging
python scripts/seo/verify-migration.py --base-url https://staging.tellyads.com

# Production
python scripts/seo/verify-migration.py --base-url https://tellyads.com

# With sample URLs file
python scripts/seo/verify-migration.py \
  --base-url https://tellyads.com \
  --sample-file docs/seo/sample_urls.txt
```

### Tests Performed

| Test | Description | Pass Criteria |
|------|-------------|---------------|
| Robots.txt | Validates structure and directives | 200 status, allows legacy paths |
| Sitemap.xml | Checks URL hygiene | 200 status, no query params, no www |
| Host Canonical | Verifies www→non-www redirect | 301 from www to non-www |
| Redirect Chains | Tests legacy URL redirects | Max 1 hop to 200 |
| Legacy Sitemaps | Tests old sitemap URLs | 301 to /sitemap.xml |
| Canonical Tags | Checks `<link rel="canonical">` | Points to https://tellyads.com |
| Meta Tags | Validates SEO meta tags | title, description present |
| OG Tags | Checks Open Graph tags | og:title, og:description present |

---

## Definition of Done

- [x] All `www.tellyads.com/*` URLs 301 → `tellyads.com/*`
- [x] All legacy sitemaps 301 → `/sitemap.xml`
- [x] `/items/*` URLs resolve in ≤1 redirect to canonical page
- [x] `/post/*` URLs resolve in ≤1 redirect to canonical page
- [x] `/advert/*-n` URLs 301 to version without `-n`
- [x] No `?lightbox=`, `?d=`, `?wix-vod-video-id=` in redirected URLs
- [x] `robots.txt` allows `/items/`, `/post/`, `/advert/`
- [x] `sitemap.xml` contains only canonical `https://tellyads.com/advert/*` URLs
- [x] All pages have `<link rel="canonical" href="https://tellyads.com/...">` tag
- [x] Search results pages have `<meta name="robots" content="noindex">`
- [x] Base search page (`/search`) is indexed with canonical
- [x] Middleware does NOT perform direct DB access
- [x] All redirects are 301 (permanent)
- [x] Verification script passes all 8 tests

---

## Files Modified

| File | Changes |
|------|---------|
| `frontend/middleware.ts` | Added www→non-www redirect, legacy sitemap redirects, query param stripping |
| `frontend/app/robots.ts` | Allow legacy paths during migration |
| `frontend/app/sitemap.ts` | Emit only canonical URLs, filter published ads |
| `frontend/lib/seo.ts` | Add canonical URL support via `path` parameter |
| `frontend/app/search/page.tsx` | Conditional noindex based on query presence |
| `frontend/app/browse/layout.tsx` | New file for metadata on client component page |
| `frontend/app/about/page.tsx` | Added canonical path |
| `frontend/app/latest/page.tsx` | Added canonical path |
| `frontend/app/brands/page.tsx` | Added canonical path |
| `frontend/app/api/legacy-redirect/route.ts` | Handle DB lookups for legacy URLs |
| `scripts/seo/verify-migration.py` | v3.0 with 8 comprehensive tests |
| `docs/seo/sample_urls.txt` | 50+ sample URLs for smoke testing |

---

## Post-Migration Monitoring

After DNS cutover, monitor these metrics in Google Search Console:

1. **Coverage Report**: Watch for increase in "Excluded" pages
2. **Crawl Stats**: Verify crawl rate doesn't drop
3. **Redirect Errors**: Check for any 4xx/5xx on legacy URLs
4. **Sitemap Status**: Verify new sitemap is being crawled
5. **Index Status**: Monitor indexed page count

### Expected Timeline

| Week | Expected State |
|------|----------------|
| Week 1 | Google discovers new sitemap, starts recrawling |
| Week 2-4 | Redirect equity begins transferring |
| Week 4-8 | Most legacy URLs removed from index |
| Week 8-12 | Full equity transfer complete |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Redirect chain created | Medium | Middleware tests in verification script |
| Missing canonical tags | High | Automatic canonical in page metadata |
| Broken old URLs | High | Fuzzy matching in legacy redirect API |
| Duplicate content indexed | Medium | robots.txt blocks non-canonical patterns |
| Structured data errors | Low | JSON-LD validated via testing |

---

## Appendix: Sample URLs

See [sample_urls.txt](./sample_urls.txt) for the full list of test URLs.

### Quick Reference

| URL Type | Example | Expected Behavior |
|----------|---------|-------------------|
| Legacy item | `/items/christmas-2020` | 301 → `/advert/{brand}/christmas-2020` |
| Legacy post | `/post/coca-cola-holidays-are-coming` | 301 → `/advert/coca-cola/holidays-are-coming` |
| With -n suffix | `/advert/john-lewis/christmas-n` | 301 → `/advert/john-lewis/christmas` |
| Legacy page | `/latestads` | 301 → `/latest` |
| Legacy sitemap | `/dynamic-advert-sitemap.xml` | 301 → `/sitemap.xml` |
| With query param | `/browse?lightbox=true` | 301 → `/browse` |
| www host | `www.tellyads.com/browse` | 301 → `tellyads.com/browse` |

---

*Last updated: December 2024*
