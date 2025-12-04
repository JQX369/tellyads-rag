"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import Image from "next/image";

interface Ad {
  external_id: string;
  brand_name: string;
  product_name?: string;
  year?: number;
  image_url?: string;
  one_line_summary?: string;
}

interface FeaturedAdsProps {
  ads: Ad[];
  title?: string;
  subtitle?: string;
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 40, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.7,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  },
};

export function FeaturedAds({
  ads,
  title = "Now Showing",
  subtitle = "Featured",
}: FeaturedAdsProps) {
  if (!ads || ads.length === 0) return null;

  return (
    <section className="relative py-24 overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-1/4 right-0 w-[600px] h-[600px] bg-transmission/5 blob opacity-50" />
      </div>

      {/* Section header */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 mb-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="flex items-end justify-between"
        >
          <div>
            <span className="inline-flex items-center gap-3 mb-4">
              <span className="w-12 h-px bg-transmission" />
              <span className="font-mono text-xs uppercase tracking-widest text-transmission">
                {subtitle}
              </span>
            </span>
            <h2 className="font-display text-4xl md:text-5xl font-bold text-signal">
              {title}
            </h2>
          </div>

          <Link
            href="/browse"
            className="hidden md:flex items-center gap-2 font-mono text-sm text-antenna hover:text-transmission transition-colors group"
          >
            <span>View all</span>
            <motion.span
              className="inline-block"
              animate={{ x: [0, 4, 0] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              →
            </motion.span>
          </Link>
        </motion.div>
      </div>

      {/* Horizontal scroll TV carousel */}
      <div className="relative">
        <motion.div
          className="flex gap-8 overflow-x-auto scrollbar-hide px-6 lg:px-12 pb-8"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {ads.map((ad, index) => (
            <motion.div
              key={ad.external_id}
              variants={itemVariants}
              className="flex-shrink-0"
            >
              <TVAdCard ad={ad} index={index} />
            </motion.div>
          ))}
        </motion.div>

        {/* Fade edges */}
        <div className="absolute top-0 left-0 bottom-8 w-24 bg-gradient-to-r from-void to-transparent pointer-events-none" />
        <div className="absolute top-0 right-0 bottom-8 w-24 bg-gradient-to-l from-void to-transparent pointer-events-none" />
      </div>

      {/* Mobile view all link */}
      <div className="md:hidden text-center mt-8 px-6">
        <Link
          href="/browse"
          className="btn-ghost inline-block"
        >
          View all ads
        </Link>
      </div>
    </section>
  );
}

function TVAdCard({ ad, index }: { ad: Ad; index: number }) {
  return (
    <Link href={`/ads/${ad.external_id}`}>
      <motion.article
        className="group relative w-[300px] md:w-[360px]"
        whileHover={{ y: -10, scale: 1.02 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Glow effect */}
        <div className="absolute inset-0 blur-2xl bg-transmission/10 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-3xl" />

        {/* TV Frame */}
        <div className="relative card-tv">
          {/* Screen bezel */}
          <div className="card-tv-screen">
            {/* CRT Screen */}
            <div
              className="relative aspect-video overflow-hidden rounded-xl bg-void"
              style={{
                boxShadow: "inset 0 0 50px 15px rgba(0,0,0,0.6)",
              }}
            >
              {/* Image or placeholder */}
              {ad.image_url ? (
                <Image
                  src={ad.image_url}
                  alt={`${ad.brand_name} advertisement`}
                  fill
                  className="object-cover transition-transform duration-700 group-hover:scale-110"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-transmission/10 to-void">
                  <span className="font-display text-6xl font-bold text-signal/20">
                    {ad.brand_name?.charAt(0) || "?"}
                  </span>
                </div>
              )}

              {/* Scanlines */}
              <div className="absolute inset-0 scanlines opacity-20 pointer-events-none" />

              {/* Screen reflection */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "radial-gradient(ellipse 80% 50% at 30% 20%, rgba(255,255,255,0.06) 0%, transparent 50%)",
                }}
              />

              {/* Year badge */}
              {ad.year && (
                <div className="absolute top-3 right-3">
                  <span className="font-mono text-xs bg-transmission/80 text-signal px-2 py-1 rounded-sm">
                    {ad.year}
                  </span>
                </div>
              )}

              {/* Play button overlay */}
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300">
                <motion.div
                  className="w-14 h-14 rounded-full bg-transmission flex items-center justify-center"
                  initial={{ scale: 0.8 }}
                  whileHover={{ scale: 1.1 }}
                  style={{
                    boxShadow: "0 0 30px rgba(230, 57, 70, 0.5)",
                  }}
                >
                  <svg
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="white"
                    className="ml-1"
                  >
                    <polygon points="5 3 19 12 5 21 5 3" />
                  </svg>
                </motion.div>
              </div>

              {/* Hover tint */}
              <div className="absolute inset-0 bg-transmission/0 group-hover:bg-transmission/10 transition-colors duration-300" />
            </div>
          </div>

          {/* TV Controls */}
          <div className="flex items-center justify-between mt-3 px-2">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-transmission/60 group-hover:bg-transmission transition-colors" />
              <span className="font-mono text-[10px] text-zinc-500">
                CH {String(index + 1).padStart(2, "0")}
              </span>
            </div>
            <div className="flex gap-2">
              <div className="w-4 h-4 rounded-full bg-zinc-700" />
              <div className="w-4 h-4 rounded-full bg-zinc-700" />
            </div>
          </div>
        </div>

        {/* Content below TV */}
        <div className="mt-5 px-2">
          {/* Brand */}
          <span className="font-mono text-[10px] uppercase tracking-widest text-transmission">
            {ad.brand_name}
          </span>

          {/* Product/Title */}
          <h3 className="font-display text-lg font-semibold text-signal mt-1 line-clamp-1 group-hover:text-transmission transition-colors">
            {ad.product_name || ad.brand_name}
          </h3>

          {/* Summary */}
          {ad.one_line_summary && (
            <p className="font-mono text-xs text-antenna mt-2 line-clamp-2 opacity-70 group-hover:opacity-100 transition-opacity">
              {ad.one_line_summary}
            </p>
          )}
        </div>
      </motion.article>
    </Link>
  );
}
