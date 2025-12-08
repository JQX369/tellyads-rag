/**
 * JSON-LD Structured Data Components for SEO
 *
 * Implements Schema.org structured data for:
 * - VideoObject (ad detail pages)
 * - BreadcrumbList (navigation)
 * - ItemList (list pages)
 * - Organization (site-wide)
 * - WebSite (search action)
 */

import Script from 'next/script';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://tellyads.com';

// VideoObject schema for ad detail pages
interface VideoObjectProps {
  name: string;
  description: string;
  thumbnailUrl?: string;
  uploadDate?: string;
  duration?: number; // in seconds
  brandName: string;
  year?: number;
  canonicalUrl: string;
}

export function VideoObjectJsonLd({
  name,
  description,
  thumbnailUrl,
  uploadDate,
  duration,
  brandName,
  year,
  canonicalUrl,
}: VideoObjectProps) {
  // Convert duration to ISO 8601 format (PT1M30S for 1 min 30 sec)
  const isoDuration = duration
    ? `PT${Math.floor(duration / 60)}M${Math.round(duration % 60)}S`
    : undefined;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    name,
    description,
    thumbnailUrl: thumbnailUrl || `${BASE_URL}/og-image.png`,
    uploadDate: uploadDate || new Date().toISOString(),
    duration: isoDuration,
    publisher: {
      '@type': 'Organization',
      name: 'TellyAds',
      url: BASE_URL,
      logo: {
        '@type': 'ImageObject',
        url: `${BASE_URL}/logo.png`,
      },
    },
    creator: {
      '@type': 'Organization',
      name: brandName,
    },
    ...(year && { datePublished: `${year}-01-01` }),
    url: canonicalUrl,
    potentialAction: {
      '@type': 'WatchAction',
      target: canonicalUrl,
    },
  };

  return (
    <Script
      id="video-object-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// BreadcrumbList schema for navigation
interface BreadcrumbItem {
  name: string;
  url: string;
}

interface BreadcrumbListProps {
  items: BreadcrumbItem[];
}

export function BreadcrumbListJsonLd({ items }: BreadcrumbListProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url.startsWith('http') ? item.url : `${BASE_URL}${item.url}`,
    })),
  };

  return (
    <Script
      id="breadcrumb-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// ItemList schema for list/collection pages
interface ItemListItem {
  name: string;
  url: string;
  position: number;
  image?: string;
  description?: string;
}

interface ItemListProps {
  name: string;
  description: string;
  items: ItemListItem[];
  url: string;
}

export function ItemListJsonLd({ name, description, items, url }: ItemListProps) {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    description,
    url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
    numberOfItems: items.length,
    itemListElement: items.map((item) => ({
      '@type': 'ListItem',
      position: item.position,
      name: item.name,
      url: item.url.startsWith('http') ? item.url : `${BASE_URL}${item.url}`,
      ...(item.image && { image: item.image }),
      ...(item.description && { description: item.description }),
    })),
  };

  return (
    <Script
      id="item-list-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Organization schema for site-wide identity
export function OrganizationJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'TellyAds',
    url: BASE_URL,
    logo: `${BASE_URL}/logo.png`,
    description: 'The UK\'s largest archive of TV commercials. Discover, search, and explore decades of television advertising history.',
    foundingDate: '2020',
    sameAs: [
      // Add social media URLs when available
      // 'https://twitter.com/tellyads',
      // 'https://www.facebook.com/tellyads',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'customer support',
      url: `${BASE_URL}/about`,
    },
  };

  return (
    <Script
      id="organization-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// WebSite schema with SearchAction for sitelinks search box
export function WebSiteJsonLd() {
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'TellyAds',
    url: BASE_URL,
    description: 'The UK\'s largest archive of TV commercials',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${BASE_URL}/search?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };

  return (
    <Script
      id="website-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// Combined schema for ad detail pages
interface AdPageJsonLdProps {
  ad: {
    name: string;
    description: string;
    brandName: string;
    brandSlug: string;
    slug: string;
    thumbnailUrl?: string;
    year?: number;
    duration?: number;
    uploadDate?: string;
    productCategory?: string;
  };
}

export function AdPageJsonLd({ ad }: AdPageJsonLdProps) {
  const canonicalUrl = `${BASE_URL}/advert/${ad.brandSlug}/${ad.slug}`;

  const breadcrumbs: BreadcrumbItem[] = [
    { name: 'Home', url: '/' },
    { name: 'Archive', url: '/browse' },
    { name: ad.brandName, url: `/search?brand=${encodeURIComponent(ad.brandName)}` },
    { name: ad.name, url: canonicalUrl },
  ];

  return (
    <>
      <VideoObjectJsonLd
        name={ad.name}
        description={ad.description}
        thumbnailUrl={ad.thumbnailUrl}
        uploadDate={ad.uploadDate}
        duration={ad.duration}
        brandName={ad.brandName}
        year={ad.year}
        canonicalUrl={canonicalUrl}
      />
      <BreadcrumbListJsonLd items={breadcrumbs} />
    </>
  );
}
