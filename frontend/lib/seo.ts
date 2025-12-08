import { Metadata } from 'next';

// ALWAYS use non-www canonical host for SEO
const CANONICAL_HOST = 'https://tellyads.com';
const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || CANONICAL_HOST;

export const defaultMetadata: Metadata = {
  title: {
    default: 'TellyAds | The World\'s Largest TV Ad Archive',
    template: '%s | TellyAds'
  },
  description: 'Explore thousands of TV commercials, analyze creative trends, and find inspiration in the world\'s largest database of television advertising.',
  metadataBase: new URL(CANONICAL_HOST),
  alternates: {
    canonical: CANONICAL_HOST,
  },
  openGraph: {
    type: 'website',
    locale: 'en_GB',
    url: CANONICAL_HOST,
    siteName: 'TellyAds',
    title: 'TellyAds | The World\'s Largest TV Ad Archive',
    description: 'Explore thousands of TV commercials, analyze creative trends, and find inspiration in the world\'s largest database of television advertising.',
    images: [
      {
        url: '/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'TellyAds Archive',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'TellyAds | The World\'s Largest TV Ad Archive',
    description: 'Explore thousands of TV commercials, analyze creative trends, and find inspiration.',
    images: ['/og-image.jpg'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
};

/**
 * Construct page-specific metadata with canonical URL support
 *
 * @param path - The path for canonical URL (e.g., '/browse', '/about'). Required for SEO.
 * @param noIndex - Set to true for pages that shouldn't be indexed (search results, etc.)
 */
export function constructMetadata({
  title,
  description,
  image = '/og-image.jpg',
  path,
  noIndex = false
}: {
  title?: string;
  description?: string;
  image?: string;
  path?: string;
  noIndex?: boolean;
}): Metadata {
  const canonicalUrl = path ? `${CANONICAL_HOST}${path}` : undefined;

  return {
    title,
    description,
    ...(canonicalUrl && {
      alternates: {
        canonical: canonicalUrl,
      },
    }),
    openGraph: {
      title,
      description,
      ...(canonicalUrl && { url: canonicalUrl }),
      images: [
        {
          url: image,
        },
      ],
    },
    twitter: {
      title,
      description,
      images: [image],
    },
    robots: {
      index: !noIndex,
      follow: !noIndex,
    },
  };
}

/**
 * Get canonical URL for a path
 */
export function getCanonicalUrl(path: string): string {
  return `${CANONICAL_HOST}${path}`;
}
