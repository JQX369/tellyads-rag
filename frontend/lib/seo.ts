import { Metadata } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://tellyads.com';

export const defaultMetadata: Metadata = {
  title: {
    default: 'TellyAds | The World\'s Largest TV Ad Archive',
    template: '%s | TellyAds'
  },
  description: 'Explore thousands of TV commercials, analyze creative trends, and find inspiration in the world\'s largest database of television advertising.',
  metadataBase: new URL(BASE_URL),
  openGraph: {
    type: 'website',
    locale: 'en_GB',
    url: BASE_URL,
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

export function constructMetadata({
  title,
  description,
  image = '/og-image.jpg',
  noIndex = false
}: {
  title?: string;
  description?: string;
  image?: string;
  noIndex?: boolean;
}): Metadata {
  return {
    title,
    description,
    openGraph: {
      title,
      description,
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

