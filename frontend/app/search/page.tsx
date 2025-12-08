import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { SearchResult } from "@/lib/types";
import { constructMetadata } from "@/lib/seo";
import { Header, Footer } from "@/components/layout";
import { Badge } from "@/components/ui";
import { SearchInput } from "@/components/SearchInput";

// Force dynamic rendering as search results depend on query params
export const dynamic = "force-dynamic";

interface SearchPageProps {
  searchParams: Promise<{ q?: string; page?: string }>;
}

export async function generateMetadata({
  searchParams,
}: SearchPageProps): Promise<Metadata> {
  const params = await searchParams;
  const query = params.q;

  // Base search page (no query) should be indexed with canonical
  // Search results (with query) should NOT be indexed (duplicative content)
  if (!query) {
    return constructMetadata({
      title: "Search TV Commercials",
      description: "Search the TellyAds archive of thousands of TV commercials by concept, emotion, visual content, or brand.",
      path: "/search",
      noIndex: false,
    });
  }

  // Search results pages - noindex but still follow links
  return constructMetadata({
    title: `Search: "${query}"`,
    description: `Search results for "${query}" in the TellyAds archive.`,
    noIndex: true,
  });
}

async function getSearchResults(query: string): Promise<SearchResult[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/search`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit: 50 }),
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return [];
    }

    return res.json();
  } catch {
    return [];
  }
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const query = params.q || "";
  const results = query ? await getSearchResults(query) : [];

  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Search header */}
          <div className="max-w-2xl mx-auto mb-16">
            <div className="text-center mb-8">
              <span className="inline-flex items-center gap-3 mb-4">
                <span className="w-8 h-px bg-transmission" />
                <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
                  Semantic Search
                </span>
                <span className="w-8 h-px bg-transmission" />
              </span>
              <h1 className="font-display text-display-md font-bold text-signal">
                Search the Archive
              </h1>
              <p className="font-mono text-antenna mt-4">
                Find commercials by concept, emotion, visual content, or brand
              </p>
            </div>

            {/* Search input */}
            <SearchInput initialQuery={query} />
          </div>

          {/* Results */}
          {query ? (
            <div>
              {/* Results header */}
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h2 className="font-display text-xl font-semibold text-signal">
                    Results for &ldquo;{query}&rdquo;
                  </h2>
                  <p className="font-mono text-sm text-antenna mt-1">
                    Found {results.length} commercials
                  </p>
                </div>

                {results.length > 0 && (
                  <Link
                    href="/browse"
                    className="font-mono text-sm text-antenna hover:text-signal transition-colors"
                  >
                    Browse all instead →
                  </Link>
                )}
              </div>

              {/* Results grid */}
              {results.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {results.map((result) => (
                    <SearchResultCard key={result.id} result={result} />
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
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  </div>
                  <h3 className="font-display text-xl font-semibold text-signal mb-2">
                    No results found
                  </h3>
                  <p className="font-mono text-antenna mb-6">
                    Try different keywords or browse the archive
                  </p>
                  <Link
                    href="/browse"
                    className="inline-flex items-center justify-center px-6 py-3 font-mono uppercase tracking-ultra-wide text-sm bg-transmission text-signal rounded-pill hover:bg-transmission-dark transition-colors"
                  >
                    Browse Archive
                  </Link>
                </div>
              )}
            </div>
          ) : (
            // Empty state - no query yet
            <div className="text-center py-16">
              <p className="font-mono text-antenna mb-8">
                Enter a search query above to find commercials
              </p>

              {/* Example searches */}
              <div className="max-w-xl mx-auto">
                <p className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
                  Try searching for
                </p>
                <div className="flex flex-wrap justify-center gap-3">
                  {[
                    "nostalgic 90s ads",
                    "car commercials with road trips",
                    "funny beer ads",
                    "emotional christmas ads",
                    "tech product launches",
                  ].map((example) => (
                    <Link
                      key={example}
                      href={`/search?q=${encodeURIComponent(example)}`}
                      className="px-4 py-2 font-mono text-sm text-antenna bg-static/50 border border-white/10 rounded-pill hover:border-transmission/30 hover:text-signal transition-colors"
                    >
                      {example}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </>
  );
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <Link href={`/ads/${result.external_id}`}>
      <article className="group relative bg-static/30 border border-white/5 rounded overflow-hidden transition-all duration-300 hover:border-white/10 hover:-translate-y-1 hover:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.5)]">
        {/* Image */}
        <div className="relative aspect-video overflow-hidden bg-static">
          {result.image_url ? (
            <Image
              src={result.image_url}
              alt={`${result.brand_name} advertisement`}
              fill
              className="object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-display text-4xl font-bold text-antenna/30">
                {result.brand_name?.charAt(0) || "?"}
              </span>
            </div>
          )}

          {/* Score badge */}
          {result.score !== undefined && (
            <div className="absolute top-3 right-3">
              <Badge variant="transmission" size="sm">
                {Math.round(result.score * 100)}% match
              </Badge>
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
        </div>

        {/* Content */}
        <div className="p-4">
          <span className="font-mono text-[10px] uppercase tracking-ultra-wide text-transmission">
            {result.brand_name}
          </span>
          <h3 className="font-display text-base font-semibold text-signal mt-1 line-clamp-1">
            {result.product_name || result.brand_name}
          </h3>
          {(result.description || result.text) && (
            <p className="font-mono text-xs text-antenna mt-2 line-clamp-2">
              {result.description || result.text}
            </p>
          )}
        </div>
      </article>
    </Link>
  );
}
