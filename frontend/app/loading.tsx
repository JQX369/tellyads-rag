'use client';

export default function Loading() {
  return (
    <div className="min-h-screen bg-void flex items-center justify-center">
      <div className="flex flex-col items-center gap-6">
        {/* Starburst spinner */}
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-2 border-white/10" />
          <div className="absolute inset-0 rounded-full border-2 border-transmission border-t-transparent animate-spin" />
          <div className="absolute inset-2 rounded-full border border-transmission/30 border-t-transparent animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
        </div>
        <span className="font-mono text-sm uppercase tracking-ultra-wide text-antenna animate-pulse">
          Loading...
        </span>
      </div>
    </div>
  );
}
