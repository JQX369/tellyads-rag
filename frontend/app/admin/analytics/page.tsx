"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Badge } from "@/components/ui";

// ============================================================================
// Types
// ============================================================================

interface OverviewMetrics {
  events_today: number;
  sessions_today: number;
  pageviews_today: number;
  searches_today: number;
  pageviews_7d: number;
  sessions_7d: number;
  searches_7d: number;
  ad_views_7d: number;
  pageviews_trend: number | null;
  sessions_trend: number | null;
  searches_trend: number | null;
  avg_search_rate: number | null;
  avg_view_rate: number | null;
  avg_engagement_rate: number | null;
}

interface DailyDataPoint {
  date: string;
  pageviews: number;
  sessions: number;
  searches: number;
  ad_views: number;
}

interface SearchQuery {
  query: string;
  count: number;
  unique_sessions: number;
  avg_results: number | null;
  zero_result_count: number;
}

interface SearchData {
  top_queries: SearchQuery[];
  zero_result_queries: Array<{ query: string; count: number }>;
  total_searches: number;
  unique_queries: number;
  zero_result_rate: number;
}

interface TopAd {
  ad_id: string;
  external_id: string;
  brand_name: string;
  views: number;
}

interface ContentData {
  top_ads: TopAd[];
  top_brands: Array<{ brand: string; views: number }>;
  total_ad_views: number;
  unique_ads_viewed: number;
}

interface PipelineData {
  jobs_queued: number;
  jobs_running: number;
  jobs_completed_24h: number;
  jobs_failed_24h: number;
  total_ads: number;
  ads_with_embeddings: number;
  ads_with_transcripts: number;
  ads_missing_embeddings: number;
  recent_errors: Array<{ error_code: string; count: number; last_seen: string }>;
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdminAnalytics() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "search" | "content" | "pipeline">("overview");

  // Data states
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [dailyData, setDailyData] = useState<DailyDataPoint[]>([]);
  const [searchData, setSearchData] = useState<SearchData | null>(null);
  const [contentData, setContentData] = useState<ContentData | null>(null);
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);

  // Check auth on mount
  useEffect(() => {
    const storedKey = sessionStorage.getItem("admin_key");
    if (storedKey) {
      setIsAuthenticated(true);
      fetchData(storedKey);
    } else {
      window.location.href = "/admin";
    }
  }, []);

  const getAdminKey = () => sessionStorage.getItem("admin_key") || "";

  const fetchData = async (key: string) => {
    setLoading(true);
    const headers = { "x-admin-key": key };

    try {
      // Fetch all data in parallel
      const [overviewRes, dailyRes, searchRes, contentRes, pipelineRes] = await Promise.all([
        fetch("/api/admin/analytics/overview", { headers }),
        fetch("/api/admin/analytics/daily?days=30", { headers }),
        fetch("/api/admin/analytics/search?days=7", { headers }),
        fetch("/api/admin/analytics/content?days=7", { headers }),
        fetch("/api/admin/analytics/pipeline", { headers }),
      ]);

      if (overviewRes.ok) setOverview(await overviewRes.json());
      if (dailyRes.ok) {
        const data = await dailyRes.json();
        setDailyData(data.data || []);
      }
      if (searchRes.ok) setSearchData(await searchRes.json());
      if (contentRes.ok) setContentData(await contentRes.json());
      if (pipelineRes.ok) setPipelineData(await pipelineRes.json());
    } catch (error) {
      console.error("Failed to fetch analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="starburst" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-void">
      {/* Header */}
      <header className="border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-transmission rounded-sm flex items-center justify-center">
                <span className="font-display text-sm font-bold text-signal">T</span>
              </div>
              <span className="font-display font-bold text-signal">TellyAds</span>
            </Link>
            <Badge variant="transmission">Analytics</Badge>
          </div>
          <Link
            href="/admin"
            className="font-mono text-sm text-antenna hover:text-signal transition-colors"
          >
            Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-display text-display-md font-bold text-signal mb-2">
            Analytics
          </h1>
          <p className="font-mono text-antenna mb-8">
            Internal metrics and decision dashboard
          </p>

          {/* Tabs */}
          <div className="flex gap-2 mb-8 border-b border-white/10 pb-4">
            {(["overview", "search", "content", "pipeline"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={clsx(
                  "px-4 py-2 font-mono text-sm rounded transition-colors",
                  activeTab === tab
                    ? "bg-transmission text-signal"
                    : "bg-static/30 text-antenna hover:text-signal"
                )}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-24">
              <div className="starburst" />
            </div>
          ) : (
            <>
              {activeTab === "overview" && <OverviewTab overview={overview} dailyData={dailyData} />}
              {activeTab === "search" && <SearchTab data={searchData} />}
              {activeTab === "content" && <ContentTab data={contentData} />}
              {activeTab === "pipeline" && <PipelineTab data={pipelineData} />}
            </>
          )}
        </motion.div>
      </main>
    </div>
  );
}

// ============================================================================
// Overview Tab
// ============================================================================

function OverviewTab({
  overview,
  dailyData,
}: {
  overview: OverviewMetrics | null;
  dailyData: DailyDataPoint[];
}) {
  if (!overview) {
    return <EmptyState message="No analytics data yet. Start tracking events to see metrics." />;
  }

  return (
    <div className="space-y-8">
      {/* Today's Metrics */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Today
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Events" value={overview.events_today} />
          <MetricCard label="Sessions" value={overview.sessions_today} />
          <MetricCard label="Pageviews" value={overview.pageviews_today} />
          <MetricCard label="Searches" value={overview.searches_today} />
        </div>
      </section>

      {/* 7 Day Metrics */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Last 7 Days
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Pageviews"
            value={overview.pageviews_7d}
            trend={overview.pageviews_trend}
          />
          <MetricCard
            label="Sessions"
            value={overview.sessions_7d}
            trend={overview.sessions_trend}
          />
          <MetricCard
            label="Searches"
            value={overview.searches_7d}
            trend={overview.searches_trend}
          />
          <MetricCard label="Ad Views" value={overview.ad_views_7d} />
        </div>
      </section>

      {/* Funnel Rates */}
      {(overview.avg_search_rate !== null || overview.avg_view_rate !== null) && (
        <section>
          <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
            Funnel (7-day avg)
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Search Rate"
              value={overview.avg_search_rate !== null ? `${(overview.avg_search_rate * 100).toFixed(1)}%` : "N/A"}
            />
            <MetricCard
              label="View Rate"
              value={overview.avg_view_rate !== null ? `${(overview.avg_view_rate * 100).toFixed(1)}%` : "N/A"}
            />
            <MetricCard
              label="Engagement Rate"
              value={overview.avg_engagement_rate !== null ? `${(overview.avg_engagement_rate * 100).toFixed(1)}%` : "N/A"}
            />
          </div>
        </section>
      )}

      {/* Sparkline Chart */}
      {dailyData.length > 0 && (
        <section>
          <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
            30-Day Trend
          </h2>
          <div className="bg-static/30 rounded-lg border border-white/5 p-6">
            <BarChart data={dailyData.map((d) => d.pageviews)} labels={dailyData.map((d) => d.date)} />
            <div className="mt-2 text-center font-mono text-xs text-antenna">
              Daily Pageviews
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// Search Tab
// ============================================================================

function SearchTab({ data }: { data: SearchData | null }) {
  if (!data || data.top_queries.length === 0) {
    return <EmptyState message="No search data yet. Searches will appear here once users start searching." />;
  }

  return (
    <div className="space-y-8">
      {/* Summary */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Search Summary (7 days)
        </h2>
        <div className="grid grid-cols-3 gap-4">
          <MetricCard label="Total Searches" value={data.total_searches} />
          <MetricCard label="Unique Queries" value={data.unique_queries} />
          <MetricCard
            label="Zero Result Rate"
            value={`${data.zero_result_rate.toFixed(1)}%`}
            isNegative={data.zero_result_rate > 10}
          />
        </div>
      </section>

      {/* Top Queries */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Top Queries
        </h2>
        <div className="bg-static/30 rounded-lg border border-white/5 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="px-4 py-3 text-left font-mono text-xs uppercase text-antenna">Query</th>
                <th className="px-4 py-3 text-right font-mono text-xs uppercase text-antenna">Count</th>
                <th className="px-4 py-3 text-right font-mono text-xs uppercase text-antenna">Avg Results</th>
              </tr>
            </thead>
            <tbody>
              {data.top_queries.slice(0, 15).map((q, i) => (
                <tr key={i} className="border-b border-white/5 last:border-0">
                  <td className="px-4 py-3 font-mono text-sm text-signal">{q.query}</td>
                  <td className="px-4 py-3 font-mono text-sm text-antenna text-right">{q.count}</td>
                  <td className="px-4 py-3 font-mono text-sm text-antenna text-right">
                    {q.avg_results !== null ? q.avg_results.toFixed(1) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Zero Result Queries */}
      {data.zero_result_queries.length > 0 && (
        <section>
          <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
            Zero-Result Queries (Content Gaps)
          </h2>
          <div className="flex flex-wrap gap-2">
            {data.zero_result_queries.map((q, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-transmission/20 border border-transmission/30 rounded font-mono text-sm text-transmission"
              >
                {q.query} ({q.count})
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// Content Tab
// ============================================================================

function ContentTab({ data }: { data: ContentData | null }) {
  if (!data || data.top_ads.length === 0) {
    return <EmptyState message="No content engagement data yet. Ad views will appear here." />;
  }

  return (
    <div className="space-y-8">
      {/* Summary */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Content Summary (7 days)
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard label="Total Ad Views" value={data.total_ad_views} />
          <MetricCard label="Unique Ads Viewed" value={data.unique_ads_viewed} />
        </div>
      </section>

      {/* Top Ads */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Top Viewed Ads
        </h2>
        <div className="bg-static/30 rounded-lg border border-white/5 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="px-4 py-3 text-left font-mono text-xs uppercase text-antenna">Ad</th>
                <th className="px-4 py-3 text-left font-mono text-xs uppercase text-antenna">Brand</th>
                <th className="px-4 py-3 text-right font-mono text-xs uppercase text-antenna">Views</th>
              </tr>
            </thead>
            <tbody>
              {data.top_ads.map((ad, i) => (
                <tr key={i} className="border-b border-white/5 last:border-0">
                  <td className="px-4 py-3">
                    <Link
                      href={`/ads/${ad.external_id}`}
                      className="font-mono text-sm text-signal hover:text-transmission transition-colors"
                    >
                      {ad.external_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-sm text-antenna">{ad.brand_name}</td>
                  <td className="px-4 py-3 font-mono text-sm text-antenna text-right">{ad.views}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Top Brands */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Top Brands by Views
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {data.top_brands.slice(0, 10).map((brand, i) => (
            <div
              key={i}
              className="p-4 bg-static/30 rounded border border-white/5"
            >
              <div className="font-mono text-sm text-signal truncate">{brand.brand}</div>
              <div className="font-display text-xl font-bold text-transmission">{brand.views}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// ============================================================================
// Pipeline Tab
// ============================================================================

function PipelineTab({ data }: { data: PipelineData | null }) {
  if (!data) {
    return <EmptyState message="Pipeline data unavailable." />;
  }

  const embeddingCoverage = data.total_ads > 0
    ? ((data.ads_with_embeddings / data.total_ads) * 100).toFixed(1)
    : "0";

  return (
    <div className="space-y-8">
      {/* Job Queue */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Job Queue
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Queued" value={data.jobs_queued} />
          <MetricCard label="Running" value={data.jobs_running} />
          <MetricCard label="Completed (24h)" value={data.jobs_completed_24h} />
          <MetricCard
            label="Failed (24h)"
            value={data.jobs_failed_24h}
            isNegative={data.jobs_failed_24h > 0}
          />
        </div>
      </section>

      {/* Data Quality */}
      <section>
        <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
          Data Quality
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="Total Ads" value={data.total_ads} />
          <MetricCard label="With Embeddings" value={data.ads_with_embeddings} />
          <MetricCard label="Embedding Coverage" value={`${embeddingCoverage}%`} />
          <MetricCard
            label="Missing Embeddings"
            value={data.ads_missing_embeddings}
            isNegative={data.ads_missing_embeddings > 0}
          />
        </div>
      </section>

      {/* Recent Errors */}
      {data.recent_errors.length > 0 && (
        <section>
          <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
            Recent Errors (7 days)
          </h2>
          <div className="bg-static/30 rounded-lg border border-white/5 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-3 text-left font-mono text-xs uppercase text-antenna">Error Code</th>
                  <th className="px-4 py-3 text-right font-mono text-xs uppercase text-antenna">Count</th>
                  <th className="px-4 py-3 text-right font-mono text-xs uppercase text-antenna">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_errors.map((err, i) => (
                  <tr key={i} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-3 font-mono text-sm text-transmission">{err.error_code}</td>
                    <td className="px-4 py-3 font-mono text-sm text-antenna text-right">{err.count}</td>
                    <td className="px-4 py-3 font-mono text-sm text-antenna text-right">
                      {new Date(err.last_seen).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// Shared Components
// ============================================================================

function MetricCard({
  label,
  value,
  trend,
  isNegative,
}: {
  label: string;
  value: number | string;
  trend?: number | null;
  isNegative?: boolean;
}) {
  const displayValue = typeof value === "number" ? value.toLocaleString() : value;

  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mb-2">
        {label}
      </div>
      <div
        className={clsx(
          "font-display text-2xl font-bold",
          isNegative ? "text-transmission" : "text-signal"
        )}
      >
        {displayValue}
      </div>
      {trend !== null && trend !== undefined && (
        <div
          className={clsx(
            "font-mono text-xs mt-1",
            trend > 0 ? "text-green-400" : trend < 0 ? "text-transmission" : "text-antenna"
          )}
        >
          {trend > 0 ? "+" : ""}
          {trend.toFixed(1)}% vs prev
        </div>
      )}
    </div>
  );
}

function BarChart({ data, labels }: { data: number[]; labels: string[] }) {
  if (data.length === 0) return null;

  const max = Math.max(...data, 1);
  const barWidth = 100 / data.length;

  return (
    <div className="h-32 flex items-end gap-1">
      {data.map((value, i) => (
        <div
          key={i}
          className="flex-1 bg-transmission/60 hover:bg-transmission transition-colors rounded-t"
          style={{ height: `${(value / max) * 100}%` }}
          title={`${labels[i]}: ${value}`}
        />
      ))}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-24">
      <div className="text-4xl mb-4">📊</div>
      <p className="font-mono text-antenna">{message}</p>
    </div>
  );
}
