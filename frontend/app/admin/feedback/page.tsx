"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { Button, Badge } from "@/components/ui";

interface LeaderboardEntry {
  ad_id: string;
  external_id: string;
  brand: string | null;
  title: string | null;
  weighted_score: number;
  time_decayed_score: number;
  total_views: number;
  rating_avg: number | null;
  rating_count: number;
  likes: number;
  rank_by_score: number;
  score_percentile: number;
}

interface PendingReview {
  id: string;
  ad_id: string;
  external_id: string;
  brand: string | null;
  title: string | null;
  rating: number;
  review_text: string;
  created_at: string;
  session_id: string;
  reported_count: number;
}

interface WeightConfig {
  id: string;
  config_key: string;
  name: string;
  description: string | null;
  is_active: boolean;
  weight_views: number;
  weight_unique_views: number;
  weight_completions: number;
  weight_likes: number;
  weight_saves: number;
  weight_shares: number;
  weight_rating: number;
  weight_review: number;
  decay_half_life_days: number;
  recency_boost_days: number;
  recency_boost_multiplier: number;
  created_at: string;
  updated_at: string;
}

interface FeedbackStats {
  total_ads: number;
  ads_with_views: number;
  ads_with_ratings: number;
  total_views: number;
  total_ratings: number;
  avg_rating: number | null;
  last_refresh: string | null;
}

type TabType = "overview" | "weights" | "reviews";

export default function FeedbackPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [refreshing, setRefreshing] = useState(false);

  // Data state
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [pendingReviews, setPendingReviews] = useState<PendingReview[]>([]);
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [config, setConfig] = useState<WeightConfig | null>(null);
  const [editingConfig, setEditingConfig] = useState<Partial<WeightConfig> | null>(null);

  const getAdminKey = () => sessionStorage.getItem("admin_key") || "";

  useEffect(() => {
    const key = sessionStorage.getItem("admin_key");
    if (key) {
      setIsAuthenticated(true);
      fetchData(key);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchData = useCallback(async (key: string) => {
    try {
      const res = await fetch("/api/admin/feedback", {
        headers: { "x-admin-key": key },
      });
      if (res.ok) {
        const data = await res.json();
        setLeaderboard(data.leaderboard || []);
        setPendingReviews(data.pendingReviews || []);
        setStats(data.stats || null);
        setConfig(data.config || null);
      }
    } catch (e) {
      console.error("Failed to fetch feedback data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRefreshMetrics = async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/admin/feedback", {
        method: "POST",
        headers: {
          "x-admin-key": getAdminKey(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "refresh" }),
      });
      if (res.ok) {
        const data = await res.json();
        alert(`Refreshed ${data.updated} ads`);
        fetchData(getAdminKey());
      }
    } catch (e) {
      console.error("Failed to refresh metrics:", e);
    } finally {
      setRefreshing(false);
    }
  };

  const handleSaveWeights = async () => {
    if (!editingConfig) return;

    try {
      const res = await fetch("/api/admin/feedback/weights", {
        method: "PUT",
        headers: {
          "x-admin-key": getAdminKey(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(editingConfig),
      });
      if (res.ok) {
        const data = await res.json();
        setConfig(data.config);
        setEditingConfig(null);
        alert("Weights saved! Click 'Refresh Metrics' to apply to all ads.");
      }
    } catch (e) {
      console.error("Failed to save weights:", e);
    }
  };

  const handleModerateReview = async (reviewId: string, action: "approve" | "reject" | "flag") => {
    try {
      const res = await fetch("/api/admin/feedback/reviews", {
        method: "POST",
        headers: {
          "x-admin-key": getAdminKey(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ review_id: reviewId, action }),
      });
      if (res.ok) {
        setPendingReviews((prev) => prev.filter((r) => r.id !== reviewId));
      }
    } catch (e) {
      console.error("Failed to moderate review:", e);
    }
  };

  if (!isAuthenticated && !loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center p-6">
        <div className="text-center">
          <h1 className="font-display text-2xl font-bold text-signal mb-4">Authentication Required</h1>
          <p className="font-mono text-antenna mb-6">Please login from the admin dashboard first.</p>
          <Link href="/admin"><Button variant="primary">Go to Admin Login</Button></Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="starburst" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-void">
      <header className="border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-transmission rounded-sm flex items-center justify-center">
                <span className="font-display text-sm font-bold text-signal">T</span>
              </div>
              <span className="font-display font-bold text-signal">TellyAds</span>
            </Link>
            <Badge variant="transmission">Feedback</Badge>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              onClick={handleRefreshMetrics}
              disabled={refreshing}
            >
              {refreshing ? "Refreshing..." : "Refresh Metrics"}
            </Button>
            <Button variant="ghost" onClick={() => fetchData(getAdminKey())}>Reload</Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-display text-display-md font-bold text-signal mb-2">Feedback & Scoring</h1>
              <p className="font-mono text-antenna">Configure weights, moderate reviews, view leaderboard</p>
            </div>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
              <StatCard label="Total Ads" value={stats.total_ads} />
              <StatCard label="With Views" value={stats.ads_with_views} />
              <StatCard label="With Ratings" value={stats.ads_with_ratings} />
              <StatCard label="Total Views" value={stats.total_views} />
              <StatCard label="Total Ratings" value={stats.total_ratings} />
              <StatCard
                label="Avg Rating"
                value={stats.avg_rating ? stats.avg_rating.toFixed(2) : "-"}
                isText
              />
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-white/10 pb-4">
            <TabButton active={activeTab === "overview"} onClick={() => setActiveTab("overview")}>
              Leaderboard
            </TabButton>
            <TabButton active={activeTab === "weights"} onClick={() => setActiveTab("weights")}>
              Weights Config
            </TabButton>
            <TabButton
              active={activeTab === "reviews"}
              onClick={() => setActiveTab("reviews")}
              count={pendingReviews.length}
              variant={pendingReviews.length > 0 ? "warning" : undefined}
            >
              Pending Reviews
            </TabButton>
          </div>

          <AnimatePresence mode="wait">
            {activeTab === "overview" && (
              <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <LeaderboardTable entries={leaderboard} />
              </motion.div>
            )}

            {activeTab === "weights" && (
              <motion.div key="weights" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <WeightsEditor
                  config={config}
                  editing={editingConfig}
                  onEdit={(updates) => setEditingConfig({ ...editingConfig, ...updates })}
                  onSave={handleSaveWeights}
                  onCancel={() => setEditingConfig(null)}
                  onStartEdit={() => setEditingConfig(config ? { config_key: config.config_key } : null)}
                />
              </motion.div>
            )}

            {activeTab === "reviews" && (
              <motion.div key="reviews" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <ReviewsList reviews={pendingReviews} onModerate={handleModerateReview} />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-12 pt-8 border-t border-white/10">
            <Link href="/admin" className="font-mono text-sm text-antenna hover:text-signal transition-colors">&larr; Back to Dashboard</Link>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function StatCard({ label, value, isText = false }: { label: string; value: number | string; isText?: boolean }) {
  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className={clsx("font-display font-bold text-signal", isText ? "text-xl" : "text-2xl")}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mt-1">{label}</div>
    </div>
  );
}

function TabButton({ children, active, onClick, count, variant }: { children: React.ReactNode; active: boolean; onClick: () => void; count?: number; variant?: "warning" }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "px-4 py-2 font-mono text-sm rounded-t transition-colors flex items-center gap-2",
        active ? "bg-static/50 text-signal border-b-2 border-transmission" : "text-antenna hover:text-signal"
      )}
    >
      {children}
      {count !== undefined && count > 0 && (
        <span className={clsx(
          "px-2 py-0.5 rounded-full text-xs",
          variant === "warning" ? "bg-yellow-500/20 text-yellow-400" : "bg-white/10 text-antenna"
        )}>{count}</span>
      )}
    </button>
  );
}

function LeaderboardTable({ entries }: { entries: LeaderboardEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5">
        <p className="font-mono text-antenna">No feedback data yet. Run "Refresh Metrics" to populate.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10">
            <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Rank</th>
            <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Ad</th>
            <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Brand</th>
            <th className="text-right py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Score</th>
            <th className="text-right py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Views</th>
            <th className="text-right py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Rating</th>
            <th className="text-right py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Likes</th>
            <th className="text-right py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Percentile</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.ad_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
              <td className="py-3 px-2 font-mono text-signal">#{entry.rank_by_score}</td>
              <td className="py-3 px-2 font-mono text-signal max-w-[200px] truncate">
                <Link href={`/advert/${entry.external_id}`} className="hover:text-transmission">
                  {entry.title || entry.external_id}
                </Link>
              </td>
              <td className="py-3 px-2 font-mono text-antenna">{entry.brand || "-"}</td>
              <td className="py-3 px-2 font-mono text-signal text-right">{entry.weighted_score.toFixed(1)}</td>
              <td className="py-3 px-2 font-mono text-antenna text-right">{entry.total_views.toLocaleString()}</td>
              <td className="py-3 px-2 font-mono text-antenna text-right">
                {entry.rating_avg ? `${entry.rating_avg.toFixed(1)} (${entry.rating_count})` : "-"}
              </td>
              <td className="py-3 px-2 font-mono text-antenna text-right">{entry.likes}</td>
              <td className="py-3 px-2 text-right">
                <span className={clsx(
                  "px-2 py-0.5 rounded text-xs font-mono",
                  entry.score_percentile >= 90 ? "bg-green-500/20 text-green-400" :
                  entry.score_percentile >= 50 ? "bg-blue-500/20 text-blue-400" :
                  "bg-gray-500/20 text-gray-400"
                )}>
                  {entry.score_percentile?.toFixed(0)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WeightsEditor({
  config,
  editing,
  onEdit,
  onSave,
  onCancel,
  onStartEdit,
}: {
  config: WeightConfig | null;
  editing: Partial<WeightConfig> | null;
  onEdit: (updates: Partial<WeightConfig>) => void;
  onSave: () => void;
  onCancel: () => void;
  onStartEdit: () => void;
}) {
  if (!config) {
    return (
      <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5">
        <p className="font-mono text-antenna">No weight configuration found.</p>
      </div>
    );
  }

  const isEditing = editing !== null;
  const getValue = (field: keyof WeightConfig) =>
    isEditing && editing[field] !== undefined ? editing[field] : config[field];

  const weightFields: Array<{ key: keyof WeightConfig; label: string; description: string }> = [
    { key: "weight_views", label: "Views", description: "Weight for total view count" },
    { key: "weight_unique_views", label: "Unique Views", description: "Weight for unique visitors" },
    { key: "weight_completions", label: "Completions", description: "Weight for watch completions" },
    { key: "weight_likes", label: "Likes", description: "Weight for like count" },
    { key: "weight_saves", label: "Saves", description: "Weight for save count" },
    { key: "weight_shares", label: "Shares", description: "Weight for share count" },
    { key: "weight_rating", label: "Rating", description: "Weight for star ratings" },
    { key: "weight_review", label: "Reviews", description: "Weight for written reviews" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-display text-xl font-bold text-signal">{config.name}</h2>
          <p className="font-mono text-sm text-antenna">{config.description}</p>
        </div>
        {!isEditing ? (
          <Button variant="primary" onClick={onStartEdit}>Edit Weights</Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onCancel}>Cancel</Button>
            <Button variant="primary" onClick={onSave}>Save Changes</Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {weightFields.map(({ key, label, description }) => (
          <div key={key} className="p-4 bg-static/30 rounded-lg border border-white/5">
            <div className="flex justify-between items-center mb-2">
              <span className="font-mono text-sm text-signal">{label}</span>
              {isEditing ? (
                <input
                  type="number"
                  min="0"
                  max="10"
                  step="0.5"
                  value={getValue(key) as number}
                  onChange={(e) => onEdit({ [key]: parseFloat(e.target.value) })}
                  className="w-20 bg-void border border-white/20 rounded px-2 py-1 font-mono text-sm text-signal text-right focus:outline-none focus:border-transmission"
                />
              ) : (
                <span className="font-display text-2xl text-signal">{String(config[key])}</span>
              )}
            </div>
            <p className="font-mono text-xs text-antenna">{description}</p>
          </div>
        ))}
      </div>

      <div className="p-4 bg-static/30 rounded-lg border border-white/5">
        <h3 className="font-display text-lg font-bold text-signal mb-4">Time Decay Settings</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block font-mono text-xs text-antenna mb-1">Half-life (days)</label>
            {isEditing ? (
              <input
                type="number"
                min="1"
                value={getValue("decay_half_life_days") as number}
                onChange={(e) => onEdit({ decay_half_life_days: parseInt(e.target.value) })}
                className="w-full bg-void border border-white/20 rounded px-3 py-2 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
              />
            ) : (
              <span className="font-mono text-lg text-signal">{config.decay_half_life_days} days</span>
            )}
          </div>
          <div>
            <label className="block font-mono text-xs text-antenna mb-1">Recency Boost (days)</label>
            {isEditing ? (
              <input
                type="number"
                min="0"
                value={getValue("recency_boost_days") as number}
                onChange={(e) => onEdit({ recency_boost_days: parseInt(e.target.value) })}
                className="w-full bg-void border border-white/20 rounded px-3 py-2 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
              />
            ) : (
              <span className="font-mono text-lg text-signal">{config.recency_boost_days} days</span>
            )}
          </div>
          <div>
            <label className="block font-mono text-xs text-antenna mb-1">Boost Multiplier</label>
            {isEditing ? (
              <input
                type="number"
                min="1"
                step="0.1"
                value={getValue("recency_boost_multiplier") as number}
                onChange={(e) => onEdit({ recency_boost_multiplier: parseFloat(e.target.value) })}
                className="w-full bg-void border border-white/20 rounded px-3 py-2 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
              />
            ) : (
              <span className="font-mono text-lg text-signal">{config.recency_boost_multiplier}x</span>
            )}
          </div>
        </div>
      </div>

      <p className="font-mono text-xs text-antenna">
        Last updated: {new Date(config.updated_at).toLocaleString()}
      </p>
    </div>
  );
}

function ReviewsList({
  reviews,
  onModerate,
}: {
  reviews: PendingReview[];
  onModerate: (id: string, action: "approve" | "reject" | "flag") => void;
}) {
  if (reviews.length === 0) {
    return (
      <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5">
        <p className="font-mono text-antenna">No pending reviews to moderate.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {reviews.map((review) => (
        <div key={review.id} className="p-4 bg-static/30 rounded-lg border border-white/5">
          <div className="flex justify-between items-start mb-3">
            <div>
              <Link
                href={`/advert/${review.external_id}`}
                className="font-mono text-signal hover:text-transmission"
              >
                {review.title || review.external_id}
              </Link>
              <span className="text-antenna mx-2">by</span>
              <span className="font-mono text-antenna">{review.brand || "Unknown"}</span>
            </div>
            <div className="flex items-center gap-2">
              <RatingStars rating={review.rating} />
              {review.reported_count > 0 && (
                <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs font-mono">
                  {review.reported_count} reports
                </span>
              )}
            </div>
          </div>

          <div className="p-3 bg-void/50 rounded mb-3">
            <p className="font-mono text-sm text-signal whitespace-pre-wrap">{review.review_text}</p>
          </div>

          <div className="flex justify-between items-center">
            <span className="font-mono text-xs text-antenna">
              {new Date(review.created_at).toLocaleString()}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => onModerate(review.id, "reject")}>
                Reject
              </Button>
              <Button variant="ghost" size="sm" onClick={() => onModerate(review.id, "flag")}>
                Flag
              </Button>
              <Button variant="primary" size="sm" onClick={() => onModerate(review.id, "approve")}>
                Approve
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function RatingStars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <span
          key={star}
          className={clsx(
            "text-lg",
            star <= rating ? "text-yellow-400" : "text-gray-600"
          )}
        >
          ★
        </span>
      ))}
    </div>
  );
}
