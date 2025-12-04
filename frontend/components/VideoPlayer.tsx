"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { clsx } from "clsx";
import { OnAirLight } from "@/components/ui";

interface VideoPlayerProps {
  videoUrl?: string;
  posterUrl?: string;
  adId: string;
}

export function VideoPlayer({ videoUrl, posterUrl, adId }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [showControls, setShowControls] = useState(true);
  const [watermarkPosition, setWatermarkPosition] = useState({ x: 20, y: 20 });
  const controlsTimeout = useRef<NodeJS.Timeout | null>(null);

  // Generate session-based watermark ID (anti-scraping measure)
  const [sessionId] = useState(() => {
    if (typeof window !== "undefined") {
      const existing = sessionStorage.getItem("ta_session");
      if (existing) return existing;
      const newId = Math.random().toString(36).substring(2, 8).toUpperCase();
      sessionStorage.setItem("ta_session", newId);
      return newId;
    }
    return "XXXXXX";
  });

  // Randomize watermark position periodically (anti-scraping)
  useEffect(() => {
    const interval = setInterval(() => {
      setWatermarkPosition({
        x: 10 + Math.random() * 80,
        y: 10 + Math.random() * 80,
      });
    }, 30000); // Change position every 30 seconds

    return () => clearInterval(interval);
  }, []);

  // Hide controls after inactivity
  const resetControlsTimeout = useCallback(() => {
    setShowControls(true);
    if (controlsTimeout.current) {
      clearTimeout(controlsTimeout.current);
    }
    if (isPlaying) {
      controlsTimeout.current = setTimeout(() => {
        setShowControls(false);
      }, 3000);
    }
  }, [isPlaying]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener("mousemove", resetControlsTimeout);
    container.addEventListener("mouseenter", resetControlsTimeout);

    return () => {
      container.removeEventListener("mousemove", resetControlsTimeout);
      container.removeEventListener("mouseenter", resetControlsTimeout);
    };
  }, [resetControlsTimeout]);

  // Disable right-click on video (anti-scraping)
  useEffect(() => {
    const handleContextMenu = (e: Event) => {
      e.preventDefault();
      return false;
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener("contextmenu", handleContextMenu);
    }

    return () => {
      if (container) {
        container.removeEventListener("contextmenu", handleContextMenu);
      }
    };
  }, []);

  const togglePlay = () => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const current = videoRef.current.currentTime;
    const total = videoRef.current.duration;
    setCurrentTime(current);
    setProgress((current / total) * 100);
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setDuration(videoRef.current.duration);
    setIsLoading(false);
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    videoRef.current.currentTime = percent * videoRef.current.duration;
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  if (!videoUrl) {
    return (
      <div className="video-container aspect-video flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-static flex items-center justify-center">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-antenna"
            >
              <rect x="2" y="7" width="20" height="14" rx="2" />
              <polyline points="7 2 12 7 17 2" />
            </svg>
          </div>
          <p className="font-mono text-sm text-antenna">Video Unavailable</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={clsx(
        "video-container relative aspect-video group",
        "bg-void rounded-lg overflow-hidden",
        "border border-white/5"
      )}
      style={{ userSelect: "none" }}
    >
      {/* Video element */}
      <video
        ref={videoRef}
        src={videoUrl}
        poster={posterUrl}
        className="w-full h-full object-contain"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onWaiting={() => setIsLoading(true)}
        onCanPlay={() => setIsLoading(false)}
        playsInline
        // Anti-scraping: disable download
        controlsList="nodownload nofullscreen noremoteplayback"
        disablePictureInPicture
      />

      {/* Dynamic watermark (anti-scraping) */}
      <div
        className="absolute pointer-events-none select-none opacity-30 font-mono text-xs text-white/50"
        style={{
          left: `${watermarkPosition.x}%`,
          top: `${watermarkPosition.y}%`,
          transform: "translate(-50%, -50%)",
          textShadow: "0 1px 2px rgba(0,0,0,0.5)",
        }}
      >
        {sessionId} · TellyAds
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-void/50">
          <div className="starburst" style={{ "--starburst-size": "50px" } as React.CSSProperties} />
        </div>
      )}

      {/* Play/Pause overlay */}
      <div
        className={clsx(
          "absolute inset-0 flex items-center justify-center cursor-pointer",
          "transition-opacity duration-300",
          isPlaying && !showControls ? "opacity-0" : "opacity-100"
        )}
        onClick={togglePlay}
      >
        {!isPlaying && !isLoading && (
          <div className="w-20 h-20 rounded-full bg-transmission/90 flex items-center justify-center transform hover:scale-110 transition-transform">
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="white"
              className="ml-1"
            >
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
        )}
      </div>

      {/* Custom controls */}
      <div
        className={clsx(
          "absolute bottom-0 left-0 right-0 p-4",
          "bg-gradient-to-t from-void/90 to-transparent",
          "transition-opacity duration-300",
          showControls || !isPlaying ? "opacity-100" : "opacity-0"
        )}
      >
        {/* Progress bar */}
        <div
          className="h-1 bg-white/20 rounded-full cursor-pointer mb-3 group/progress"
          onClick={handleSeek}
        >
          <div
            className="h-full bg-transmission rounded-full relative"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-signal rounded-full opacity-0 group-hover/progress:opacity-100 transition-opacity" />
          </div>
        </div>

        {/* Controls row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Play/Pause button */}
            <button
              onClick={togglePlay}
              className="text-signal hover:text-transmission transition-colors"
            >
              {isPlaying ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              )}
            </button>

            {/* Time display */}
            <span className="font-mono text-xs text-signal">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* ON AIR indicator */}
          {isPlaying && <OnAirLight text="Playing" />}
        </div>
      </div>

      {/* Film frame borders (decorative) */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-transmission/30" />
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-transmission/30" />
    </div>
  );
}
