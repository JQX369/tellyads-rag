"use client";

import { clsx } from "clsx";

interface StarburstProps {
  size?: number;
  color?: string;
  className?: string;
  spinning?: boolean;
}

export function Starburst({
  size = 40,
  color = "#E63946",
  className,
  spinning = true,
}: StarburstProps) {
  return (
    <div
      className={clsx("relative", className)}
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 100 100"
        className={clsx(
          "absolute inset-0",
          spinning && "animate-spin-slow"
        )}
        style={{ animationDuration: "8s" }}
      >
        <polygon
          fill={color}
          points="50,0 61,35 98,35 68,57 79,91 50,70 21,91 32,57 2,35 39,35"
        />
      </svg>
      <svg
        viewBox="0 0 100 100"
        className={clsx(
          "absolute inset-0 opacity-50 scale-75",
          spinning && "animate-spin-slow"
        )}
        style={{
          animationDuration: "8s",
          animationDirection: "reverse"
        }}
      >
        <polygon
          fill={color}
          points="50,0 61,35 98,35 68,57 79,91 50,70 21,91 32,57 2,35 39,35"
        />
      </svg>
    </div>
  );
}

// Eight-pointed atomic starburst
export function AtomicStarburst({
  size = 60,
  color = "#E63946",
  className,
}: StarburstProps) {
  return (
    <div
      className={clsx("relative", className)}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0">
        {/* Main 8-point star */}
        <path
          fill={color}
          d="M50 0 L56 38 L50 45 L44 38 Z
             M100 50 L62 56 L55 50 L62 44 Z
             M50 100 L44 62 L50 55 L56 62 Z
             M0 50 L38 44 L45 50 L38 56 Z
             M85 15 L60 42 L55 45 L58 40 Z
             M85 85 L58 60 L55 55 L60 58 Z
             M15 85 L40 58 L45 55 L42 60 Z
             M15 15 L42 40 L45 45 L40 42 Z"
        />
        {/* Center circle */}
        <circle cx="50" cy="50" r="8" fill={color} />
      </svg>
    </div>
  );
}
