"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { clsx } from "clsx";

interface SearchInputProps {
  initialQuery?: string;
  autoFocus?: boolean;
}

export function SearchInput({ initialQuery = "", autoFocus = true }: SearchInputProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div
        className={clsx(
          "relative flex items-center",
          "bg-static/50 backdrop-blur-sm",
          "border rounded-lg overflow-hidden",
          "transition-all duration-300",
          isFocused
            ? "border-transmission/50 shadow-[0_0_0_4px_rgba(230,57,70,0.1)]"
            : "border-white/10 hover:border-white/20"
        )}
      >
        {/* Search icon */}
        <div className="pl-4">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={clsx(
              "transition-colors duration-200",
              isFocused ? "text-transmission" : "text-antenna"
            )}
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </div>

        {/* Input */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Search by concept, emotion, or brand..."
          autoFocus={autoFocus}
          className={clsx(
            "flex-1 px-4 py-4",
            "bg-transparent",
            "font-mono text-base text-signal placeholder:text-antenna",
            "focus:outline-none"
          )}
        />

        {/* Submit button */}
        <button
          type="submit"
          disabled={!query.trim()}
          className={clsx(
            "px-6 py-4 font-mono text-sm uppercase tracking-ultra-wide",
            "bg-transmission text-signal",
            "transition-all duration-200",
            "hover:bg-transmission-dark",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          Search
        </button>
      </div>

      {/* Animated accent line */}
      <div
        className={clsx(
          "absolute bottom-0 left-0 h-px bg-transmission",
          "transition-all duration-300",
          isFocused ? "w-full" : "w-0"
        )}
      />
    </form>
  );
}
