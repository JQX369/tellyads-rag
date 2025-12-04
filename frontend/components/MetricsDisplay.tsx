"use client";

import { Gauge } from "@/components/ui";

interface Metric {
  key: string;
  label: string;
  value: number;
  description: string;
}

interface MetricsDisplayProps {
  metrics: Metric[];
}

export function MetricsDisplay({ metrics }: MetricsDisplayProps) {
  if (metrics.length === 0) return null;

  return (
    <div className="p-6 bg-static/30 rounded-lg border border-white/5">
      {/* Section header */}
      <div className="flex items-center gap-3 mb-8">
        <span className="w-8 h-px bg-transmission" />
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-transmission">
          Performance Metrics
        </h2>
      </div>

      {/* Gauges grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
        {metrics.map((metric) => (
          <Gauge
            key={metric.key}
            value={metric.value}
            label={metric.label}
            description={metric.description}
            size="md"
            animated
          />
        ))}
      </div>

      {/* Disclaimer */}
      <p className="mt-8 font-mono text-xs text-antenna/60 text-center">
        Scores powered by AI analysis · Scale 0-10
      </p>
    </div>
  );
}
