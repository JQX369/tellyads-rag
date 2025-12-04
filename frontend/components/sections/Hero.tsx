"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import Image from "next/image";
import { useRef } from "react";

export function Hero() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  const tvY = useTransform(scrollYProgress, [0, 1], [0, -100]);
  const tvRotate = useTransform(scrollYProgress, [0, 1], [0, -5]);
  const textY = useTransform(scrollYProgress, [0, 1], [0, 50]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <section
      ref={containerRef}
      className="relative min-h-screen overflow-hidden bg-void"
    >
      {/* Animated background blobs */}
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          className="absolute -top-1/4 -left-1/4 w-[600px] h-[600px] bg-transmission/5 blob"
          animate={{
            scale: [1, 1.1, 1],
            x: [0, 30, 0],
            y: [0, -20, 0],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -bottom-1/4 -right-1/4 w-[800px] h-[800px] bg-transmission/3 blob-reverse"
          animate={{
            scale: [1.1, 1, 1.1],
            x: [0, -40, 0],
            y: [0, 30, 0],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-white/[0.02] blob"
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
        />
      </div>

      {/* Decorative orbiting rings */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
        <div className="retro-ring w-[600px] h-[600px] opacity-20" />
        <div
          className="retro-ring w-[800px] h-[800px] opacity-10 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          style={{ animationDirection: "reverse", animationDuration: "45s" }}
        />
      </div>

      {/* Main content */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 pt-32 pb-20">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center min-h-[80vh]">
          {/* Left: Text content */}
          <motion.div style={{ y: textY, opacity }} className="space-y-8">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-3"
            >
              <span className="on-air">
                <span className="on-air-text">Now Streaming</span>
              </span>
            </motion.div>

            {/* Heading */}
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.1 }}
              className="font-display text-5xl md:text-6xl lg:text-7xl font-bold text-signal leading-[0.95]"
            >
              <span className="block">Britain&apos;s TV</span>
              <span className="block text-gradient-red">Ad Archive</span>
            </motion.h1>

            {/* Description */}
            <motion.p
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="font-mono text-lg text-antenna max-w-md leading-relaxed"
            >
              Explore thousands of UK television commercials from 2000 to today.
              Searchable. Streamable. Nostalgic.
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.3 }}
              className="flex flex-wrap gap-4"
            >
              <Link href="/browse" className="btn-retro">
                Browse Archive
              </Link>
              <Link href="/random" className="btn-ghost">
                Random Ad
              </Link>
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="flex gap-12 pt-8 border-t border-white/10"
            >
              <Stat value="20K+" label="Adverts" />
              <Stat value="3000+" label="Brands" />
              <Stat value="24yrs" label="Of Ads" />
            </motion.div>
          </motion.div>

          {/* Right: Hero TV Display */}
          <motion.div
            style={{ y: tvY, rotate: tvRotate }}
            className="relative flex justify-center lg:justify-end"
          >
            <HeroTV />
          </motion.div>
        </div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        className="absolute bottom-8 left-1/2 -translate-x-1/2"
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="flex flex-col items-center gap-2">
          <span className="font-mono text-xs text-antenna uppercase tracking-widest">
            Scroll
          </span>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className="text-transmission"
          >
            <path d="M12 5v14M5 12l7 7 7-7" />
          </svg>
        </div>
      </motion.div>
    </section>
  );
}

function HeroTV() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, rotateY: -20 }}
      animate={{ opacity: 1, scale: 1, rotateY: 0 }}
      transition={{ duration: 1, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="relative"
    >
      {/* Glow effect behind TV */}
      <div className="absolute inset-0 blur-3xl bg-transmission/20 scale-110 rounded-full" />

      {/* Retro TV Frame */}
      <div className="relative tv-frame w-[320px] md:w-[420px] lg:w-[480px]">
        {/* Screen bezel */}
        <div className="tv-screen-inner">
          {/* CRT Screen */}
          <div className="tv-screen-curved aspect-[4/3] bg-void crt-on">
            {/* Video/Image content */}
            <div className="relative w-full h-full overflow-hidden">
              {/* Background Video - Place your video at /public/hero-video.mp4 */}
              <video
                autoPlay
                loop
                muted
                playsInline
                className="absolute inset-0 w-full h-full object-cover"
                poster="/hero-poster.jpg"
              >
                <source src="/hero-video.mp4" type="video/mp4" />
                <source src="/hero-video.webm" type="video/webm" />
              </video>

              {/* Fallback overlay when no video */}
              <div className="absolute inset-0 bg-gradient-to-br from-transmission/20 via-void/50 to-void/80">
                {/* Animated test pattern (shows through when video loads) */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <motion.div
                    className="text-center"
                    animate={{ opacity: [0.5, 1, 0.5] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  >
                    <div className="font-display text-6xl md:text-7xl font-bold text-signal mb-2">
                      TA
                    </div>
                    <div className="font-mono text-xs text-transmission uppercase tracking-widest">
                      TellyAds
                    </div>
                  </motion.div>
                </div>

                {/* Color bars at bottom */}
                <div className="absolute bottom-0 left-0 right-0 h-8 flex">
                  {["#E63946", "#F8F9FA", "#0D0D0D", "#E63946", "#6B6B6B", "#F8F9FA", "#2B2B2B"].map(
                    (color, i) => (
                      <div
                        key={i}
                        className="flex-1"
                        style={{ backgroundColor: color }}
                      />
                    )
                  )}
                </div>
              </div>

              {/* Scanlines overlay */}
              <div className="absolute inset-0 scanlines-animated opacity-30" />

              {/* CRT vignette effect */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 50%, rgba(0,0,0,0.4) 100%)",
                }}
              />

              {/* Screen reflection */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "radial-gradient(ellipse 100% 60% at 30% 20%, rgba(255,255,255,0.1) 0%, transparent 50%)",
                }}
              />
            </div>
          </div>
        </div>

        {/* TV Controls */}
        <div className="flex items-center justify-between mt-4 px-4">
          {/* Channel indicator */}
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-transmission animate-pulse" />
            <span className="font-mono text-xs text-zinc-500">CH 01</span>
          </div>

          {/* Control knobs */}
          <div className="flex items-center gap-3">
            <div className="tv-knob w-8 h-8" />
            <div className="tv-knob w-8 h-8" />
          </div>
        </div>

        {/* Brand badge */}
        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 bg-zinc-800 px-4 py-1 rounded-full">
          <span className="font-display text-xs font-bold text-zinc-400 tracking-widest">
            TELLYADS
          </span>
        </div>
      </div>

      {/* Floating decoration */}
      <motion.div
        className="absolute -top-8 -right-8 w-16 h-16"
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
      >
        <div className="starburst" style={{ "--starburst-size": "64px" } as React.CSSProperties} />
      </motion.div>

      {/* Antenna decoration */}
      <div className="absolute -top-16 left-1/2 -translate-x-1/2">
        <svg
          width="80"
          height="60"
          viewBox="0 0 80 60"
          fill="none"
          className="text-zinc-600"
        >
          <path
            d="M40 60V30M40 30L20 5M40 30L60 5"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle cx="20" cy="5" r="4" fill="currentColor" />
          <circle cx="60" cy="5" r="4" fill="currentColor" />
        </svg>
      </div>
    </motion.div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="font-display text-3xl md:text-4xl font-bold text-signal">
        {value}
      </div>
      <div className="font-mono text-xs uppercase tracking-widest text-antenna mt-1">
        {label}
      </div>
    </div>
  );
}
