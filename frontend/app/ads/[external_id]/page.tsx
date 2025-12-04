import { Metadata } from "next";
import { AdDetail } from "@/lib/types";
import { constructMetadata } from "@/lib/seo";
import Link from "next/link";
import Image from "next/image";
import { Header, Footer } from "@/components/layout";
import { Badge } from "@/components/ui";
import { VideoPlayer } from "@/components/VideoPlayer";
import { MetricsDisplay } from "@/components/MetricsDisplay";
import { SimilarAds } from "@/components/SimilarAds";

// Force dynamic rendering for fresh data
export const dynamic = "force-dynamic";

interface AdPageProps {
  params: Promise<{ external_id: string }>;
}

async function getAdDetail(external_id: string): Promise<AdDetail> {
  // Use internal API route - construct absolute URL for server-side fetch
  const baseUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

  const res = await fetch(
    `${baseUrl}/api/ads/${external_id}`,
    {
      cache: "no-store",
    }
  );

  if (!res.ok) {
    throw new Error("Ad not found");
  }

  return res.json();
}

async function getSimilarAds(external_id: string): Promise<any[]> {
  try {
    // Use internal API route
    const baseUrl = process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

    const res = await fetch(
      `${baseUrl}/api/ads/${external_id}/similar?limit=5`,
      {
        next: { revalidate: 3600 },
      }
    );
    return res.ok ? res.json() : [];
  } catch {
    return [];
  }
}

export async function generateMetadata({ params }: AdPageProps): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const ad = await getAdDetail(resolvedParams.external_id);
    const title = `${ad.brand_name || "TV Ad"} - ${ad.product_name || "Commercial"}`;
    const description =
      ad.description ||
      `Watch this ${ad.year || ""} commercial for ${ad.brand_name}. Part of the TellyAds archive.`;

    return constructMetadata({
      title,
      description,
      image: ad.image_url,
    });
  } catch {
    return constructMetadata({ title: "Ad Not Found" });
  }
}

export default async function AdPage({ params }: AdPageProps) {
  let ad: AdDetail;
  let similarAds: any[] = [];

  try {
    const resolvedParams = await params;
    [ad, similarAds] = await Promise.all([
      getAdDetail(resolvedParams.external_id),
      getSimilarAds(resolvedParams.external_id),
    ]);
  } catch {
    return (
      <>
        <Header />
        <main className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <h1 className="font-display text-6xl font-bold text-signal mb-4">404</h1>
            <p className="font-mono text-lg text-antenna mb-8">Ad not found or removed.</p>
            <Link
              href="/browse"
              className="font-mono text-sm text-transmission hover:underline"
            >
              Return to Archive
            </Link>
          </div>
        </main>
        <Footer />
      </>
    );
  }

  // Extract only the 4 key metrics we want to display
  const displayMetrics = extractDisplayMetrics(ad.impact_scores);

  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Breadcrumb */}
          <nav className="mb-8">
            <ol className="flex items-center gap-2 font-mono text-sm text-antenna">
              <li>
                <Link href="/" className="hover:text-signal transition-colors">
                  Home
                </Link>
              </li>
              <li>/</li>
              <li>
                <Link href="/browse" className="hover:text-signal transition-colors">
                  Archive
                </Link>
              </li>
              <li>/</li>
              <li className="text-signal">{ad.brand_name}</li>
            </ol>
          </nav>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
            {/* Main Content */}
            <div className="lg:col-span-2 space-y-8">
              {/* Video Player with Anti-Scraping Protection */}
              <VideoPlayer
                videoUrl={ad.video_url}
                posterUrl={ad.image_url}
                adId={ad.external_id}
              />

              {/* Title & Core Info */}
              <div>
                {/* Brand Label */}
                <div className="flex items-center gap-3 mb-3">
                  <span className="w-8 h-px bg-transmission" />
                  <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
                    {ad.brand_name}
                  </span>
                </div>

                {/* Title */}
                <h1 className="font-display text-display-md font-bold text-signal mb-4">
                  {ad.product_name || ad.brand_name}
                </h1>

                {/* Meta chips */}
                <div className="flex flex-wrap gap-3 mb-6">
                  {ad.year && <Badge variant="default">{ad.year}</Badge>}
                  {ad.duration_seconds && (
                    <Badge variant="default">{Math.round(ad.duration_seconds)}s</Badge>
                  )}
                  {ad.product_category && (
                    <Badge variant="muted">{formatCategory(ad.product_category)}</Badge>
                  )}
                </div>

                {/* Description */}
                {ad.description && (
                  <p className="font-mono text-base text-antenna leading-relaxed max-w-2xl">
                    {ad.description}
                  </p>
                )}
              </div>

              {/* Metrics Display - Only 4 Key Metrics */}
              {displayMetrics.length > 0 && (
                <MetricsDisplay metrics={displayMetrics} />
              )}

              {/* Additional metadata - Minimal */}
              <div className="border-t border-white/10 pt-8">
                <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
                  Details
                </h2>
                <dl className="grid grid-cols-2 md:grid-cols-4 gap-6">
                  {ad.brand_name && (
                    <MetaItem label="Brand" value={ad.brand_name} />
                  )}
                  {ad.year && <MetaItem label="Year" value={String(ad.year)} />}
                  {ad.duration_seconds && (
                    <MetaItem
                      label="Duration"
                      value={formatDuration(ad.duration_seconds)}
                    />
                  )}
                  {ad.product_category && (
                    <MetaItem
                      label="Category"
                      value={formatCategory(ad.product_category)}
                    />
                  )}
                </dl>
              </div>
            </div>

            {/* Sidebar */}
            <aside className="lg:col-span-1 space-y-8">
              {/* Similar Ads */}
              <SimilarAds ads={similarAds} />

              {/* Share/Actions */}
              <div className="p-4 bg-static/30 rounded border border-white/5">
                <h3 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
                  Actions
                </h3>
                <div className="flex flex-col gap-2">
                  <button
                    className="w-full px-4 py-2 font-mono text-sm text-signal bg-static/50 border border-white/10 rounded hover:bg-static transition-colors"
                    onClick={() => {
                      if (typeof navigator !== "undefined") {
                        navigator.clipboard.writeText(window.location.href);
                      }
                    }}
                  >
                    Copy Link
                  </button>
                  <Link
                    href="/browse"
                    className="w-full px-4 py-2 font-mono text-sm text-center text-antenna hover:text-signal border border-white/5 rounded transition-colors"
                  >
                    Back to Archive
                  </Link>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </main>

      <Footer />
    </>
  );
}

// Extract only the 4 metrics we want to display publicly
function extractDisplayMetrics(impactScores: any): Array<{
  key: string;
  label: string;
  value: number;
  description: string;
}> {
  if (!impactScores) return [];

  const metricsToShow = [
    {
      key: "hook_power",
      label: "Hook Power",
      description: "Does it grab you?",
    },
    {
      key: "emotional_resonance",
      label: "Emotional Resonance",
      description: "Does it move you?",
    },
    {
      key: "brand_integration",
      label: "Brand Integration",
      description: "Do you remember who?",
    },
    {
      key: "distinctiveness",
      label: "Distinctiveness",
      description: "Is it unique?",
    },
  ];

  return metricsToShow
    .map((metric) => {
      const data = impactScores[metric.key];
      if (data && typeof data === "object" && typeof data.score === "number") {
        return {
          key: metric.key,
          label: metric.label,
          value: data.score,
          description: metric.description,
        };
      }
      return null;
    })
    .filter(Boolean) as Array<{
    key: string;
    label: string;
    value: number;
    description: string;
  }>;
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mb-1">
        {label}
      </dt>
      <dd className="font-display text-lg text-signal">{value}</dd>
    </div>
  );
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
}

function formatCategory(category: string): string {
  return category
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}
