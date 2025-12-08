import { Metadata } from 'next';
import Link from 'next/link';
import { constructMetadata } from '@/lib/seo';
import { Header, Footer } from '@/components/layout';

// Revalidate brand list daily
export const revalidate = 86400;

async function getBrands(): Promise<string[]> {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/brands`);
    return res.ok ? res.json() : [];
  } catch {
    return [];
  }
}

export const metadata: Metadata = constructMetadata({
  title: 'Browse TV Ads by Brand | TellyAds',
  description: 'Explore our complete index of television commercials organized by brand.',
  path: '/brands',
});

export default async function BrandsIndex() {
  const brands = await getBrands();

  // Group by first letter
  const grouped = brands.reduce((acc, brand) => {
    const letter = brand.charAt(0).toUpperCase();
    if (!acc[letter]) acc[letter] = [];
    acc[letter].push(brand);
    return acc;
  }, {} as Record<string, string[]>);

  const sortedLetters = Object.keys(grouped).sort();

  return (
    <>
      <Header />

      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Page Header */}
          <div className="mb-12">
            <span className="inline-flex items-center gap-3 mb-4">
              <span className="w-8 h-px bg-transmission" />
              <span className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
                Directory
              </span>
            </span>
            <h1 className="font-display text-display-lg font-bold text-signal">
              Browse Brands
            </h1>
            <p className="font-mono text-antenna mt-4 max-w-xl">
              Explore our complete index of television commercials organized by brand.
            </p>
          </div>

          {/* Letter Navigation */}
          <nav className="mb-12 flex flex-wrap gap-2">
            {sortedLetters.map(letter => (
              <a
                key={letter}
                href={`#${letter}`}
                className="w-10 h-10 flex items-center justify-center font-mono text-sm bg-static/50 border border-white/10 rounded hover:border-transmission/50 hover:text-transmission transition-colors text-antenna"
              >
                {letter}
              </a>
            ))}
          </nav>

          {/* Brand Sections */}
          {sortedLetters.map(letter => (
            <section key={letter} id={letter} className="mb-12 scroll-mt-28">
              <h2 className="font-display text-2xl font-bold text-transmission border-b border-white/10 pb-3 mb-6">
                {letter}
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-y-3 gap-x-6">
                {grouped[letter].map(brand => (
                  <Link
                    key={brand}
                    href={`/search?q=${encodeURIComponent(brand)}`}
                    className="font-mono text-sm text-antenna hover:text-signal hover:underline transition-colors truncate"
                  >
                    {brand}
                  </Link>
                ))}
              </div>
            </section>
          ))}

          {/* Empty State */}
          {sortedLetters.length === 0 && (
            <div className="text-center py-24">
              <p className="font-mono text-lg text-antenna mb-4">No brands found</p>
              <Link
                href="/browse"
                className="font-mono text-sm text-transmission hover:underline"
              >
                Browse all ads instead
              </Link>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </>
  );
}
