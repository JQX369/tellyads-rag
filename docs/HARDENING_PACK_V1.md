# Hardening Pack v1 - TellyAds Production Deployment

**Generated:** December 4, 2025
**Status:** Ready for Implementation
**Scope:** Vercel-only deployment (Next.js App Router)

---

## Audit Summary

### Files Audited
- **14 API Routes** in `frontend/app/api/`
- **12 Pages** in `frontend/app/`
- **Key libs:** `lib/db.ts`, `middleware.ts`, `next.config.ts`

### Key Findings

| Area | Status | Notes |
|------|--------|-------|
| SQL Parameterization | **PASS** | All queries use `$1`, `$2` placeholders |
| DB Pool Config | **PASS** | `max:10`, timeouts configured |
| Publish Gating | **PASS** | `PUBLISH_GATE_CONDITION` applied consistently |
| Runtime Declaration | **FAIL** | No `export const runtime = "nodejs"` |
| Security Headers | **FAIL** | Only Cache-Control present |
| Rate Limiting | **FAIL** | No protection on `/api/search` |
| Input Validation | **FAIL** | No zod schemas |
| Admin Security | **CRITICAL** | `NEXT_PUBLIC_ADMIN_PASSWORD` exposed to client |
| session_id Pattern | **WARN** | Inconsistent (body vs query param) |

---

## Prioritized Checklist

### P0 - Must Fix Before Production

| ID | Issue | Risk | File(s) |
|----|-------|------|---------|
| P0-1 | Admin password exposed via NEXT_PUBLIC_ | **CRITICAL** - Anyone can see password in browser | `frontend/app/admin/page.tsx` |
| P0-2 | No runtime declaration | Vercel may default to Edge which breaks pg | All 14 route files |
| P0-3 | No security headers | XSS, clickjacking, MIME sniffing | `frontend/next.config.ts` |
| P0-4 | No rate limiting on /api/search | OpenAI cost explosion | `frontend/app/api/search/route.ts` |

### P1 - Should Fix

| ID | Issue | Risk | File(s) |
|----|-------|------|---------|
| P1-1 | No input validation | Malformed requests, injection vectors | All POST routes |
| P1-2 | Inconsistent session_id handling | Confusing API, potential bugs | POST routes + GET feedback |
| P1-3 | No CORS configuration | API abuse from other origins | `frontend/next.config.ts` |
| P1-4 | No request logging | No observability for debugging | `frontend/middleware.ts` |

### P2 - Nice to Have

| ID | Issue | Risk | File(s) |
|----|-------|------|---------|
| P2-1 | No sitemap caching headers | Frequent regeneration | `frontend/app/sitemap.ts` |
| P2-2 | No structured error responses | Inconsistent error format | All routes |
| P2-3 | No OpenTelemetry tracing | Limited production debugging | New middleware |

---

## Implementation Plan

### P0-1: Fix Admin Password Exposure (CRITICAL)

**Problem:** `NEXT_PUBLIC_ADMIN_PASSWORD` is visible in client-side JavaScript bundle.

**Solution:** Move admin to API route with server-only env var and X-Admin-Key header.

#### Files to Create/Modify:

**1. Create `frontend/app/api/admin/verify/route.ts`:**

```typescript
/**
 * Admin Verification API
 * POST /api/admin/verify
 *
 * Verifies X-Admin-Key header against server-side secret.
 */

import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const ADMIN_KEY = process.env.ADMIN_KEY; // Server-only, no NEXT_PUBLIC_

export async function POST(request: NextRequest) {
  const adminKey = request.headers.get('x-admin-key');

  if (!ADMIN_KEY) {
    console.error('ADMIN_KEY not configured');
    return NextResponse.json(
      { error: 'Admin not configured' },
      { status: 503 }
    );
  }

  if (!adminKey || adminKey !== ADMIN_KEY) {
    return NextResponse.json(
      { error: 'Unauthorized' },
      { status: 401 }
    );
  }

  return NextResponse.json({ verified: true });
}
```

**2. Modify `frontend/app/admin/page.tsx`:**

```typescript
'use client';

import { useState, useEffect } from 'react';

export default function AdminPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/admin/verify', {
        method: 'POST',
        headers: {
          'x-admin-key': adminKey,
        },
      });

      if (res.ok) {
        sessionStorage.setItem('admin_key', adminKey);
        setIsAuthenticated(true);
      } else {
        setError('Invalid admin key');
      }
    } catch {
      setError('Verification failed');
    } finally {
      setLoading(false);
    }
  };

  // Check for existing session
  useEffect(() => {
    const stored = sessionStorage.getItem('admin_key');
    if (stored) {
      // Re-verify stored key
      fetch('/api/admin/verify', {
        method: 'POST',
        headers: { 'x-admin-key': stored },
      }).then(res => {
        if (res.ok) setIsAuthenticated(true);
        else sessionStorage.removeItem('admin_key');
      });
    }
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-black">
        <form onSubmit={handleLogin} className="bg-gray-900 p-8 rounded-lg">
          <h1 className="text-2xl font-bold mb-6 text-white">Admin Access</h1>
          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="Enter admin key"
            className="w-full p-3 mb-4 bg-gray-800 text-white rounded"
            disabled={loading}
          />
          {error && <p className="text-red-500 mb-4">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full p-3 bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Login'}
          </button>
        </form>
      </div>
    );
  }

  // Render admin dashboard...
  return (
    <div className="min-h-screen bg-black text-white p-8">
      <h1 className="text-3xl font-bold mb-8">Admin Dashboard</h1>
      {/* Admin content here */}
    </div>
  );
}
```

**3. Update `.env.example` and `.env`:**

```bash
# Remove this:
# NEXT_PUBLIC_ADMIN_PASSWORD=your_secure_password

# Add this (server-only):
ADMIN_KEY=generate_a_secure_random_key_here
```

---

### P0-2: Add Runtime Declarations

**Problem:** Without explicit runtime, Vercel may use Edge Runtime which doesn't support `pg` native module.

**Solution:** Add `export const runtime = 'nodejs';` to all route files.

#### Files to Modify (14 total):

```
frontend/app/api/search/route.ts
frontend/app/api/recent/route.ts
frontend/app/api/status/route.ts
frontend/app/api/legacy-redirect/route.ts
frontend/app/api/ads/[external_id]/route.ts
frontend/app/api/ads/[external_id]/view/route.ts
frontend/app/api/ads/[external_id]/like/route.ts
frontend/app/api/ads/[external_id]/save/route.ts
frontend/app/api/ads/[external_id]/reasons/route.ts
frontend/app/api/ads/[external_id]/similar/route.ts
frontend/app/api/ads/[external_id]/feedback/route.ts
frontend/app/api/advert/[brand]/[slug]/route.ts
frontend/app/sitemap.ts
frontend/app/robots.ts
```

**Code to add (after imports, before first export):**

```typescript
export const runtime = 'nodejs';
```

---

### P0-3: Add Security Headers

**Modify `frontend/next.config.ts`:**

```typescript
import type { NextConfig } from 'next';

const securityHeaders = [
  {
    key: 'X-DNS-Prefetch-Control',
    value: 'on',
  },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload',
  },
  {
    key: 'X-Frame-Options',
    value: 'SAMEORIGIN',
  },
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  },
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=()',
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
      {
        source: '/api/:path*',
        headers: [
          ...securityHeaders,
          { key: 'Cache-Control', value: 'no-store, must-revalidate' },
        ],
      },
      {
        source: '/_next/static/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
        ],
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.supabase.co' },
      { protocol: 'https', hostname: '**.cloudfront.net' },
    ],
  },
};

export default nextConfig;
```

---

### P0-4: Rate Limiting for /api/search

**Create `frontend/lib/rate-limit.ts`:**

```typescript
/**
 * Simple in-memory rate limiter for Vercel serverless.
 * Uses sliding window counter algorithm.
 *
 * Note: This is per-instance. For distributed rate limiting,
 * use Vercel KV or Upstash Redis.
 */

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const cache = new Map<string, RateLimitEntry>();

// Clean up old entries periodically
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of cache.entries()) {
    if (entry.resetAt < now) {
      cache.delete(key);
    }
  }
}, 60000); // Every minute

export interface RateLimitConfig {
  windowMs: number;  // Time window in milliseconds
  max: number;       // Max requests per window
}

export interface RateLimitResult {
  success: boolean;
  remaining: number;
  resetAt: number;
}

export function checkRateLimit(
  identifier: string,
  config: RateLimitConfig
): RateLimitResult {
  const now = Date.now();
  const key = identifier;

  const entry = cache.get(key);

  if (!entry || entry.resetAt < now) {
    // New window
    cache.set(key, {
      count: 1,
      resetAt: now + config.windowMs,
    });
    return {
      success: true,
      remaining: config.max - 1,
      resetAt: now + config.windowMs,
    };
  }

  if (entry.count >= config.max) {
    return {
      success: false,
      remaining: 0,
      resetAt: entry.resetAt,
    };
  }

  entry.count++;
  return {
    success: true,
    remaining: config.max - entry.count,
    resetAt: entry.resetAt,
  };
}

/**
 * Get rate limit identifier from request.
 * Uses X-Forwarded-For (Vercel provides this) or falls back to a hash.
 */
export function getRateLimitKey(request: Request): string {
  // Vercel provides client IP in X-Forwarded-For
  const forwarded = request.headers.get('x-forwarded-for');
  const ip = forwarded?.split(',')[0]?.trim() || 'anonymous';

  // Hash the IP to avoid storing raw IPs
  return `rl:${hashString(ip)}`;
}

function hashString(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36);
}
```

**Modify `frontend/app/api/search/route.ts`:**

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { queryAll, queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';
import { checkRateLimit, getRateLimitKey } from '@/lib/rate-limit';
import OpenAI from 'openai';

export const runtime = 'nodejs';

// Rate limit: 30 requests per minute per IP
const RATE_LIMIT_CONFIG = {
  windowMs: 60 * 1000,
  max: 30,
};

export async function GET(request: NextRequest) {
  // Rate limiting
  const rateLimitKey = getRateLimitKey(request);
  const rateLimitResult = checkRateLimit(rateLimitKey, RATE_LIMIT_CONFIG);

  if (!rateLimitResult.success) {
    return NextResponse.json(
      { error: 'Too many requests. Please try again later.' },
      {
        status: 429,
        headers: {
          'Retry-After': Math.ceil((rateLimitResult.resetAt - Date.now()) / 1000).toString(),
          'X-RateLimit-Remaining': '0',
          'X-RateLimit-Reset': rateLimitResult.resetAt.toString(),
        },
      }
    );
  }

  // ... rest of existing search logic ...
}
```

---

### P1-1: Input Validation with Zod

**Create `frontend/lib/validation.ts`:**

```typescript
import { z } from 'zod';

// Session ID: UUID v4 format
export const sessionIdSchema = z.string().uuid('Invalid session ID format');

// External ID: alphanumeric with hyphens/underscores
export const externalIdSchema = z.string()
  .min(1, 'External ID required')
  .max(100, 'External ID too long')
  .regex(/^[a-zA-Z0-9_-]+$/, 'Invalid external ID format');

// Search query
export const searchQuerySchema = z.string()
  .min(1, 'Query required')
  .max(500, 'Query too long');

// Pagination
export const paginationSchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20),
  offset: z.coerce.number().int().min(0).default(0),
});

// Reason enum
export const reasonSchema = z.enum([
  'creative',
  'funny',
  'memorable',
  'emotional',
  'informative',
  'well_produced',
  'catchy_music',
  'good_acting',
  'clever_concept',
  'beautiful_visually',
]);

// View request body
export const viewRequestSchema = z.object({
  session_id: sessionIdSchema,
});

// Like/Save request body
export const likeRequestSchema = z.object({
  session_id: sessionIdSchema,
});

// Reason request body
export const reasonRequestSchema = z.object({
  session_id: sessionIdSchema,
  reason: reasonSchema,
});

// Helper to validate and return typed result or error response
export function validateBody<T>(
  schema: z.ZodSchema<T>,
  data: unknown
): { success: true; data: T } | { success: false; error: string } {
  const result = schema.safeParse(data);
  if (!result.success) {
    const firstError = result.error.errors[0];
    return {
      success: false,
      error: `${firstError.path.join('.')}: ${firstError.message}`,
    };
  }
  return { success: true, data: result.data };
}
```

**Install zod:**

```bash
cd frontend && npm install zod
```

---

### P1-2: Standardize session_id Handling

**Create `frontend/lib/session.ts`:**

```typescript
import { NextRequest } from 'next/server';
import { sessionIdSchema } from './validation';

/**
 * Extract and validate session_id from request.
 *
 * For POST requests: reads from JSON body
 * For GET requests: reads from query parameter
 *
 * Returns validated session_id or null if invalid/missing.
 */
export async function getSessionId(
  request: NextRequest,
  body?: Record<string, unknown>
): Promise<string | null> {
  let sessionId: string | null = null;

  if (request.method === 'GET') {
    const { searchParams } = new URL(request.url);
    sessionId = searchParams.get('session_id');
  } else if (body) {
    sessionId = body.session_id as string | null;
  }

  if (!sessionId) return null;

  const result = sessionIdSchema.safeParse(sessionId);
  return result.success ? result.data : null;
}
```

---

### P1-3: CORS Configuration

**Add to `frontend/next.config.ts` headers function:**

```typescript
// Add CORS headers for API routes
{
  source: '/api/:path*',
  headers: [
    { key: 'Access-Control-Allow-Origin', value: process.env.NEXT_PUBLIC_SITE_URL || 'https://tellyads.com' },
    { key: 'Access-Control-Allow-Methods', value: 'GET, POST, OPTIONS' },
    { key: 'Access-Control-Allow-Headers', value: 'Content-Type, X-Admin-Key' },
    { key: 'Access-Control-Max-Age', value: '86400' },
  ],
},
```

---

## Acceptance Tests

### Local Testing

```bash
# 1. Install dependencies
cd frontend && npm install zod

# 2. Start dev server
npm run dev

# 3. Test security headers
curl -I http://localhost:3000 | grep -E "(X-Frame-Options|X-Content-Type|Strict-Transport)"

# 4. Test rate limiting (run 35 times quickly)
for i in {1..35}; do curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3000/api/search?q=test"; done
# Should see 429 after ~30 requests

# 5. Test admin verification
curl -X POST http://localhost:3000/api/admin/verify -H "x-admin-key: wrong" -w "%{http_code}"
# Should return 401

curl -X POST http://localhost:3000/api/admin/verify -H "x-admin-key: YOUR_ADMIN_KEY" -w "%{http_code}"
# Should return 200

# 6. Test input validation
curl -X POST http://localhost:3000/api/ads/test-ad/view \
  -H "Content-Type: application/json" \
  -d '{"session_id": "not-a-uuid"}'
# Should return 400 with validation error

# 7. Build check
npm run build
# Should complete without errors
```

### Vercel Preview Testing

```bash
# Deploy to preview
vercel

# 1. Check headers
curl -I https://your-preview.vercel.app | grep -E "(X-Frame-Options|Strict-Transport)"

# 2. Verify admin not accessible without key
curl -X POST https://your-preview.vercel.app/api/admin/verify -w "%{http_code}"
# Should return 401

# 3. Test search rate limiting
# (Use browser dev tools to monitor 429 responses)

# 4. Check no NEXT_PUBLIC_ADMIN_PASSWORD in source
# View source in browser, search for "tellyads2024" - should NOT appear
```

---

## Go/No-Go Gate

### Must Pass Before Production

- [ ] **P0-1**: Admin key NOT visible in browser source/network tab
- [ ] **P0-2**: All routes have `runtime = 'nodejs'`
- [ ] **P0-3**: Security headers present (`curl -I` test)
- [ ] **P0-4**: Rate limiting returns 429 after threshold
- [ ] **Build**: `npm run build` succeeds
- [ ] **Deploy**: Vercel preview deployment succeeds
- [ ] **Smoke Test**: Search, view ad, like/save all work

### Should Pass (Non-blocking)

- [ ] **P1-1**: Invalid session_id returns 400
- [ ] **P1-2**: CORS headers present for API routes
- [ ] **P1-3**: Console has no errors on page load

---

## Files Summary

### Create New (4 files)
- `frontend/app/api/admin/verify/route.ts` - Admin auth endpoint
- `frontend/lib/rate-limit.ts` - Rate limiting utility
- `frontend/lib/validation.ts` - Zod schemas
- `frontend/lib/session.ts` - Session ID helper

### Modify Existing (17 files)
- `frontend/next.config.ts` - Security headers + CORS
- `frontend/app/admin/page.tsx` - Use API for auth
- `frontend/app/api/search/route.ts` - Add rate limiting + runtime
- `frontend/app/api/recent/route.ts` - Add runtime
- `frontend/app/api/status/route.ts` - Add runtime
- `frontend/app/api/legacy-redirect/route.ts` - Add runtime
- `frontend/app/api/ads/[external_id]/route.ts` - Add runtime
- `frontend/app/api/ads/[external_id]/view/route.ts` - Add runtime + validation
- `frontend/app/api/ads/[external_id]/like/route.ts` - Add runtime + validation
- `frontend/app/api/ads/[external_id]/save/route.ts` - Add runtime + validation
- `frontend/app/api/ads/[external_id]/reasons/route.ts` - Add runtime + validation
- `frontend/app/api/ads/[external_id]/similar/route.ts` - Add runtime
- `frontend/app/api/ads/[external_id]/feedback/route.ts` - Add runtime
- `frontend/app/api/advert/[brand]/[slug]/route.ts` - Add runtime
- `frontend/app/sitemap.ts` - Add runtime
- `frontend/app/robots.ts` - Add runtime

### Environment Changes
- Remove: `NEXT_PUBLIC_ADMIN_PASSWORD`
- Add: `ADMIN_KEY` (server-only)

---

## Estimated Effort

| Priority | Items | Effort |
|----------|-------|--------|
| P0 | 4 issues | ~2 hours |
| P1 | 4 issues | ~1.5 hours |
| P2 | 3 issues | ~1 hour |
| Testing | All | ~1 hour |
| **Total** | | **~5.5 hours** |

---

## Next Steps

1. Review and approve this plan
2. Implement P0 items first
3. Run local acceptance tests
4. Deploy to Vercel preview
5. Run preview acceptance tests
6. If all pass: deploy to production
