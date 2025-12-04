import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import { queryOne, PUBLISH_GATE_CONDITION } from '@/lib/db';

interface PageProps {
  params: Promise<{ brand: string; slug: string }>;
}

interface AdData {
  id: string;
  external_id: string;
  brand_name: string;
  brand_slug: string;
  slug: string;
  headline?: string;
  summary?: string;
  extracted_summary?: string;
  one_line_summary?: string;
  year?: number;
  product_category?: string;
  product_name?: string;
  duration_seconds?: number;
  format_type?: string;
  video_url?: string;
  thumbnail_url?: string;
  hero_analysis?: any;
  impact_scores?: any;
  curated_tags?: string[];
  is_featured?: boolean;
  // Feedback data
  view_count?: number;
  like_count?: number;
  save_count?: number;
  ai_score?: number;
  user_score?: number;
  confidence_weight?: number;
  final_score?: number;
  reason_counts?: Record<string, number>;
  distinct_reason_sessions?: number;
  reason_threshold_met?: boolean;
}

async function getAd(brand: string, slug: string): Promise<AdData | null> {
  try {
    const row = await queryOne(
      `
      SELECT
        a.id,
        a.external_id,
        a.brand_name,
        a.product_name,
        a.product_category,
        a.one_line_summary,
        a.format_type,
        a.year,
        a.duration_seconds,
        a.s3_key,
        a.has_supers,
        a.has_price_claims,
        a.impact_scores,
        a.hero_analysis,
        a.created_at,
        e.brand_slug,
        e.slug,
        e.headline,
        e.editorial_summary,
        e.curated_tags,
        e.is_featured,
        e.seo_title,
        e.seo_description,
        e.legacy_url
      FROM ad_editorial e
      JOIN ads a ON a.id = e.ad_id
      WHERE e.brand_slug = $1
        AND e.slug = $2
        AND ${PUBLISH_GATE_CONDITION}
      `,
      [brand, slug]
    );

    if (!row) return null;

    return {
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      brand_slug: row.brand_slug,
      slug: row.slug,
      headline: row.headline || row.one_line_summary,
      summary: row.editorial_summary,
      extracted_summary: row.one_line_summary,
      one_line_summary: row.one_line_summary,
      product_name: row.product_name,
      product_category: row.product_category,
      format_type: row.format_type,
      year: row.year,
      duration_seconds: row.duration_seconds,
      // Note: video_url/thumbnail_url not stored in ads table, would need CSV lookup
      video_url: undefined,
      thumbnail_url: undefined,
      impact_scores: row.impact_scores,
      hero_analysis: row.hero_analysis,
      curated_tags: row.curated_tags || [],
      is_featured: row.is_featured || false,
      // Feedback aggregates not available (table doesn't exist)
      view_count: 0,
      like_count: 0,
      save_count: 0,
      ai_score: undefined,
      user_score: undefined,
      confidence_weight: undefined,
      final_score: undefined,
      reason_counts: undefined,
      distinct_reason_sessions: undefined,
      reason_threshold_met: false,
    };
  } catch (error) {
    console.error('Error fetching ad:', error);
    return null;
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { brand, slug } = await params;
  const ad = await getAd(brand, slug);

  if (!ad) {
    return {
      title: 'Ad Not Found | TellyAds',
      description: 'The requested advertisement could not be found.',
    };
  }

  const title = ad.headline || ad.one_line_summary || 'TV Commercial';
  const description = ad.summary || ad.extracted_summary || ad.one_line_summary || '';
  const brandName = ad.brand_name || brand;

  return {
    title: `${title} | ${brandName} | TellyAds`,
    description: description.slice(0, 160),
    alternates: {
      canonical: `https://tellyads.com/advert/${brand}/${slug}`,
    },
    openGraph: {
      title: `${title} | ${brandName}`,
      description,
      url: `https://tellyads.com/advert/${brand}/${slug}`,
      type: 'video.other',
      images: ad.thumbnail_url ? [{ url: ad.thumbnail_url }] : [],
      siteName: 'TellyAds',
    },
    twitter: {
      card: 'summary_large_image',
      title: `${title} | ${brandName}`,
      description: description.slice(0, 200),
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default async function AdvertPage({ params }: PageProps) {
  const { brand, slug } = await params;
  const ad = await getAd(brand, slug);

  if (!ad) {
    notFound();
  }

  const title = ad.headline || ad.one_line_summary || 'Untitled Ad';
  const description = ad.summary || ad.extracted_summary || '';

  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-950 to-black text-white">
      {/* Breadcrumb */}
      <nav className="container mx-auto px-4 py-4">
        <ol className="flex items-center gap-2 text-sm text-gray-400">
          <li>
            <Link href="/" className="hover:text-white transition-colors">
              Home
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link href="/search" className="hover:text-white transition-colors">
              Ads
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link
              href={`/search?brand=${encodeURIComponent(ad.brand_name)}`}
              className="hover:text-white transition-colors"
            >
              {ad.brand_name}
            </Link>
          </li>
          <li>/</li>
          <li className="text-white truncate max-w-[200px]">{title}</li>
        </ol>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2">
            {/* Video Player */}
            {ad.video_url && (
              <div className="aspect-video bg-black rounded-xl overflow-hidden mb-6">
                <video
                  src={ad.video_url}
                  controls
                  poster={ad.thumbnail_url}
                  className="w-full h-full object-contain"
                >
                  Your browser does not support the video tag.
                </video>
              </div>
            )}

            {/* Title & Meta */}
            <div className="mb-6">
              {ad.is_featured && (
                <span className="inline-block px-2 py-1 text-xs font-medium bg-yellow-500/20 text-yellow-400 rounded-full mb-2">
                  Featured
                </span>
              )}
              <h1 className="text-3xl font-bold mb-2">{title}</h1>
              <div className="flex flex-wrap items-center gap-4 text-gray-400 text-sm">
                <span className="font-medium text-white">{ad.brand_name}</span>
                {ad.year && <span>{ad.year}</span>}
                {ad.duration_seconds && (
                  <span>{Math.floor(ad.duration_seconds / 60)}:{String(ad.duration_seconds % 60).padStart(2, '0')}</span>
                )}
                {ad.product_category && <span>{ad.product_category}</span>}
              </div>
            </div>

            {/* Description */}
            {description && (
              <div className="prose prose-invert max-w-none mb-8">
                <p className="text-gray-300 leading-relaxed">{description}</p>
              </div>
            )}

            {/* Tags */}
            {ad.curated_tags && ad.curated_tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-8">
                {ad.curated_tags.map((tag) => (
                  <Link
                    key={tag}
                    href={`/search?tag=${encodeURIComponent(tag)}`}
                    className="px-3 py-1 text-sm bg-gray-800 hover:bg-gray-700 rounded-full transition-colors"
                  >
                    {tag}
                  </Link>
                ))}
              </div>
            )}

            {/* Impact Scores */}
            {ad.impact_scores && (
              <div className="bg-gray-900/50 rounded-xl p-6 border border-white/10 mb-8">
                <h3 className="text-lg font-semibold mb-4">Impact Analysis</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(ad.impact_scores).map(([key, value]) => (
                    <div key={key} className="text-center">
                      <div className="text-2xl font-bold text-green-400">
                        {typeof value === 'number' ? value.toFixed(0) : String(value ?? '')}
                      </div>
                      <div className="text-xs text-gray-500 capitalize">
                        {key.replace(/_/g, ' ')}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            {/* Feedback Panel (Client Component would go here) */}
            <div className="bg-gray-900/50 rounded-xl p-6 border border-white/10 mb-6">
              <h3 className="text-lg font-semibold mb-4">Community Feedback</h3>

              {/* Static display - real interaction needs client component */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Views</span>
                  <span className="font-medium">{ad.view_count || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Likes</span>
                  <span className="font-medium">{ad.like_count || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Saves</span>
                  <span className="font-medium">{ad.save_count || 0}</span>
                </div>

                {/* Scores */}
                <div className="pt-4 border-t border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-gray-400">Score</span>
                    <span className="text-lg font-bold text-green-400">
                      {ad.final_score?.toFixed(1) || ad.ai_score?.toFixed(1) || '—'}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    AI: {ad.ai_score?.toFixed(0) || 50} |
                    User: {ad.user_score?.toFixed(0) || 0} |
                    Weight: {((ad.confidence_weight || 0) * 100).toFixed(0)}%
                  </div>
                </div>

                {/* Reason counts (only if threshold met) */}
                {ad.reason_threshold_met && ad.reason_counts && Object.keys(ad.reason_counts).length > 0 && (
                  <div className="pt-4 border-t border-white/10">
                    <p className="text-sm text-gray-400 mb-2">Why people like this:</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(ad.reason_counts).map(([reason, count]) => (
                        <span
                          key={reason}
                          className="px-2 py-1 text-xs bg-gray-800 rounded-full"
                        >
                          {reason.replace(/_/g, ' ')} ({count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Placeholder for interactive buttons */}
              <div className="mt-6 pt-4 border-t border-white/10 text-center text-sm text-gray-500">
                <p>Like and save buttons coming soon</p>
              </div>
            </div>

            {/* Ad Info */}
            <div className="bg-gray-900/50 rounded-xl p-6 border border-white/10">
              <h3 className="text-lg font-semibold mb-4">Details</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-gray-500">External ID</dt>
                  <dd className="font-mono">{ad.external_id}</dd>
                </div>
                {ad.format_type && (
                  <div>
                    <dt className="text-gray-500">Format</dt>
                    <dd>{ad.format_type}</dd>
                  </div>
                )}
                {ad.product_name && (
                  <div>
                    <dt className="text-gray-500">Product</dt>
                    <dd>{ad.product_name}</dd>
                  </div>
                )}
              </dl>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
