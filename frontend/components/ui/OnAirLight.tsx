"use client";

import { clsx } from "clsx";

interface OnAirLightProps {
  text?: string;
  active?: boolean;
  className?: string;
}

export function OnAirLight({
  text = "ON AIR",
  active = true,
  className,
}: OnAirLightProps) {
  return (
    <div
      className={clsx(
        "inline-flex items-center gap-3 px-4 py-2",
        "bg-void/80 backdrop-blur-sm",
        "border border-transmission/30 rounded",
        className
      )}
    >
      {/* Glowing indicator */}
      <span
        className={clsx(
          "relative w-2.5 h-2.5 rounded-full",
          active ? "bg-transmission" : "bg-antenna"
        )}
      >
        {active && (
          <>
            {/* Glow rings */}
            <span className="absolute inset-0 rounded-full bg-transmission animate-ping opacity-75" />
            <span
              className="absolute -inset-1 rounded-full opacity-50"
              style={{
                background: "radial-gradient(circle, rgba(230, 57, 70, 0.6) 0%, transparent 70%)",
              }}
            />
          </>
        )}
      </span>

      {/* Text */}
      <span
        className={clsx(
          "font-mono text-label uppercase tracking-ultra-wide",
          active ? "text-transmission" : "text-antenna"
        )}
      >
        {text}
      </span>
    </div>
  );
}
