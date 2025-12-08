import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Header, Footer } from "@/components/layout";
import { Badge } from "@/components/ui";
import { constructMetadata } from "@/lib/seo";

export const metadata: Metadata = constructMetadata({
  title: "Latest Ads | TellyAds",
  description:
    "Discover the most recently added TV commercials to the TellyAds archive. Fresh content updated regularly.",
  path: "/latest",
});

interface Ad {
  id: string;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  year?: number;
  image_url?: string;
  one_line_summary?: string;
  product_category?: string;
  created_at?: string;
}

async function getLatestAds(): Promise<Ad[]> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/recent?limit=24`, {
      next: { revalidate: 300 }, // Revalidate every 5 minutes
    });

    if (!response.ok) return [];

    const data = await response.json();
    return data.ads || data || [];
  } catch (error) {
    console.error("Failed to fetch latest ads:", error);
    return [];
  }
}

export default async function LatestPage() {
  const ads = await getLatestAds();

  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Page header */}
          <div className="text-center mb-16">
            <span className="inline-flex items-center gap-3 mb-4">
              <span className="w-8 h-px bg-transmission" />
              <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
                Fresh Content
              </span>
              <span className="w-8 h-px bg-transmission" />
            </span>

            <h1 className="font-display text-display-md md:text-display-lg font-bold text-signal mb-4">
              Latest Ads
            </h1>

            <p className="font-mono text-antenna max-w-lg mx-auto">
              The most recently added commercials to our archive. Updated
              regularly with new discoveries.
            </p>
          </div>

          {/* Ads grid */}
          {ads.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {ads.map((ad, index) => (
                <LatestAdCard key={ad.external_id} ad={ad} index={index} />
              ))}
            </div>
          ) : (
            <div className="text-center py-24">
              <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-static flex items-center justify-center">
                <svg
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="text-antenna"
                >
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              </div>
              <h3 className="font-display text-xl font-semibold text-signal mb-2">
                No ads available
              </h3>
              <p className="font-mono text-antenna mb-6">
                Check back soon for new additions to the archive.
              </p>
              <Link
                href="/browse"
                className="inline-flex items-center justify-center px-6 py-3 font-mono uppercase tracking-ultra-wide text-sm bg-transmission text-signal rounded-pill hover:bg-transmission-dark transition-colors"
              >
                Browse All Ads
              </Link>
            </div>
          )}

          {/* Load more / Browse all */}
          {ads.length > 0 && (
            <div className="text-center mt-12">
              <Link
                href="/browse"
                className="inline-flex items-center gap-2 font-mono text-sm text-antenna hover:text-transmission transition-colors group"
              >
                <span>View all ads in archive</span>
                <span className="group-hover:translate-x-1 transition-transform">
                  →
                </span>
              </Link>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </>
  );
}

function LatestAdCard({ ad, index }: { ad: Ad; index: number }) {
  // Format the date if available
  const formattedDate = ad.created_at
    ? new Date(ad.created_at).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
      })
    : null;

  return (
    <Link href={`/ads/${ad.external_id}`}>
      <article className="group relative bg-static/30 border border-white/5 rounded-xl overflow-hidden transition-all duration-300 hover:border-white/10 hover:-translate-y-2 hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.5)]">
        {/* New badge for first few items */}
        {index < 4 && (
          <div className="absolute top-3 left-3 z-10">
            <Badge variant="transmission" size="sm">
              New
            </Badge>
          </div>
        )}

        {/* Image */}
        <div className="relative aspect-video overflow-hidden bg-static">
          {ad.image_url ? (
            <Image
              src={ad.image_url}
              alt={`${ad.brand_name} advertisement`}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-transmission/10 to-void">
              <span className="font-display text-5xl font-bold text-signal/20">
                {ad.brand_name?.charAt(0) || "?"}
              </span>
            </div>
          )}

          {/* Year badge */}
          {ad.year && (
            <div className="absolute top-3 right-3">
              <span className="font-mono text-xs bg-void/80 text-signal px-2 py-1 rounded-sm backdrop-blur-sm">
                {ad.year}
              </span>
            </div>
          )}

          {/* Play overlay */}
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-void/40">
            <div className="w-12 h-12 rounded-full bg-transmission/90 flex items-center justify-center">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="white"
                className="ml-0.5"
              >
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </div>
          </div>

          {/* Scanlines */}
          <div className="absolute inset-0 scanlines opacity-10 pointer-events-none" />
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-[10px] uppercase tracking-ultra-wide text-transmission">
              {ad.brand_name}
            </span>
            {formattedDate && (
              <span className="font-mono text-[10px] text-antenna">
                {formattedDate}
              </span>
            )}
          </div>

          <h3 className="font-display text-base font-semibold text-signal line-clamp-1 group-hover:text-transmission transition-colors">
            {ad.product_name || ad.brand_name}
          </h3>

          {ad.one_line_summary && (
            <p className="font-mono text-xs text-antenna mt-2 line-clamp-2 opacity-70 group-hover:opacity-100 transition-opacity">
              {ad.one_line_summary}
            </p>
          )}

          {ad.product_category && (
            <div className="mt-3">
              <span className="inline-block font-mono text-[9px] uppercase tracking-widest text-antenna bg-static/50 px-2 py-0.5 rounded-sm">
                {ad.product_category}
              </span>
            </div>
          )}
        </div>
      </article>
    </Link>
  );
}
