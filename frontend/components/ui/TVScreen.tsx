"use client";

import { ReactNode, useState } from "react";
import { motion } from "framer-motion";
import { clsx } from "clsx";

interface TVScreenProps {
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  variant?: "wood" | "plastic" | "chrome";
  showStatic?: boolean;
  showScanlines?: boolean;
  className?: string;
  onClick?: () => void;
}

export function TVScreen({
  children,
  size = "md",
  variant = "plastic",
  showStatic = false,
  showScanlines = true,
  className,
  onClick,
}: TVScreenProps) {
  const [isOn, setIsOn] = useState(true);

  const sizes = {
    sm: "w-[280px]",
    md: "w-[400px]",
    lg: "w-[560px]",
    xl: "w-full max-w-[800px]",
  };

  const variants = {
    wood: "bg-gradient-to-b from-amber-800 via-amber-900 to-amber-950",
    plastic: "bg-gradient-to-b from-zinc-700 via-zinc-800 to-zinc-900",
    chrome: "bg-gradient-to-b from-zinc-400 via-zinc-500 to-zinc-600",
  };

  return (
    <motion.div
      className={clsx("tv-set relative", sizes[size], className)}
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
    >
      {/* TV Cabinet/Shell */}
      <div
        className={clsx(
          "relative rounded-[2rem] p-6 md:p-8",
          variants[variant],
          "shadow-[0_20px_60px_-20px_rgba(0,0,0,0.8)]",
          "border-t border-white/10"
        )}
      >
        {/* Inner bezel */}
        <div className="relative rounded-[1.5rem] bg-black p-3 shadow-inner">
          {/* CRT Screen with curved edges */}
          <div
            className={clsx(
              "tv-screen relative overflow-hidden",
              "rounded-[1rem]",
              "aspect-[4/3]",
              "bg-void"
            )}
            style={{
              boxShadow: "inset 0 0 60px 20px rgba(0,0,0,0.5)",
            }}
          >
            {/* Screen content */}
            <div className="relative z-10 w-full h-full">{children}</div>

            {/* CRT curve reflection */}
            <div
              className="absolute inset-0 pointer-events-none z-20"
              style={{
                background:
                  "radial-gradient(ellipse 120% 100% at 50% 0%, rgba(255,255,255,0.1) 0%, transparent 50%)",
              }}
            />

            {/* Scanlines overlay */}
            {showScanlines && (
              <div className="absolute inset-0 pointer-events-none z-30 scanlines opacity-30" />
            )}

            {/* Static effect */}
            {showStatic && (
              <div className="absolute inset-0 z-40 tv-static opacity-20" />
            )}

            {/* Screen edge glow */}
            <div
              className="absolute inset-0 pointer-events-none z-20"
              style={{
                boxShadow: "inset 0 0 100px 30px rgba(230,57,70,0.1)",
              }}
            />
          </div>

          {/* Screen glass reflection */}
          <div
            className="absolute top-3 left-3 right-3 h-1/3 rounded-t-[1rem] pointer-events-none"
            style={{
              background:
                "linear-gradient(180deg, rgba(255,255,255,0.08) 0%, transparent 100%)",
            }}
          />
        </div>

        {/* TV Controls */}
        <div className="flex items-center justify-between mt-4 px-2">
          {/* Channel display */}
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-transmission animate-pulse" />
            <span className="font-mono text-xs text-zinc-400">CH 04</span>
          </div>

          {/* Knobs */}
          <div className="flex items-center gap-3">
            <TVKnob />
            <TVKnob />
          </div>
        </div>

        {/* Brand logo */}
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2">
          <span className="font-display text-xs font-bold text-zinc-500 tracking-widest">
            TELLYADS
          </span>
        </div>
      </div>

      {/* TV Stand/Legs */}
      <div className="flex justify-center gap-16 -mt-1">
        <div className="w-3 h-8 bg-gradient-to-b from-zinc-600 to-zinc-800 rounded-b-full" />
        <div className="w-3 h-8 bg-gradient-to-b from-zinc-600 to-zinc-800 rounded-b-full" />
      </div>
    </motion.div>
  );
}

function TVKnob() {
  return (
    <div className="relative w-8 h-8 rounded-full bg-gradient-to-b from-zinc-600 to-zinc-800 shadow-lg cursor-pointer hover:rotate-45 transition-transform duration-300">
      <div className="absolute inset-1 rounded-full bg-gradient-to-b from-zinc-500 to-zinc-700" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-3 bg-zinc-400 rounded-full" />
    </div>
  );
}

// Mini TV for cards
export function MiniTV({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <motion.div
      className={clsx("mini-tv cursor-pointer group", className)}
      whileHover={{ scale: 1.02, y: -5 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
    >
      {/* TV Frame */}
      <div className="relative bg-gradient-to-b from-zinc-700 via-zinc-800 to-zinc-900 rounded-2xl p-3 shadow-xl border-t border-white/10">
        {/* Screen bezel */}
        <div className="relative bg-black rounded-xl p-1.5">
          {/* CRT Screen */}
          <div
            className="relative overflow-hidden rounded-lg aspect-video bg-void"
            style={{
              boxShadow: "inset 0 0 30px 10px rgba(0,0,0,0.5)",
            }}
          >
            {children}

            {/* Scanlines */}
            <div className="absolute inset-0 pointer-events-none scanlines opacity-20" />

            {/* Curve reflection */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse 150% 100% at 50% 0%, rgba(255,255,255,0.07) 0%, transparent 40%)",
              }}
            />

            {/* Hover glow */}
            <div className="absolute inset-0 bg-transmission/0 group-hover:bg-transmission/10 transition-colors duration-300" />
          </div>
        </div>

        {/* Mini controls */}
        <div className="flex items-center justify-between mt-2 px-1">
          <div className="w-1.5 h-1.5 rounded-full bg-transmission/80" />
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-zinc-600" />
            <div className="w-3 h-3 rounded-full bg-zinc-600" />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
