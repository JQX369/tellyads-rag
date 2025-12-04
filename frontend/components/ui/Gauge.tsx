"use client";

import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";

interface GaugeProps {
  value: number; // 0-10 scale
  label: string;
  description?: string;
  size?: "sm" | "md" | "lg";
  animated?: boolean;
  className?: string;
}

export function Gauge({
  value,
  label,
  description,
  size = "md",
  animated = true,
  className,
}: GaugeProps) {
  const [displayValue, setDisplayValue] = useState(animated ? 0 : value);
  const gaugeRef = useRef<HTMLDivElement>(null);
  const hasAnimated = useRef(false);

  // Convert 0-10 scale to percentage
  const percentage = (displayValue / 10) * 100;

  // Size configurations
  const sizes = {
    sm: { size: 80, stroke: 6, fontSize: "text-lg" },
    md: { size: 120, stroke: 8, fontSize: "text-2xl" },
    lg: { size: 160, stroke: 10, fontSize: "text-3xl" },
  };

  const config = sizes[size];
  const radius = (config.size - config.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  useEffect(() => {
    if (!animated || hasAnimated.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasAnimated.current) {
            hasAnimated.current = true;

            // Animate value with spring-like easing
            const duration = 1200;
            const startTime = performance.now();

            const animate = (currentTime: number) => {
              const elapsed = currentTime - startTime;
              const progress = Math.min(elapsed / duration, 1);

              // Spring easing
              const eased = 1 - Math.pow(1 - progress, 4);
              const currentValue = eased * value;

              setDisplayValue(currentValue);

              if (progress < 1) {
                requestAnimationFrame(animate);
              }
            };

            requestAnimationFrame(animate);
          }
        });
      },
      { threshold: 0.5 }
    );

    if (gaugeRef.current) {
      observer.observe(gaugeRef.current);
    }

    return () => observer.disconnect();
  }, [animated, value]);

  // Color based on value
  const getColor = () => {
    if (value >= 7) return "#E63946"; // transmission red
    if (value >= 5) return "#FAF3E8"; // warm white
    return "#6B6B6B"; // antenna gray
  };

  return (
    <div
      ref={gaugeRef}
      className={clsx(
        "flex flex-col items-center gap-2",
        className
      )}
    >
      <div
        className="relative"
        style={{ width: config.size, height: config.size }}
      >
        <svg
          width={config.size}
          height={config.size}
          viewBox={`0 0 ${config.size} ${config.size}`}
          className="transform -rotate-90"
        >
          {/* Background ring */}
          <circle
            cx={config.size / 2}
            cy={config.size / 2}
            r={radius}
            fill="none"
            stroke="#2B2B2B"
            strokeWidth={config.stroke}
          />
          {/* Value ring */}
          <circle
            cx={config.size / 2}
            cy={config.size / 2}
            r={radius}
            fill="none"
            stroke={getColor()}
            strokeWidth={config.stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{
              transition: animated ? "stroke-dashoffset 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)" : "none",
            }}
          />
        </svg>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={clsx("font-display font-bold text-signal", config.fontSize)}>
            {displayValue.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Label */}
      <div className="text-center">
        <p className="font-mono text-label uppercase tracking-ultra-wide text-signal">
          {label}
        </p>
        {description && (
          <p className="font-mono text-xs text-antenna mt-1 max-w-[120px]">
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
