import { Metadata } from 'next';
import AdGrid from '@/components/AdGrid';
import SearchBar from '@/components/SearchBar';
import { SearchResult } from '@/lib/types';
import { constructMetadata } from '@/lib/seo';

// Force dynamic rendering as search results depend on query params
export const dynamic = 'force-dynamic';

interface SearchPageProps {
  searchParams: { q?: string; page?: string };
}

export async function generateMetadata({ searchParams }: SearchPageProps): Promise<Metadata> {
  const query = searchParams.q || 'All Ads';
  return constructMetadata({
    title: `Search results for "${query}" - TellyAds`,
    description: `Browse semantic search results for "${query}" in the TellyAds archive.`,
    noIndex: true, // Often good practice to noindex internal search results
  });
}

async function getSearchResults(query: string): Promise<SearchResult[]> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit: 50 }),
    cache: 'no-store',
  });
  
  if (!res.ok) {
    throw new Error('Failed to fetch results');
  }
  
  return res.json();
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const query = searchParams.q || '';
  const results = query ? await getSearchResults(query) : [];

  return (
    <div className="min-h-screen bg-slate-50">
        <header className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-10">
            <div className="max-w-7xl mx-auto px-4 py-4 flex items-center gap-6">
                <a href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600 shrink-0">
                    TellyAds
                </a>
                <div className="flex-grow max-w-xl">
                    {/* Compact Search Bar Implementation inline or reused component with styling overrides? */}
                    {/* Reusing existing component but it has fixed styling. Might be better to make it adaptable or just use as is for now. */}
                    {/* For MVP let's re-render simple input or adjust SearchBar component to accept className. */}
                    {/* Just re-using the search bar component for now, it centers itself but that's okay. */}
                   <SearchBar />
                </div>
            </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-8">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-800">
                    {query ? `Results for "${query}"` : 'Search Ads'}
                </h1>
                <p className="text-slate-500">
                    {results.length} commercials found
                </p>
            </div>

            <AdGrid ads={results} />
        </main>
    </div>
  );
}





