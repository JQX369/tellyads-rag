import type { NextConfig } from "next";

// Security headers for production hardening
const securityHeaders = [
  // Prevent MIME type sniffing
  {
    key: 'X-Content-Type-Options',
    value: 'nosniff',
  },
  // Referrer policy
  {
    key: 'Referrer-Policy',
    value: 'strict-origin-when-cross-origin',
  },
  // Prevent clickjacking
  {
    key: 'X-Frame-Options',
    value: 'SAMEORIGIN',
  },
  // Disable unnecessary browser features
  {
    key: 'Permissions-Policy',
    value: 'camera=(), microphone=(), geolocation=(), browsing-topics=()',
  },
  // DNS prefetch for performance
  {
    key: 'X-DNS-Prefetch-Control',
    value: 'on',
  },
];

// HSTS header (only for production HTTPS)
const hstsHeader = {
  key: 'Strict-Transport-Security',
  value: 'max-age=63072000; includeSubDomains; preload',
};

const nextConfig: NextConfig = {
  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.supabase.co',
      },
      {
        protocol: 'https',
        hostname: 's3.amazonaws.com',
      },
      {
        protocol: 'https',
        hostname: '**.amazonaws.com',
      },
    ],
  },

  // Environment variables available at runtime
  env: {
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL || 'https://tellyads.com',
  },

  // Headers for security and caching
  async headers() {
    const isProd = process.env.NODE_ENV === 'production';

    // Add HSTS only in production
    const allSecurityHeaders = isProd
      ? [...securityHeaders, hstsHeader]
      : securityHeaders;

    return [
      // Apply security headers globally
      {
        source: '/:path*',
        headers: allSecurityHeaders,
      },
      // API routes - no caching by default for POST, short cache for GET
      {
        source: '/api/:path*',
        headers: [
          ...allSecurityHeaders,
          { key: 'Cache-Control', value: 'no-store, must-revalidate' },
        ],
      },
      // Static assets - long cache
      {
        source: '/_next/static/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
        ],
      },
      // Sitemap - moderate cache
      {
        source: '/sitemap.xml',
        headers: [
          ...allSecurityHeaders,
          { key: 'Cache-Control', value: 'public, s-maxage=3600, stale-while-revalidate=86400' },
        ],
      },
      // Robots - moderate cache
      {
        source: '/robots.txt',
        headers: [
          ...allSecurityHeaders,
          { key: 'Cache-Control', value: 'public, s-maxage=3600, stale-while-revalidate=86400' },
        ],
      },
    ];
  },
};

export default nextConfig;
