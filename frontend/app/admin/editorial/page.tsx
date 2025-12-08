"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Badge, Button } from "@/components/ui";

interface Ad {
  id: number;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  product_category?: string;
  one_line_summary?: string;
  year?: number;
  created_at?: string;
  // Editorial
  editorial_id?: number;
  brand_slug?: string;
  slug?: string;
  headline?: string;
  editorial_status: 'published' | 'draft' | 'none';
  is_hidden: boolean;
  is_featured: boolean;
}

interface Counts {
  total: number;
  with_editorial: number;
  published: number;
  draft: number;
  hidden: number;
}

type FilterType = 'all' | 'published' | 'draft' | 'hidden' | 'unpublished';

export default function EditorialPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState("");
  const [ads, setAds] = useState<Ad[]>([]);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [processing, setProcessing] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Check auth
  useEffect(() => {
    const storedKey = sessionStorage.getItem("admin_key");
    if (!storedKey) {
      router.push("/admin");
    } else {
      setAdminKey(storedKey);
      setIsAuthenticated(true);
    }
  }, [router]);

  // Fetch ads when authenticated or filter changes
  useEffect(() => {
    if (isAuthenticated && adminKey) {
      fetchAds(true);
    }
  }, [isAuthenticated, adminKey, filter]);

  const fetchAds = async (reset: boolean = false) => {
    setLoading(true);
    const newOffset = reset ? 0 : offset;

    try {
      const response = await fetch(
        `/api/admin/editorial?filter=${filter}&limit=50&offset=${newOffset}`,
        {
          headers: { "x-admin-key": adminKey },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (reset) {
          setAds(data.ads);
          setOffset(50);
        } else {
          setAds((prev) => [...prev, ...data.ads]);
          setOffset(newOffset + 50);
        }
        setCounts(data.counts);
        setHasMore(data.ads.length === 50);
      } else if (response.status === 401) {
        router.push("/admin");
      }
    } catch (e) {
      console.error("Failed to fetch ads:", e);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === ads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ads.map((a) => a.id)));
    }
  };

  const bulkAction = async (action: string) => {
    if (selectedIds.size === 0) return;

    setProcessing(true);
    try {
      const response = await fetch("/api/admin/editorial/bulk", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-key": adminKey,
        },
        body: JSON.stringify({
          ad_ids: Array.from(selectedIds),
          action,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log("Bulk action result:", data);
        // Refresh the list
        setSelectedIds(new Set());
        fetchAds(true);
      } else {
        const err = await response.json();
        alert(`Error: ${err.error}`);
      }
    } catch (e) {
      console.error("Bulk action failed:", e);
      alert("Bulk action failed. Check console.");
    } finally {
      setProcessing(false);
    }
  };

  const singleAction = async (adId: number, action: string) => {
    setProcessing(true);
    try {
      const response = await fetch("/api/admin/editorial/bulk", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-key": adminKey,
        },
        body: JSON.stringify({
          ad_ids: [adId],
          action,
        }),
      });

      if (response.ok) {
        fetchAds(true);
      }
    } catch (e) {
      console.error("Action failed:", e);
    } finally {
      setProcessing(false);
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
            <Badge variant="transmission">Editorial</Badge>
          </div>

          <Link
            href="/admin"
            className="font-mono text-sm text-antenna hover:text-signal transition-colors"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          {/* Title & Stats */}
          <div className="mb-8">
            <h1 className="font-display text-display-md font-bold text-signal mb-2">
              Editorial Management
            </h1>
            <p className="font-mono text-antenna mb-6">
              Publish, unpublish, and manage ad visibility
            </p>

            {/* Stats row */}
            {counts && (
              <div className="flex flex-wrap gap-4">
                <StatBadge label="Total" value={counts.total} />
                <StatBadge label="Published" value={counts.published} color="green" />
                <StatBadge label="Draft" value={counts.draft} color="yellow" />
                <StatBadge label="Hidden" value={counts.hidden} color="red" />
                <StatBadge
                  label="No Editorial"
                  value={counts.total - counts.with_editorial}
                  color="gray"
                />
              </div>
            )}
          </div>

          {/* Filter tabs */}
          <div className="flex flex-wrap gap-2 mb-6">
            {(['all', 'published', 'draft', 'hidden', 'unpublished'] as FilterType[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={clsx(
                  "px-4 py-2 font-mono text-sm rounded transition-colors",
                  filter === f
                    ? "bg-transmission text-signal"
                    : "bg-static/50 text-antenna hover:text-signal"
                )}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          {/* Bulk actions bar */}
          {selectedIds.size > 0 && (
            <div className="sticky top-0 z-10 bg-void/95 backdrop-blur border border-white/10 rounded-lg p-4 mb-4 flex flex-wrap items-center gap-4">
              <span className="font-mono text-sm text-signal">
                {selectedIds.size} selected
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => bulkAction("publish")}
                  disabled={processing}
                >
                  Publish
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => bulkAction("unpublish")}
                  disabled={processing}
                >
                  Unpublish
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => bulkAction("hide")}
                  disabled={processing}
                >
                  Hide
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => bulkAction("feature")}
                  disabled={processing}
                >
                  Feature
                </Button>
              </div>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="ml-auto font-mono text-sm text-antenna hover:text-signal"
              >
                Clear
              </button>
            </div>
          )}

          {/* Table */}
          <div className="bg-static/30 rounded-lg border border-white/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={selectedIds.size === ads.length && ads.length > 0}
                        onChange={selectAll}
                        className="w-4 h-4 rounded"
                      />
                    </th>
                    <th className="px-4 py-3 text-left font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Brand / Product
                    </th>
                    <th className="px-4 py-3 text-left font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Year
                    </th>
                    <th className="px-4 py-3 text-left font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Flags
                    </th>
                    <th className="px-4 py-3 text-right font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {loading && ads.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center">
                        <div className="starburst mx-auto" />
                      </td>
                    </tr>
                  ) : ads.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center font-mono text-antenna">
                        No ads found
                      </td>
                    </tr>
                  ) : (
                    ads.map((ad) => (
                      <tr
                        key={ad.id}
                        className={clsx(
                          "border-b border-white/5 transition-colors",
                          selectedIds.has(ad.id)
                            ? "bg-transmission/10"
                            : "hover:bg-static/30"
                        )}
                      >
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(ad.id)}
                            onChange={() => toggleSelect(ad.id)}
                            className="w-4 h-4 rounded"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-display text-signal font-medium">
                            {ad.brand_name || "Unknown Brand"}
                          </div>
                          <div className="font-mono text-xs text-antenna">
                            {ad.product_name || ad.external_id}
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono text-sm text-antenna">
                          {ad.year || "—"}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={ad.editorial_status} isHidden={ad.is_hidden} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            {ad.is_featured && (
                              <Badge variant="transmission">Featured</Badge>
                            )}
                            {ad.is_hidden && (
                              <Badge variant="muted">Hidden</Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {ad.editorial_status === 'published' && !ad.is_hidden ? (
                              <button
                                onClick={() => singleAction(ad.id, "unpublish")}
                                disabled={processing}
                                className="font-mono text-xs text-antenna hover:text-signal"
                              >
                                Unpublish
                              </button>
                            ) : (
                              <button
                                onClick={() => singleAction(ad.id, "publish")}
                                disabled={processing}
                                className="font-mono text-xs text-transmission hover:text-transmission/80"
                              >
                                Publish
                              </button>
                            )}
                            <span className="text-white/20">|</span>
                            <Link
                              href={`/ads/${ad.external_id}`}
                              className="font-mono text-xs text-antenna hover:text-signal"
                            >
                              View
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Load more */}
            {hasMore && ads.length > 0 && (
              <div className="p-4 text-center border-t border-white/5">
                <button
                  onClick={() => fetchAds(false)}
                  disabled={loading}
                  className="font-mono text-sm text-antenna hover:text-signal disabled:opacity-50"
                >
                  {loading ? "Loading..." : "Load more"}
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function StatBadge({
  label,
  value,
  color = "default",
}: {
  label: string;
  value: number;
  color?: "default" | "green" | "yellow" | "red" | "gray";
}) {
  const colorClasses = {
    default: "bg-static/50 text-signal",
    green: "bg-green-900/30 text-green-400",
    yellow: "bg-yellow-900/30 text-yellow-400",
    red: "bg-red-900/30 text-red-400",
    gray: "bg-white/5 text-antenna",
  };

  return (
    <div className={clsx("px-4 py-2 rounded-lg", colorClasses[color])}>
      <span className="font-mono text-xs uppercase tracking-wide opacity-70">{label}</span>
      <span className="ml-2 font-display font-bold">{value.toLocaleString()}</span>
    </div>
  );
}

function StatusBadge({
  status,
  isHidden,
}: {
  status: 'published' | 'draft' | 'none';
  isHidden: boolean;
}) {
  if (isHidden) {
    return <Badge variant="muted">Hidden</Badge>;
  }

  switch (status) {
    case 'published':
      return <Badge variant="default">Published</Badge>;
    case 'draft':
      return <Badge variant="transmission">Draft</Badge>;
    default:
      return <Badge variant="muted">No Editorial</Badge>;
  }
}
