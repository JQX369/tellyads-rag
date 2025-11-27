import { Metadata } from 'next';
import Link from 'next/link';

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

export const metadata: Metadata = {
    title: 'Browse TV Ads by Brand | TellyAds',
    description: 'Explore our complete index of television commercials organized by brand.',
};

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
        <div className="min-h-screen bg-slate-50">
             <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 py-4">
                    <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
                        TellyAds
                    </Link>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 py-12">
                <h1 className="text-3xl font-bold text-slate-900 mb-8">Browse Brands</h1>
                
                {sortedLetters.map(letter => (
                    <div key={letter} className="mb-8">
                        <h2 className="text-xl font-bold text-blue-600 border-b border-blue-100 pb-2 mb-4">{letter}</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-y-2 gap-x-4">
                            {grouped[letter].map(brand => (
                                <Link 
                                    key={brand} 
                                    href={`/search?q=${encodeURIComponent(brand)}`}
                                    className="text-slate-600 hover:text-blue-600 hover:underline text-sm truncate"
                                >
                                    {brand}
                                </Link>
                            ))}
                        </div>
                    </div>
                ))}
            </main>
        </div>
    );
}

