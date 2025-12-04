"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Badge } from "@/components/ui";

interface Ad {
  id: string;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  year?: number;
  product_category?: string;
  created_at?: string;
  processing_status?: string;
}

export default function ManageAdsPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Check auth
  useEffect(() => {
    const authToken = sessionStorage.getItem("admin_auth");
    if (authToken !== "authenticated") {
      router.push("/admin");
    } else {
      setIsAuthenticated(true);
      fetchAds();
    }
  }, [router]);

  const fetchAds = async (pageNum: number = 0, reset: boolean = false) => {
    setLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${apiUrl}/api/recent?limit=20&offset=${pageNum * 20}`
      );

      if (response.ok) {
        const data = await response.json();
        const newAds = data.ads || data || [];

        if (reset) {
          setAds(newAds);
        } else {
          setAds((prev) => [...prev, ...newAds]);
        }

        setHasMore(newAds.length === 20);
      }
    } catch (e) {
      console.error("Failed to fetch ads:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // In production, implement search API
    console.log("Search:", searchQuery);
  };

  const handleDelete = async (externalId: string) => {
    if (!confirm("Are you sure you want to delete this ad? This action cannot be undone.")) {
      return;
    }

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/admin/ads/${externalId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        setAds((prev) => prev.filter((ad) => ad.external_id !== externalId));
      } else {
        alert("Failed to delete ad. Please try again.");
      }
    } catch (e) {
      console.error("Delete failed:", e);
      alert("Failed to delete ad. Please try again.");
    }
  };

  const loadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchAds(nextPage);
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
            <Badge variant="transmission">Admin</Badge>
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
      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-display text-display-md font-bold text-signal mb-2">
                Manage Ads
              </h1>
              <p className="font-mono text-antenna">
                View, edit, and delete ads from the archive
              </p>
            </div>

            <Link
              href="/admin/upload"
              className="px-6 py-3 font-mono uppercase tracking-ultra-wide text-sm bg-transmission text-signal rounded-pill hover:bg-transmission-dark transition-colors"
            >
              Upload New
            </Link>
          </div>

          {/* Search */}
          <form onSubmit={handleSearch} className="mb-8">
            <div className="flex gap-4">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by brand, product, or ID..."
                className="flex-1 px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
              />
              <button
                type="submit"
                className="px-6 py-3 font-mono text-sm bg-static text-signal border border-white/10 rounded hover:bg-static/80 transition-colors"
              >
                Search
              </button>
            </div>
          </form>

          {/* Ads table */}
          <div className="bg-static/30 rounded-lg border border-white/5 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Brand
                    </th>
                    <th className="text-left px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Product
                    </th>
                    <th className="text-left px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Year
                    </th>
                    <th className="text-left px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Category
                    </th>
                    <th className="text-left px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
                      Status
                    </th>
                    <th className="text-right px-6 py-4 font-mono text-label uppercase tracking-ultra-wide text-antenna">
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
                        key={ad.external_id}
                        className="border-b border-white/5 hover:bg-static/30 transition-colors"
                      >
                        <td className="px-6 py-4">
                          <span className="font-display text-signal font-medium">
                            {ad.brand_name || "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="font-mono text-sm text-antenna">
                            {ad.product_name || "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="font-mono text-sm text-antenna">
                            {ad.year || "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="font-mono text-sm text-antenna">
                            {ad.product_category || "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <Badge
                            variant={
                              ad.processing_status === "complete"
                                ? "default"
                                : ad.processing_status === "processing"
                                ? "transmission"
                                : "muted"
                            }
                          >
                            {ad.processing_status || "Live"}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-3">
                            <Link
                              href={`/ads/${ad.external_id}`}
                              className="font-mono text-xs text-antenna hover:text-signal transition-colors"
                            >
                              View
                            </Link>
                            <button
                              onClick={() => handleDelete(ad.external_id)}
                              className="font-mono text-xs text-transmission hover:text-transmission-light transition-colors"
                            >
                              Delete
                            </button>
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
              <div className="p-6 text-center border-t border-white/5">
                <button
                  onClick={loadMore}
                  disabled={loading}
                  className="font-mono text-sm text-antenna hover:text-signal transition-colors disabled:opacity-50"
                >
                  {loading ? "Loading..." : "Load more ads"}
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </main>
    </div>
  );
}
