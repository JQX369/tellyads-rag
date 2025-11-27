import { Metadata } from 'next';
import AdGrid from '@/components/AdGrid';
import SearchBar from '@/components/SearchBar';
import { SearchResult } from '@/lib/types';
import { constructMetadata } from '@/lib/seo';
import Link from 'next/link';

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
    <div className="min-h-screen bg-background flex flex-col">
        <header className="bg-black/20 backdrop-blur-xl border-b border-white/5 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 py-4 flex items-center gap-6">
                <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 shrink-0 hover:opacity-80 transition-opacity">
                    TellyAds
                </Link>
                <div className="flex-grow max-w-xl">
                   <SearchBar />
                </div>
            </div>
        </header>

        <main className="flex-grow w-full max-w-7xl mx-auto px-4 py-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white tracking-tight">
                    {query ? `Results for "${query}"` : 'Search Ads'}
                </h1>
                <p className="text-muted-foreground mt-2">
                    Found {results.length} commercials matching your query
                </p>
            </div>

            <AdGrid ads={results} />
        </main>
    </div>
  );
}
