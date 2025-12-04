"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { clsx } from "clsx";
import { Header, Footer } from "@/components/layout";
import { Badge } from "@/components/ui";

interface Ad {
  id: string;
  external_id: string;
  brand_name?: string;
  brand_slug?: string;
  slug?: string;
  product_name?: string;
  year?: number;
  image_url?: string;
  one_line_summary?: string;
  product_category?: string;
  duration_seconds?: number;
  canonical_url?: string;
}

const decades = ["1950s", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"];

const categories = [
  { id: "automotive", name: "Automotive" },
  { id: "fmcg", name: "FMCG" },
  { id: "finance", name: "Finance" },
  { id: "tech", name: "Technology" },
  { id: "retail", name: "Retail" },
  { id: "entertainment", name: "Entertainment" },
  { id: "telecom", name: "Telecom" },
  { id: "travel", name: "Travel" },
  { id: "pharma", name: "Pharma" },
  { id: "alcohol", name: "Alcohol" },
  { id: "charity", name: "Charity" },
  { id: "government", name: "Government" },
];

function BrowseContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(0);

  // Filter state from URL params
  const selectedDecade = searchParams.get("decade") || "";
  const selectedCategory = searchParams.get("category") || "";
  const selectedBrand = searchParams.get("brand") || "";

  // Sidebar state (mobile)
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch ads with filters
  const fetchAds = useCallback(
    async (pageNum: number, reset: boolean = false) => {
      setLoading(true);
      try {
        // Use relative URL to call Next.js API routes (works in both dev and production)
        const params = new URLSearchParams({
          limit: "24",
          offset: String(pageNum * 24),
        });

        if (selectedDecade) params.set("decade", selectedDecade);
        if (selectedCategory) params.set("category", selectedCategory);
        if (selectedBrand) params.set("brand", selectedBrand);

        const response = await fetch(`/api/recent?${params}`);
        if (!response.ok) throw new Error("Failed to fetch");

        const data = await response.json();
        const newAds = data.ads || data || [];

        if (reset) {
          setAds(newAds);
        } else {
          setAds((prev) => [...prev, ...newAds]);
        }

        setHasMore(newAds.length === 24);
      } catch (error) {
        console.error("Failed to fetch ads:", error);
      } finally {
        setLoading(false);
      }
    },
    [selectedDecade, selectedCategory, selectedBrand]
  );

  // Initial load and filter changes
  useEffect(() => {
    setPage(0);
    fetchAds(0, true);
  }, [fetchAds]);

  // Update URL params
  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    router.push(`/browse?${params.toString()}`);
  };

  // Clear all filters
  const clearFilters = () => {
    router.push("/browse");
  };

  // Load more
  const loadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchAds(nextPage);
  };

  // Active filters count
  const activeFiltersCount = [selectedDecade, selectedCategory, selectedBrand].filter(Boolean).length;

  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Page Header */}
          <div className="mb-12">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <span className="inline-flex items-center gap-3 mb-4">
                <span className="w-8 h-px bg-transmission" />
                <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
                  The Archive
                </span>
              </span>
              <h1 className="font-display text-display-lg font-bold text-signal">
                Browse Ads
              </h1>
            </motion.div>
          </div>

          <div className="flex gap-8">
            {/* Sidebar Filters */}
            <aside
              className={clsx(
                "fixed inset-y-0 left-0 z-40 w-72 bg-void border-r border-white/10 p-6 pt-24",
                "transform transition-transform duration-300 lg:relative lg:translate-x-0 lg:pt-0 lg:bg-transparent lg:border-0",
                sidebarOpen ? "translate-x-0" : "-translate-x-full"
              )}
            >
              {/* Mobile close button */}
              <button
                className="lg:hidden absolute top-6 right-6 text-antenna hover:text-signal"
                onClick={() => setSidebarOpen(false)}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>

              {/* Filters Header */}
              <div className="flex items-center justify-between mb-6">
                <h2 className="font-mono text-label uppercase tracking-ultra-wide text-signal">
                  Filters
                </h2>
                {activeFiltersCount > 0 && (
                  <button
                    onClick={clearFilters}
                    className="font-mono text-xs text-antenna hover:text-transmission transition-colors"
                  >
                    Clear all ({activeFiltersCount})
                  </button>
                )}
              </div>

              {/* Decade Filter */}
              <FilterSection title="Decade">
                <div className="flex flex-wrap gap-2">
                  {decades.map((decade) => (
                    <button
                      key={decade}
                      onClick={() => updateFilter("decade", selectedDecade === decade ? "" : decade)}
                      className={clsx(
                        "px-3 py-1.5 font-mono text-xs uppercase tracking-wide rounded-sm border transition-all",
                        selectedDecade === decade
                          ? "bg-transmission text-signal border-transmission"
                          : "bg-static/50 text-antenna border-white/10 hover:border-transmission/30 hover:text-signal"
                      )}
                    >
                      {decade}
                    </button>
                  ))}
                </div>
              </FilterSection>

              {/* Category Filter */}
              <FilterSection title="Category">
                <div className="flex flex-col gap-1">
                  {categories.map((category) => (
                    <button
                      key={category.id}
                      onClick={() =>
                        updateFilter("category", selectedCategory === category.id ? "" : category.id)
                      }
                      className={clsx(
                        "px-3 py-2 font-mono text-xs text-left rounded-sm transition-all",
                        selectedCategory === category.id
                          ? "bg-transmission/10 text-transmission"
                          : "text-antenna hover:bg-static/50 hover:text-signal"
                      )}
                    >
                      {category.name}
                    </button>
                  ))}
                </div>
              </FilterSection>
            </aside>

            {/* Backdrop for mobile sidebar */}
            <AnimatePresence>
              {sidebarOpen && (
                <motion.div
                  className="fixed inset-0 bg-void/80 backdrop-blur-sm z-30 lg:hidden"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  onClick={() => setSidebarOpen(false)}
                />
              )}
            </AnimatePresence>

            {/* Main Content */}
            <div className="flex-1">
              {/* Mobile filter toggle + Active filters */}
              <div className="flex items-center gap-4 mb-6">
                <button
                  className="lg:hidden flex items-center gap-2 px-4 py-2 bg-static/50 border border-white/10 rounded text-sm font-mono text-signal"
                  onClick={() => setSidebarOpen(true)}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="4" y1="6" x2="20" y2="6" />
                    <line x1="4" y1="12" x2="14" y2="12" />
                    <line x1="4" y1="18" x2="9" y2="18" />
                  </svg>
                  Filters
                  {activeFiltersCount > 0 && (
                    <span className="ml-1 w-5 h-5 flex items-center justify-center bg-transmission rounded-full text-xs">
                      {activeFiltersCount}
                    </span>
                  )}
                </button>

                {/* Active filter chips */}
                {selectedDecade && (
                  <Badge variant="transmission" className="cursor-pointer" onClick={() => updateFilter("decade", "")}>
                    {selectedDecade} ×
                  </Badge>
                )}
                {selectedCategory && (
                  <Badge variant="transmission" className="cursor-pointer" onClick={() => updateFilter("category", "")}>
                    {categories.find((c) => c.id === selectedCategory)?.name} ×
                  </Badge>
                )}
              </div>

              {/* Results Grid */}
              {loading && ads.length === 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {[...Array(12)].map((_, i) => (
                    <div key={i} className="aspect-[4/3] bg-static/30 rounded animate-pulse" />
                  ))}
                </div>
              ) : ads.length === 0 ? (
                <div className="text-center py-24">
                  <p className="font-mono text-lg text-antenna mb-4">No ads found</p>
                  <button
                    onClick={clearFilters}
                    className="font-mono text-sm text-transmission hover:underline"
                  >
                    Clear filters and try again
                  </button>
                </div>
              ) : (
                <>
                  <motion.div
                    className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
                    initial="hidden"
                    animate="visible"
                    variants={{
                      hidden: { opacity: 0 },
                      visible: {
                        opacity: 1,
                        transition: { staggerChildren: 0.05 },
                      },
                    }}
                  >
                    {ads.map((ad) => (
                      <motion.div
                        key={ad.external_id}
                        variants={{
                          hidden: { opacity: 0, y: 20 },
                          visible: { opacity: 1, y: 0 },
                        }}
                      >
                        <AdCard ad={ad} />
                      </motion.div>
                    ))}
                  </motion.div>

                  {/* Load More */}
                  {hasMore && (
                    <div className="mt-12 text-center">
                      <button
                        onClick={loadMore}
                        disabled={loading}
                        className={clsx(
                          "px-8 py-3 font-mono uppercase tracking-ultra-wide text-sm",
                          "bg-static/50 text-signal border border-white/10 rounded-pill",
                          "hover:bg-static hover:border-white/20 transition-all",
                          "disabled:opacity-50 disabled:cursor-not-allowed"
                        )}
                      >
                        {loading ? "Loading..." : "Load More"}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </>
  );
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h3 className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mb-3">{title}</h3>
      {children}
    </div>
  );
}

function AdCard({ ad }: { ad: Ad }) {
  // Use canonical URL format: /advert/{brand}/{slug} if available, otherwise /ads/{external_id}
  const adUrl = ad.canonical_url || `/ads/${ad.external_id}`;

  return (
    <Link href={adUrl}>
      <article
        className={clsx(
          "group relative",
          "bg-static/30 backdrop-blur-sm",
          "border border-white/5 rounded overflow-hidden",
          "transition-all duration-300 ease-expo-out",
          "hover:border-white/10 hover:-translate-y-1",
          "hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.5)]"
        )}
      >
        {/* Image */}
        <div className="relative aspect-video overflow-hidden">
          <div className="absolute inset-0 bg-static" />
          {ad.image_url ? (
            <Image
              src={ad.image_url}
              alt={`${ad.brand_name} advertisement`}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-display text-4xl font-bold text-antenna/30">
                {ad.brand_name?.charAt(0) || "?"}
              </span>
            </div>
          )}

          {/* Year badge */}
          {ad.year && (
            <div className="absolute top-3 right-3">
              <Badge variant="default" size="sm">
                {ad.year}
              </Badge>
            </div>
          )}

          {/* Play overlay */}
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-void/40">
            <div className="w-12 h-12 rounded-full bg-transmission/90 flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="white" className="ml-0.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <span className="font-mono text-[10px] uppercase tracking-ultra-wide text-transmission">
            {ad.brand_name}
          </span>
          <h3 className="font-display text-base font-semibold text-signal mt-1 line-clamp-1">
            {ad.product_name || ad.brand_name}
          </h3>
          {ad.one_line_summary && (
            <p className="font-mono text-xs text-antenna mt-2 line-clamp-2">
              {ad.one_line_summary}
            </p>
          )}
        </div>
      </article>
    </Link>
  );
}

export default function BrowsePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="starburst" />
        </div>
      }
    >
      <BrowseContent />
    </Suspense>
  );
}
