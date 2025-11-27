import { Metadata } from 'next';
import { AdDetail } from '@/lib/types';
import { constructMetadata } from '@/lib/seo';
import Link from 'next/link';

// Force dynamic rendering
export const dynamic = 'force-dynamic';

interface AdPageProps {
  params: { external_id: string };
}

async function getAdDetail(external_id: string): Promise<AdDetail> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/ads/${external_id}`, {
    cache: 'no-store', // Always fetch fresh data
  });
  
  if (!res.ok) {
    throw new Error('Ad not found');
  }
  
  return res.json();
}

async function getSimilarAds(external_id: string): Promise<any[]> {
    try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/ads/${external_id}/similar`, {
            next: { revalidate: 3600 }
        });
        return res.ok ? res.json() : [];
    } catch {
        return [];
    }
}

export async function generateMetadata({ params }: AdPageProps): Promise<Metadata> {
  try {
    const ad = await getAdDetail(params.external_id);
    const title = `${ad.brand_name || 'TV Ad'} - ${ad.product_name || ad.description || 'Commercial'} | TellyAds`;
    const description = ad.description || `Watch this ${ad.year || ''} commercial for ${ad.brand_name}. Analyzed with AI for creative insights.`;
    
    return constructMetadata({
      title,
      description,
      image: ad.image_url,
    });
  } catch {
    return constructMetadata({ title: 'Ad Not Found' });
  }
}

export default async function AdPage({ params }: AdPageProps) {
  let ad: AdDetail;
  let similarAds = [];

  try {
    ad = await getAdDetail(params.external_id);
    similarAds = await getSimilarAds(params.external_id);
  } catch (e) {
    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <div className="text-center">
                <h1 className="text-4xl font-bold text-slate-800 mb-4">404</h1>
                <p className="text-slate-500 mb-8">Ad not found or removed.</p>
                <Link href="/" className="text-blue-600 hover:underline">Return Home</Link>
            </div>
        </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
         <div className="max-w-7xl mx-auto px-4 py-4">
            <Link href="/" className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
                TellyAds
            </Link>
         </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Main Content: Video & Metadata */}
            <div className="lg:col-span-2 space-y-8">
                {/* Video Player */}
                <div className="bg-black rounded-xl overflow-hidden shadow-lg aspect-video relative">
                    {ad.video_url ? (
                        <video 
                            controls 
                            poster={ad.image_url}
                            className="w-full h-full object-contain"
                            src={ad.video_url}
                        >
                            Your browser does not support the video tag.
                        </video>
                    ) : (
                        <div className="flex items-center justify-center h-full text-white/50">
                            Video Unavailable
                        </div>
                    )}
                </div>

                {/* Title & Core Info */}
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 mb-2">
                        {ad.brand_name} <span className="text-slate-400 font-light">|</span> {ad.product_name}
                    </h1>
                    <div className="flex flex-wrap gap-4 text-sm text-slate-600 mb-6">
                        {ad.year && <span className="bg-slate-100 px-3 py-1 rounded-full">{ad.year}</span>}
                        {ad.duration_seconds && <span className="bg-slate-100 px-3 py-1 rounded-full">{ad.duration_seconds}s</span>}
                        <span className="bg-slate-100 px-3 py-1 rounded-full">{ad.external_id}</span>
                    </div>
                    <p className="text-lg text-slate-700 leading-relaxed">
                        {ad.description}
                    </p>
                </div>

                {/* Analysis Section (RAG Data) */}
                {ad.analysis && (
                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-6">
                        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                            ✨ AI Creative Analysis
                        </h2>
                        
                        {/* Impact Scores */}
                        {ad.impact_scores && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {Object.entries(ad.impact_scores).map(([key, val]: [string, any]) => {
                                    if (typeof val === 'object' && val?.score) {
                                        return (
                                            <div key={key} className="bg-slate-50 p-3 rounded-lg text-center">
                                                <div className="text-2xl font-bold text-blue-600">{val.score}/10</div>
                                                <div className="text-xs font-medium uppercase tracking-wider text-slate-500 mt-1">
                                                    {key.replace(/_/g, ' ')}
                                                </div>
                                            </div>
                                        );
                                    }
                                    return null;
                                })}
                            </div>
                        )}

                        {/* Creative DNA / Strategy */}
                        <div className="prose prose-slate max-w-none">
                            {/* Assuming some analysis structure - adapting generically */}
                            {ad.analysis.campaign_strategy && (
                                <div className="mb-4">
                                    <h3 className="text-base font-semibold text-slate-900 uppercase tracking-wide mb-2">Strategy</h3>
                                    <ul className="list-disc pl-4 space-y-1">
                                        <li><strong>Objective:</strong> {ad.analysis.campaign_strategy.objective}</li>
                                        <li><strong>Target:</strong> {ad.analysis.campaign_strategy.target_audience}</li>
                                        <li><strong>Hook:</strong> {ad.analysis.creative_dna?.hook_type}</li>
                                    </ul>
                                </div>
                            )}
                            
                             {ad.analysis.emotional_timeline?.arc_shape && (
                                <div className="mb-4">
                                    <h3 className="text-base font-semibold text-slate-900 uppercase tracking-wide mb-2">Emotional Arc</h3>
                                    <p>{ad.analysis.emotional_timeline.arc_shape.replace(/_/g, ' ')} journey peaking with {ad.analysis.emotional_timeline.peak_emotion}.</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* Sidebar: Similar Ads */}
            <div className="lg:col-span-1 space-y-6">
                <h3 className="font-bold text-slate-900 text-lg">Similar Commercials</h3>
                <div className="flex flex-col gap-4">
                    {similarAds.map((sim: any) => (
                        <Link href={`/ads/${sim.external_id}`} key={sim.id} className="group block">
                             <div className="flex gap-4 p-3 bg-white rounded-lg border border-slate-100 hover:shadow-md transition-shadow">
                                <div className="w-24 aspect-video bg-slate-100 rounded overflow-hidden relative shrink-0">
                                    {/* Placeholder for similar ad thumb */}
                                    <div className="absolute inset-0 flex items-center justify-center text-slate-300">📺</div>
                                </div>
                                <div>
                                    <div className="font-semibold text-sm text-slate-900 group-hover:text-blue-600 line-clamp-2">
                                        {sim.brand_name} - {sim.product_name}
                                    </div>
                                    <div className="text-xs text-slate-500 mt-1">
                                        {Math.round((sim.score || 0) * 100)}% Match
                                    </div>
                                </div>
                             </div>
                        </Link>
                    ))}
                    {similarAds.length === 0 && (
                        <div className="text-slate-400 text-sm">No similar ads found.</div>
                    )}
                </div>
            </div>

        </div>
      </main>
    </div>
  );
}

