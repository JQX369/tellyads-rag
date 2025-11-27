import { SearchResult } from '@/lib/types';
import Link from 'next/link';

interface AdGridProps {
  ads: SearchResult[];
}

export default function AdGrid({ ads }: AdGridProps) {
  if (!ads.length) {
    return (
      <div className="flex flex-col items-center justify-center py-32 text-center">
        <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-6">
           <span className="text-4xl">🔍</span>
        </div>
        <h3 className="text-xl font-medium text-white mb-2">No commercials found</h3>
        <p className="text-slate-400 max-w-md mx-auto">
          Try adjusting your search terms or look for broader concepts like "funny" or "emotional".
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 auto-rows-[minmax(300px,auto)]">
      {ads.map((ad) => (
        <Link href={`/ads/${ad.external_id}`} key={ad.id} className="group relative">
          <div className="h-full bg-card border border-white/10 rounded-2xl overflow-hidden hover:border-blue-500/50 hover:shadow-[0_0_30px_-10px_rgba(59,130,246,0.3)] transition-all duration-300 flex flex-col">
            
            {/* Thumbnail Area */}
            <div className="relative aspect-video bg-black/40 overflow-hidden group-hover:opacity-90 transition-opacity">
               {ad.image_url ? (
                 /* eslint-disable-next-line @next/next/no-img-element */
                 <img 
                   src={ad.image_url} 
                   alt={ad.brand_name || 'Ad'} 
                   className="w-full h-full object-cover transform group-hover:scale-105 transition-transform duration-500" 
                 />
               ) : (
                 <div className="absolute inset-0 flex items-center justify-center text-white/20">
                    <span className="text-4xl">📺</span>
                 </div>
               )}
               
               {/* Score Badge */}
               {ad.score && (
                 <div className="absolute top-3 right-3 bg-black/60 backdrop-blur-md border border-white/10 text-green-400 text-xs font-bold px-2 py-1 rounded-md shadow-lg">
                   {Math.round(ad.score * 100)}% Match
                 </div>
               )}
            </div>
            
            {/* Content */}
            <div className="p-5 flex flex-col flex-grow relative">
              <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              
              <div className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-2 flex items-center gap-2">
                {ad.brand_name || 'Unknown Brand'}
              </div>
              
              <h3 className="font-medium text-lg text-white line-clamp-2 mb-3 leading-snug group-hover:text-blue-300 transition-colors">
                {ad.product_name || ad.text?.substring(0, 60) || 'Untitled Ad'}
              </h3>
              
              <p className="text-sm text-slate-400 line-clamp-2 mb-4">
                 {ad.description || ad.text || 'No description available.'}
              </p>

              <div className="mt-auto pt-4 flex items-center justify-between border-t border-white/5 text-xs text-slate-500">
                <span>{ad.item_type === 'tv_ad' ? 'Commercial' : 'Ad'}</span>
                <span className="group-hover:translate-x-1 transition-transform duration-300 text-blue-400 font-medium">
                  Watch Now →
                </span>
              </div>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
