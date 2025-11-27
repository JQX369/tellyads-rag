import SearchBar from '@/components/SearchBar';
import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex flex-col min-h-screen relative overflow-hidden">
      
      {/* Background Gradient Mesh (Decorative) */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-blue-500/20 rounded-full blur-[120px] -z-10 pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-0 right-0 w-[800px] h-[600px] bg-purple-500/10 rounded-full blur-[120px] -z-10 pointer-events-none mix-blend-screen" />

      {/* Navigation */}
      <nav className="w-full max-w-7xl mx-auto px-6 py-6 flex justify-between items-center z-50">
        <div className="text-2xl font-bold tracking-tighter bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60">
          TellyAds
        </div>
        <div className="space-x-8 text-sm font-medium text-muted-foreground">
          <Link href="/about" className="hover:text-white transition-colors duration-300">About</Link>
          <Link href="/how-it-works" className="hover:text-white transition-colors duration-300">How it Works</Link>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 relative z-10">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-blue-200 animate-fade-in">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            Now Indexing 20,000+ Commercials
          </div>

          <h1 className="text-6xl md:text-8xl font-extrabold tracking-tight text-white leading-[1.1] animate-slide-up">
            Search TV Ads with <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400">
              Semantic Intelligence
            </span>
          </h1>
          
          <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl mx-auto leading-relaxed animate-slide-up" style={{ animationDelay: '0.1s' }}>
            Find commercials by concept, emotion, or visual content. 
            The world's most advanced advertising search engine.
          </p>
          
          <div className="w-full max-w-2xl mx-auto pt-8 animate-slide-up" style={{ animationDelay: '0.2s' }}>
            <SearchBar />
          </div>

          {/* Example Tags */}
          <div className="pt-10 flex flex-wrap justify-center gap-3 animate-slide-up" style={{ animationDelay: '0.3s' }}>
            {[
              "🚗 Car commercials with road trips",
              "🥺 Nostalgic 90s ads",
              "🍫 Chocolate ads with humor"
            ].map((tag) => (
              <button 
                key={tag}
                className="px-4 py-2 bg-white/5 border border-white/10 rounded-full text-sm text-muted-foreground hover:text-white hover:bg-white/10 hover:border-white/20 transition-all duration-300 cursor-pointer"
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Stats */}
      <div className="border-t border-white/5 bg-black/20 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-12 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-4xl font-bold text-white mb-1 tracking-tight">20k+</div>
            <div className="text-sm text-muted-foreground font-medium uppercase tracking-widest">Indexed Ads</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-white mb-1 tracking-tight">1.5k+</div>
            <div className="text-sm text-muted-foreground font-medium uppercase tracking-widest">Brands</div>
          </div>
          <div>
            <div className="text-4xl font-bold text-white mb-1 tracking-tight">Daily</div>
            <div className="text-sm text-muted-foreground font-medium uppercase tracking-widest">Updates</div>
          </div>
        </div>
      </div>
    </main>
  );
}
