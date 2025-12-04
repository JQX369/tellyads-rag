import { Suspense } from "react";
import { Header, Footer } from "@/components/layout";
import { Hero, DecadeNav, CategoryShowcase, FeaturedAds } from "@/components/sections";

// Import db directly for server-side data fetching (no HTTP round-trip)
import { queryAll, queryOne, PUBLISH_GATE_CONDITION } from "@/lib/db";

// Fetch featured ads server-side (direct DB query)
async function getFeaturedAds() {
  try {
    const results = await queryAll(
      `
      SELECT
        a.id,
        a.external_id,
        a.brand_name,
        a.one_line_summary,
        a.thumbnail_url,
        a.video_url,
        a.year,
        a.duration_seconds,
        e.brand_slug,
        e.slug,
        e.headline,
        e.is_featured
      FROM ads a
      LEFT JOIN ad_editorial e ON e.ad_id = a.id AND ${PUBLISH_GATE_CONDITION}
      WHERE COALESCE((a.toxicity_scores->>'toxicity_score')::float, 0) <= 0.7
      ORDER BY a.created_at DESC
      LIMIT 6
      `
    );

    return results.map((row) => ({
      id: row.id,
      external_id: row.external_id,
      brand_name: row.brand_name,
      headline: row.headline || row.one_line_summary,
      thumbnail_url: row.thumbnail_url,
      video_url: row.video_url,
      year: row.year,
      duration_seconds: row.duration_seconds,
      brand_slug: row.brand_slug,
      slug: row.slug,
      is_featured: row.is_featured,
      canonical_url: row.brand_slug && row.slug
        ? `/advert/${row.brand_slug}/${row.slug}`
        : `/ads/${row.external_id}`,
    }));
  } catch (error) {
    console.error("Failed to fetch featured ads:", error);
    return [];
  }
}

// Get site stats (direct DB query)
async function getStats() {
  try {
    const counts = await queryOne(`
      SELECT
        COUNT(*) as total_ads,
        COUNT(DISTINCT brand_name) as total_brands
      FROM ads
    `);

    return {
      total_ads: parseInt(counts?.total_ads || "0", 10),
      total_brands: parseInt(counts?.total_brands || "0", 10),
    };
  } catch (error) {
    console.error("Failed to fetch stats:", error);
    return null;
  }
}

export default async function HomePage() {
  const [featuredAds, stats] = await Promise.all([
    getFeaturedAds(),
    getStats(),
  ]);

  return (
    <>
      <Header />

      <main className="min-h-screen">
        {/* Hero Section */}
        <Hero />

        {/* Featured Ads Carousel */}
        <Suspense fallback={<FeaturedAdsSkeleton />}>
          <FeaturedAds
            ads={featuredAds}
            title="Now Showing"
            subtitle="Featured"
          />
        </Suspense>

        {/* Decade Navigation */}
        <DecadeNav />

        {/* Category Showcase */}
        <CategoryShowcase />

        {/* Stats Section */}
        {stats && (
          <section className="py-24 bg-static/20">
            <div className="max-w-7xl mx-auto px-6 lg:px-12">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                <StatBlock
                  value={stats.total_ads?.toLocaleString() || "20,000+"}
                  label="Adverts"
                />
                <StatBlock value="20+" label="Years of History" />
                <StatBlock
                  value="2,000+"
                  label="Brands"
                />
                <StatBlock value="12" label="Categories" />
              </div>
            </div>
          </section>
        )}

        {/* CTA Section */}
        <section className="py-32 relative overflow-hidden">
          <div className="absolute inset-0 grid-lines opacity-20" />
          <div className="relative max-w-4xl mx-auto px-6 lg:px-12 text-center">
            <h2 className="font-display text-display-lg font-bold text-signal mb-6">
              Ready to Explore?
            </h2>
            <p className="font-mono text-lg text-antenna mb-10 max-w-xl mx-auto">
              Dive into decades of advertising history. Find inspiration,
              research competitors, or just enjoy the nostalgia.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="/browse"
                className="inline-flex items-center justify-center px-8 py-4 font-mono uppercase tracking-ultra-wide text-sm bg-transmission text-signal rounded-pill hover:bg-transmission-dark transition-colors"
              >
                Browse the Archive
              </a>
              <a
                href="/random"
                className="inline-flex items-center justify-center px-8 py-4 font-mono uppercase tracking-ultra-wide text-sm bg-transparent text-signal border-2 border-white/20 rounded-pill hover:border-transmission hover:text-transmission transition-colors"
              >
                Surprise Me
              </a>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}

function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="font-display text-4xl md:text-5xl font-bold text-signal">
        {value}
      </span>
      <span className="font-mono text-label uppercase tracking-ultra-wide text-antenna">
        {label}
      </span>
    </div>
  );
}

function FeaturedAdsSkeleton() {
  return (
    <section className="py-24">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="h-8 w-48 bg-static/50 rounded mb-12 animate-pulse" />
        <div className="flex gap-6 overflow-hidden">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="flex-shrink-0 w-[320px] md:w-[400px] aspect-[4/3] bg-static/30 rounded animate-pulse"
            />
          ))}
        </div>
      </div>
    </section>
  );
}
