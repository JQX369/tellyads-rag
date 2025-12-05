"use client";

import { motion } from "framer-motion";
import Link from "next/link";

const decades = [
  {
    year: "2000s",
    label: "The Millennium",
    description: "Reality TV era, dot-com boom",
    color: "#3B82F6",
    gradient: "from-blue-500/20 to-purple-500/20",
  },
  {
    year: "2010s",
    label: "The Digital Age",
    description: "Smartphones, social media rise",
    color: "#10B981",
    gradient: "from-emerald-500/20 to-teal-500/20",
  },
  {
    year: "2020s",
    label: "The Streaming Era",
    description: "Connected world, streaming wars",
    color: "#E63946",
    gradient: "from-transmission/20 to-orange-500/20",
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 50, scale: 0.9 },
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

export function DecadeNav() {
  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          className="absolute top-1/4 left-0 w-[500px] h-[500px] bg-transmission/5 blob"
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-blue-500/5 blob-reverse"
          animate={{ rotate: -360 }}
          transition={{ duration: 80, repeat: Infinity, ease: "linear" }}
        />

        {/* Film Strip - Top Right */}
        <motion.div
          className="absolute -top-8 -right-16 rotate-[15deg] opacity-[0.15]"
          initial={{ x: 100, opacity: 0 }}
          whileInView={{ x: 0, opacity: 0.15 }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay: 0.3 }}
        >
          <FilmStrip direction="down" />
        </motion.div>

        {/* Film Strip - Bottom Left */}
        <motion.div
          className="absolute -bottom-8 -left-16 -rotate-[15deg] opacity-[0.12]"
          initial={{ x: -100, opacity: 0 }}
          whileInView={{ x: 0, opacity: 0.12 }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay: 0.5 }}
        >
          <FilmStrip direction="up" />
        </motion.div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <span className="inline-flex items-center gap-4 mb-6">
            <span className="w-16 h-px bg-gradient-to-r from-transparent to-transmission" />
            <span className="font-mono text-xs uppercase tracking-widest text-transmission">
              Time Travel
            </span>
            <span className="w-16 h-px bg-gradient-to-l from-transparent to-transmission" />
          </span>
          <h2 className="font-display text-4xl md:text-5xl lg:text-6xl font-bold text-signal mb-4">
            Browse by Era
          </h2>
          <p className="font-mono text-antenna max-w-lg mx-auto">
            Three decades of British television advertising, from the millennium to today
          </p>
        </motion.div>

        {/* Decade TV cards */}
        <motion.div
          className="grid md:grid-cols-3 gap-8 lg:gap-12"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {decades.map((decade, index) => (
            <motion.div key={decade.year} variants={itemVariants}>
              <DecadeTV decade={decade} index={index} />
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function DecadeTV({
  decade,
  index,
}: {
  decade: {
    year: string;
    label: string;
    description: string;
    color: string;
    gradient: string;
  };
  index: number;
}) {
  return (
    <Link href={`/browse?decade=${decade.year.slice(0, 4)}`}>
      <motion.article
        className="group relative"
        whileHover={{ y: -12, rotateY: 5 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        style={{ perspective: "1000px" }}
      >
        {/* Glow effect */}
        <div
          className="absolute inset-0 blur-2xl opacity-0 group-hover:opacity-50 transition-opacity duration-500 rounded-3xl"
          style={{ backgroundColor: decade.color }}
        />

        {/* TV Frame */}
        <div className="relative card-tv">
          {/* Screen container */}
          <div className="card-tv-screen">
            {/* CRT Screen */}
            <div
              className={`relative aspect-[4/3] bg-gradient-to-br ${decade.gradient} overflow-hidden rounded-xl`}
              style={{
                boxShadow: `inset 0 0 60px 15px rgba(0,0,0,0.5), 0 0 0 1px ${decade.color}20`,
              }}
            >
              {/* Large year watermark */}
              <div className="absolute inset-0 flex items-center justify-center overflow-hidden">
                <motion.span
                  className="font-display text-[120px] md:text-[150px] font-bold text-white/5 select-none"
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                >
                  {decade.year.slice(0, 2)}
                </motion.span>
              </div>

              {/* Content */}
              <div className="relative z-10 h-full flex flex-col justify-between p-6">
                {/* Top: Era label */}
                <div className="flex justify-between items-start">
                  <span
                    className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 rounded-sm"
                    style={{ backgroundColor: `${decade.color}30`, color: decade.color }}
                  >
                    {decade.label}
                  </span>
                  <div
                    className="w-2 h-2 rounded-full animate-pulse"
                    style={{ backgroundColor: decade.color }}
                  />
                </div>

                {/* Bottom: Year and description */}
                <div>
                  <h3
                    className="font-display text-5xl md:text-6xl font-bold mb-2 transition-colors"
                    style={{ color: decade.color }}
                  >
                    {decade.year}
                  </h3>
                  <p className="font-mono text-xs text-signal/70 group-hover:text-signal transition-colors">
                    {decade.description}
                  </p>
                </div>
              </div>

              {/* Scanlines */}
              <div className="absolute inset-0 scanlines opacity-20 pointer-events-none" />

              {/* Screen reflection */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background:
                    "radial-gradient(ellipse 80% 50% at 30% 20%, rgba(255,255,255,0.08) 0%, transparent 50%)",
                }}
              />

              {/* Hover overlay */}
              <div
                className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{
                  background: `radial-gradient(circle at center, ${decade.color}10 0%, transparent 70%)`,
                }}
              />
            </div>
          </div>

          {/* TV Controls */}
          <div className="flex items-center justify-between mt-4 px-3">
            {/* Channel display */}
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full transition-colors"
                style={{ backgroundColor: decade.color }}
              />
              <span className="font-mono text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors">
                CH 0{index + 1}
              </span>
            </div>

            {/* Knobs */}
            <div className="flex gap-2">
              <motion.div
                className="w-5 h-5 rounded-full bg-zinc-700 group-hover:bg-zinc-600 transition-colors cursor-pointer"
                whileHover={{ rotate: 45 }}
              />
              <motion.div
                className="w-5 h-5 rounded-full bg-zinc-700 group-hover:bg-zinc-600 transition-colors cursor-pointer"
                whileHover={{ rotate: -45 }}
              />
            </div>
          </div>
        </div>

        {/* "Click to explore" hint */}
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <span className="font-mono text-[10px] text-antenna uppercase tracking-widest">
            Click to explore
          </span>
        </div>
      </motion.article>
    </Link>
  );
}

// Film strip component for background decoration
function FilmStrip({ direction }: { direction: "up" | "down" }) {
  const frames = Array.from({ length: 8 }, (_, i) => i);

  return (
    <div className="flex flex-col">
      {/* Film strip with sprocket holes */}
      <div className="relative bg-zinc-900 rounded-sm" style={{ width: 120 }}>
        {/* Left sprocket holes */}
        <div className="absolute left-1 top-0 bottom-0 flex flex-col justify-around py-2">
          {frames.map((i) => (
            <div key={`l-${i}`} className="w-2 h-3 bg-black/80 rounded-sm" />
          ))}
        </div>

        {/* Right sprocket holes */}
        <div className="absolute right-1 top-0 bottom-0 flex flex-col justify-around py-2">
          {frames.map((i) => (
            <div key={`r-${i}`} className="w-2 h-3 bg-black/80 rounded-sm" />
          ))}
        </div>

        {/* Film frames */}
        <div className="px-5 py-2 flex flex-col gap-1">
          {frames.map((i) => (
            <motion.div
              key={i}
              className="relative bg-gradient-to-br from-zinc-800 to-zinc-900 rounded-sm overflow-hidden"
              style={{ width: 80, height: 60 }}
              initial={{ opacity: 0.3 }}
              animate={{
                opacity: [0.3, 0.6, 0.3],
              }}
              transition={{
                duration: 3,
                delay: i * 0.2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              {/* Simulated ad still content */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div
                  className="w-full h-full"
                  style={{
                    background: `linear-gradient(${45 + i * 15}deg,
                      ${i % 3 === 0 ? 'rgba(230,57,70,0.2)' : i % 3 === 1 ? 'rgba(59,130,246,0.2)' : 'rgba(16,185,129,0.2)'} 0%,
                      transparent 60%)`,
                  }}
                />
              </div>
              {/* TV static overlay */}
              <div
                className="absolute inset-0 opacity-30"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
                }}
              />
              {/* Frame number */}
              <div className="absolute bottom-0.5 right-1 font-mono text-[6px] text-white/30">
                {direction === "down" ? i + 1 : 8 - i}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
