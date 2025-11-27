import { SearchResult } from '@/lib/types';
import Link from 'next/link';

interface AdGridProps {
  ads: SearchResult[];
}

export default function AdGrid({ ads }: AdGridProps) {
  if (!ads.length) {
    return (
      <div className="text-center py-20 text-gray-500">
        No ads found. Try a different search query.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {ads.map((ad) => (
        <Link href={`/ads/${ad.external_id}`} key={ad.id} className="group">
          <div className="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow overflow-hidden border border-slate-100 h-full flex flex-col">
            {/* Thumbnail Placeholder - In production, use next/image with a valid src */}
            <div className="aspect-video bg-slate-100 relative overflow-hidden">
               {/* Assuming we might have image_url in SearchResult later, or we fallback */}
               {/* For MVP, generic placeholder or try to fetch image if API provides it */}
               <div className="absolute inset-0 flex items-center justify-center text-slate-300">
                  <span className="text-4xl">📺</span>
               </div>
            </div>
            
            <div className="p-4 flex flex-col flex-grow">
              <div className="text-xs font-semibold uppercase tracking-wider text-blue-600 mb-1">
                {ad.brand_name || 'Unknown Brand'}
              </div>
              <h3 className="font-medium text-slate-900 line-clamp-2 mb-2 group-hover:text-blue-600 transition-colors">
                {ad.product_name || ad.text?.substring(0, 50) || 'Untitled Ad'}
              </h3>
              
              {ad.score && (
                <div className="mt-auto pt-3 flex items-center text-xs text-slate-500 border-t border-slate-50">
                  <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                    {Math.round(ad.score * 100)}% Match
                  </span>
                </div>
              )}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

