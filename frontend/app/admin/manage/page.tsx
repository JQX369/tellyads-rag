"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { Badge } from "@/components/ui";

interface Ad {
  id: string;
  external_id: string;
  brand_name?: string;
  product_name?: string;
  year?: number;
  product_category?: string;
  one_line_summary?: string;
  duration_seconds?: number;
  has_embedding?: boolean;
  editorial_status?: string;
  is_hidden?: boolean;
  is_featured?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface FilterOptions {
  categories: { name: string; count: number }[];
}

interface EditingAd extends Ad {
  isEditing?: boolean;
}

export default function ManageAdsPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState("");
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    categories: [],
  });
  const [pagination, setPagination] = useState({
    total: 0,
    limit: 50,
    offset: 0,
    hasMore: false,
  });
  const [editingAd, setEditingAd] = useState<EditingAd | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Check auth on mount
  useEffect(() => {
    const storedKey = sessionStorage.getItem("admin_key");
    if (storedKey) {
      setAdminKey(storedKey);
      setIsAuthenticated(true);
    } else {
      router.push("/admin");
    }
  }, [router]);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch ads when filters change
  useEffect(() => {
    if (isAuthenticated) {
      fetchAds(0, true);
    }
  }, [isAuthenticated, debouncedSearch, sortField, sortOrder, categoryFilter]);

  const fetchAds = async (offset: number = 0, reset: boolean = false) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: "50",
        offset: offset.toString(),
        sort: sortField,
        order: sortOrder,
      });

      if (debouncedSearch) params.set("search", debouncedSearch);
      if (categoryFilter) params.set("category", categoryFilter);

      const response = await fetch(`/api/admin/ads?${params}`, {
        headers: {
          "x-admin-key": adminKey,
        },
      });

      if (response.ok) {
        const data = await response.json();

        if (reset) {
          setAds(data.ads);
        } else {
          setAds((prev) => [...prev, ...data.ads]);
        }

        setPagination(data.pagination);
        setFilterOptions(data.filters);
      } else if (response.status === 401) {
        sessionStorage.removeItem("admin_key");
        router.push("/admin");
      }
    } catch (e) {
      console.error("Failed to fetch ads:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.size === ads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(ads.map((ad) => ad.external_id)));
    }
  };

  const handleSelectOne = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleDelete = async (externalId: string) => {
    if (!confirm("Are you sure you want to delete this ad? This action cannot be undone.")) {
      return;
    }

    setActionLoading(true);
    try {
      const response = await fetch(`/api/admin/ads/${externalId}`, {
        method: "DELETE",
        headers: {
          "x-admin-key": adminKey,
        },
      });

      if (response.ok) {
        setAds((prev) => prev.filter((ad) => ad.external_id !== externalId));
        setPagination((prev) => ({ ...prev, total: prev.total - 1 }));
      } else {
        alert("Failed to delete ad. Please try again.");
      }
    } catch (e) {
      console.error("Delete failed:", e);
      alert("Failed to delete ad. Please try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;

    if (!confirm(`Are you sure you want to delete ${selectedIds.size} ads? This action cannot be undone.`)) {
      return;
    }

    setActionLoading(true);
    try {
      const deletePromises = Array.from(selectedIds).map((id) =>
        fetch(`/api/admin/ads/${id}`, {
          method: "DELETE",
          headers: {
            "x-admin-key": adminKey,
          },
        })
      );

      await Promise.all(deletePromises);
      setAds((prev) => prev.filter((ad) => !selectedIds.has(ad.external_id)));
      setPagination((prev) => ({ ...prev, total: prev.total - selectedIds.size }));
      setSelectedIds(new Set());
    } catch (e) {
      console.error("Bulk delete failed:", e);
      alert("Some deletions failed. Please refresh and try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEdit = (ad: Ad) => {
    setEditingAd({ ...ad, isEditing: true });
  };

  const handleSaveEdit = async () => {
    if (!editingAd) return;

    setActionLoading(true);
    try {
      const response = await fetch(`/api/admin/ads/${editingAd.external_id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "x-admin-key": adminKey,
        },
        body: JSON.stringify({
          brand_name: editingAd.brand_name,
          product_name: editingAd.product_name,
          product_category: editingAd.product_category,
          one_line_summary: editingAd.one_line_summary,
          year: editingAd.year,
        }),
      });

      if (response.ok) {
        setAds((prev) =>
          prev.map((ad) =>
            ad.external_id === editingAd.external_id
              ? { ...ad, ...editingAd }
              : ad
          )
        );
        setEditingAd(null);
      } else {
        alert("Failed to save changes. Please try again.");
      }
    } catch (e) {
      console.error("Save failed:", e);
      alert("Failed to save changes. Please try again.");
    } finally {
      setActionLoading(false);
    }
  };

  const loadMore = () => {
    const nextOffset = pagination.offset + pagination.limit;
    setPagination((prev) => ({ ...prev, offset: nextOffset }));
    fetchAds(nextOffset, false);
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
      <header className="border-b border-white/10 sticky top-0 bg-void/95 backdrop-blur z-10">
        <div className="max-w-[1800px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-transmission rounded-sm flex items-center justify-center">
                <span className="font-display text-sm font-bold text-signal">T</span>
              </div>
              <span className="font-display font-bold text-signal">TellyAds</span>
            </Link>
            <Badge variant="transmission">Admin</Badge>
            <span className="text-white/30 mx-2">|</span>
            <span className="font-mono text-sm text-antenna">Content Manager</span>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/admin"
              className="font-mono text-sm text-antenna hover:text-signal transition-colors"
            >
              Dashboard
            </Link>
            <Link
              href="/admin/editorial"
              className="font-mono text-sm text-antenna hover:text-signal transition-colors"
            >
              Editorial
            </Link>
          </div>
        </div>
      </header>

      {/* Toolbar */}
      <div className="border-b border-white/5 bg-static/20">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[300px]">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by brand, product, ID..."
                className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-sm text-signal focus:outline-none focus:ring-2 focus:ring-transmission placeholder:text-white/30"
              />
            </div>

            {/* Category filter */}
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-sm text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
            >
              <option value="">All Categories</option>
              {filterOptions.categories.map((cat) => (
                <option key={cat.name} value={cat.name}>
                  {cat.name} ({cat.count})
                </option>
              ))}
            </select>

            {/* Bulk actions */}
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2 ml-auto">
                <span className="font-mono text-xs text-antenna">
                  {selectedIds.size} selected
                </span>
                <button
                  onClick={handleBulkDelete}
                  disabled={actionLoading}
                  className="px-3 py-1.5 font-mono text-xs bg-red-500/20 text-red-400 border border-red-500/30 rounded hover:bg-red-500/30 transition-colors disabled:opacity-50"
                >
                  Delete Selected
                </button>
              </div>
            )}

            {/* Add new button */}
            <Link
              href="/admin/upload"
              className="px-4 py-2 font-mono text-sm bg-transmission text-signal rounded hover:bg-transmission/80 transition-colors flex items-center gap-2"
            >
              <span>+</span> Add Item
            </Link>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="border-b border-white/5 bg-static/10">
        <div className="max-w-[1800px] mx-auto px-6 py-2 flex items-center gap-6">
          <span className="font-mono text-xs text-antenna">
            <span className="text-signal">{pagination.total}</span> items
          </span>
          <span className="text-white/20">|</span>
          <span className="font-mono text-xs text-antenna">
            Showing <span className="text-signal">{ads.length}</span> of {pagination.total}
          </span>
        </div>
      </div>

      {/* Table */}
      <main className="max-w-[1800px] mx-auto">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 bg-static/30">
                <th className="w-12 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === ads.length && ads.length > 0}
                    onChange={handleSelectAll}
                    className="w-4 h-4 rounded border-white/30 bg-transparent"
                  />
                </th>
                <SortableHeader
                  label="Brand"
                  field="brand_name"
                  currentSort={sortField}
                  order={sortOrder}
                  onSort={handleSort}
                />
                <SortableHeader
                  label="Product"
                  field="product_name"
                  currentSort={sortField}
                  order={sortOrder}
                  onSort={handleSort}
                />
                <SortableHeader
                  label="Category"
                  field="product_category"
                  currentSort={sortField}
                  order={sortOrder}
                  onSort={handleSort}
                />
                <SortableHeader
                  label="Year"
                  field="year"
                  currentSort={sortField}
                  order={sortOrder}
                  onSort={handleSort}
                />
                <th className="text-left px-4 py-3 font-mono text-xs uppercase tracking-wide text-antenna">
                  Embedded
                </th>
                <th className="text-left px-4 py-3 font-mono text-xs uppercase tracking-wide text-antenna">
                  Editorial
                </th>
                <SortableHeader
                  label="Created"
                  field="created_at"
                  currentSort={sortField}
                  order={sortOrder}
                  onSort={handleSort}
                />
                <th className="text-right px-4 py-3 font-mono text-xs uppercase tracking-wide text-antenna">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {loading && ads.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-16 text-center">
                    <div className="inline-block animate-spin h-6 w-6 border-2 border-transmission border-t-transparent rounded-full" />
                  </td>
                </tr>
              ) : ads.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-16 text-center font-mono text-antenna">
                    No ads found
                  </td>
                </tr>
              ) : (
                ads.map((ad) => (
                  <tr
                    key={ad.external_id}
                    className={clsx(
                      "border-b border-white/5 transition-colors",
                      selectedIds.has(ad.external_id)
                        ? "bg-transmission/10"
                        : "hover:bg-static/20"
                    )}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(ad.external_id)}
                        onChange={() => handleSelectOne(ad.external_id)}
                        className="w-4 h-4 rounded border-white/30 bg-transparent"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-display text-signal font-medium">
                        {ad.brand_name || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm text-antenna">
                        {ad.product_name || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-antenna">
                        {ad.product_category || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-sm text-antenna">
                        {ad.year || "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          "inline-block px-2 py-0.5 text-xs font-mono rounded border",
                          ad.has_embedding
                            ? "bg-green-500/20 text-green-400 border-green-500/30"
                            : "bg-gray-500/20 text-gray-400 border-gray-500/30"
                        )}
                      >
                        {ad.has_embedding ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          "inline-block px-2 py-0.5 text-xs font-mono rounded",
                          ad.editorial_status === "published"
                            ? "bg-blue-500/20 text-blue-400"
                            : ad.editorial_status === "draft"
                            ? "bg-yellow-500/20 text-yellow-400"
                            : "bg-gray-500/20 text-gray-400"
                        )}
                      >
                        {ad.editorial_status || "none"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-antenna">
                        {ad.created_at
                          ? new Date(ad.created_at).toLocaleDateString()
                          : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleEdit(ad)}
                          className="px-2 py-1 font-mono text-xs text-antenna hover:text-signal transition-colors"
                        >
                          Edit
                        </button>
                        <Link
                          href={`/ads/${ad.external_id}`}
                          target="_blank"
                          className="px-2 py-1 font-mono text-xs text-antenna hover:text-signal transition-colors"
                        >
                          View
                        </Link>
                        <button
                          onClick={() => handleDelete(ad.external_id)}
                          disabled={actionLoading}
                          className="px-2 py-1 font-mono text-xs text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
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
        {pagination.hasMore && (
          <div className="p-6 text-center border-t border-white/5">
            <button
              onClick={loadMore}
              disabled={loading}
              className="px-6 py-2 font-mono text-sm text-antenna bg-static/50 border border-white/10 rounded hover:text-signal hover:border-white/20 transition-colors disabled:opacity-50"
            >
              {loading ? "Loading..." : "Load more"}
            </button>
          </div>
        )}
      </main>

      {/* Edit Modal */}
      <AnimatePresence>
        {editingAd && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-6"
            onClick={() => setEditingAd(null)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-void border border-white/10 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-6 border-b border-white/10">
                <h2 className="font-display text-xl font-bold text-signal">Edit Ad</h2>
                <p className="font-mono text-xs text-antenna mt-1">
                  ID: {editingAd.external_id}
                </p>
              </div>

              <div className="p-6 space-y-4">
                <div>
                  <label className="block font-mono text-xs uppercase tracking-wide text-antenna mb-2">
                    Brand Name
                  </label>
                  <input
                    type="text"
                    value={editingAd.brand_name || ""}
                    onChange={(e) =>
                      setEditingAd({ ...editingAd, brand_name: e.target.value })
                    }
                    className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                  />
                </div>

                <div>
                  <label className="block font-mono text-xs uppercase tracking-wide text-antenna mb-2">
                    Product Name
                  </label>
                  <input
                    type="text"
                    value={editingAd.product_name || ""}
                    onChange={(e) =>
                      setEditingAd({ ...editingAd, product_name: e.target.value })
                    }
                    className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                  />
                </div>

                <div>
                  <label className="block font-mono text-xs uppercase tracking-wide text-antenna mb-2">
                    Product Category
                  </label>
                  <input
                    type="text"
                    value={editingAd.product_category || ""}
                    onChange={(e) =>
                      setEditingAd({ ...editingAd, product_category: e.target.value })
                    }
                    className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                  />
                </div>

                <div>
                  <label className="block font-mono text-xs uppercase tracking-wide text-antenna mb-2">
                    Year
                  </label>
                  <input
                    type="number"
                    value={editingAd.year || ""}
                    onChange={(e) =>
                      setEditingAd({
                        ...editingAd,
                        year: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                  />
                </div>

                <div>
                  <label className="block font-mono text-xs uppercase tracking-wide text-antenna mb-2">
                    One-Line Summary
                  </label>
                  <textarea
                    value={editingAd.one_line_summary || ""}
                    onChange={(e) =>
                      setEditingAd({ ...editingAd, one_line_summary: e.target.value })
                    }
                    rows={3}
                    className="w-full px-4 py-2 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission resize-none"
                  />
                </div>
              </div>

              <div className="p-6 border-t border-white/10 flex justify-end gap-4">
                <button
                  onClick={() => setEditingAd(null)}
                  className="px-4 py-2 font-mono text-sm text-antenna hover:text-signal transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={actionLoading}
                  className="px-6 py-2 font-mono text-sm bg-transmission text-signal rounded hover:bg-transmission/80 transition-colors disabled:opacity-50"
                >
                  {actionLoading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SortableHeader({
  label,
  field,
  currentSort,
  order,
  onSort,
}: {
  label: string;
  field: string;
  currentSort: string;
  order: "asc" | "desc";
  onSort: (field: string) => void;
}) {
  const isActive = currentSort === field;

  return (
    <th
      className="text-left px-4 py-3 font-mono text-xs uppercase tracking-wide text-antenna cursor-pointer hover:text-signal transition-colors select-none"
      onClick={() => onSort(field)}
    >
      <span className="flex items-center gap-1">
        {label}
        <span className={clsx("text-xs", isActive ? "text-transmission" : "text-white/20")}>
          {isActive ? (order === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </span>
    </th>
  );
}
