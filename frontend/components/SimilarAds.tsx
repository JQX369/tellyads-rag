"use client";

import Link from "next/link";
import Image from "next/image";
import { clsx } from "clsx";
import { Badge } from "@/components/ui";

interface SimilarAd {
  id: string;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  year?: number;
  image_url?: string;
  score?: number;
}

interface SimilarAdsProps {
  ads: SimilarAd[];
}

export function SimilarAds({ ads }: SimilarAdsProps) {
  if (!ads || ads.length === 0) {
    return (
      <div className="p-4 bg-static/30 rounded border border-white/5">
        <h3 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Similar Ads
        </h3>
        <p className="font-mono text-sm text-antenna/60">No similar ads found.</p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
        More Like This
      </h3>

      <div className="flex flex-col gap-3">
        {ads.map((ad) => (
          <SimilarAdCard key={ad.id || ad.external_id} ad={ad} />
        ))}
      </div>
    </div>
  );
}

function SimilarAdCard({ ad }: { ad: SimilarAd }) {
  const matchPercent = ad.score ? Math.round(ad.score * 100) : null;

  return (
    <Link href={`/ads/${ad.external_id}`}>
      <article
        className={clsx(
          "group flex gap-4 p-3",
          "bg-static/30 rounded border border-white/5",
          "transition-all duration-300",
          "hover:bg-static/50 hover:border-white/10"
        )}
      >
        {/* Thumbnail */}
        <div className="relative w-24 aspect-video rounded overflow-hidden flex-shrink-0 bg-static">
          {ad.image_url ? (
            <Image
              src={ad.image_url}
              alt={`${ad.brand_name} advertisement`}
              fill
              className="object-cover"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-display text-xl font-bold text-antenna/30">
                {ad.brand_name?.charAt(0) || "?"}
              </span>
            </div>
          )}

          {/* Play icon on hover */}
          <div className="absolute inset-0 flex items-center justify-center bg-void/40 opacity-0 group-hover:opacity-100 transition-opacity">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="white"
              className="ml-0.5"
            >
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <span className="font-mono text-[10px] uppercase tracking-ultra-wide text-transmission">
            {ad.brand_name}
          </span>
          <h4 className="font-display text-sm font-medium text-signal line-clamp-1 group-hover:text-transmission transition-colors">
            {ad.product_name || ad.brand_name}
          </h4>

          <div className="flex items-center gap-2 mt-1">
            {ad.year && (
              <span className="font-mono text-xs text-antenna">{ad.year}</span>
            )}
            {matchPercent !== null && (
              <Badge variant="muted" size="sm">
                {matchPercent}% match
              </Badge>
            )}
          </div>
        </div>
      </article>
    </Link>
  );
}
