import SearchBar from '@/components/SearchBar';
import { defaultMetadata } from '@/lib/seo';
import Link from 'next/link';

export const metadata = defaultMetadata;

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Navigation */}
      <nav className="p-6 flex justify-between items-center max-w-7xl mx-auto">
        <div className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
          TellyAds
        </div>
        <div className="space-x-6 text-gray-600">
          <Link href="/about" className="hover:text-blue-600 transition-colors">About</Link>
          <Link href="/how-it-works" className="hover:text-blue-600 transition-colors">How it Works</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="flex flex-col items-center justify-center px-4 pt-20 pb-32 text-center">
        <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 mb-6 tracking-tight">
          The World's Largest <br />
          <span className="text-blue-600">TV Ad Archive</span>
        </h1>
        <p className="text-xl md:text-2xl text-slate-600 mb-12 max-w-2xl leading-relaxed">
          Search thousands of commercials by concept, emotion, or content. 
          Powered by advanced semantic AI.
        </p>
        
        <SearchBar />

        {/* Example Tags */}
        <div className="mt-12 flex flex-wrap justify-center gap-3 text-sm text-slate-500">
          <span className="px-4 py-2 bg-white border border-slate-200 rounded-full hover:border-blue-300 cursor-pointer transition-colors">
            🚗 Car commercials with road trips
          </span>
          <span className="px-4 py-2 bg-white border border-slate-200 rounded-full hover:border-blue-300 cursor-pointer transition-colors">
            🥺 Nostalgic 90s ads
          </span>
          <span className="px-4 py-2 bg-white border border-slate-200 rounded-full hover:border-blue-300 cursor-pointer transition-colors">
            🍫 Chocolate ads with humor
          </span>
        </div>
      </div>

      {/* Stats/Social Proof (Static Placeholder for MVP) */}
      <div className="border-t border-slate-100 bg-white">
        <div className="max-w-7xl mx-auto px-6 py-16 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-4xl font-bold text-slate-900 mb-2">20,000+</div>
            <div className="text-slate-500">Commercials Indexed</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-slate-900 mb-2">1,500+</div>
            <div className="text-slate-500">Brands Tracked</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-slate-900 mb-2">Daily</div>
            <div className="text-slate-500">Updates & Analysis</div>
          </div>
        </div>
      </div>
    </main>
  );
}

