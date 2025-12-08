"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { Button, Badge } from "@/components/ui";

interface CatalogEntry {
  id: string;
  external_id: string;
  brand_name: string | null;
  title: string | null;
  air_date: string | null;
  air_date_raw: string | null;
  date_parse_confidence: number | null;
  date_parse_warning: string | null;
  year: number | null;
  decade: string | null;
  country: string | null;
  language: string | null;
  s3_key: string | null;
  video_url: string | null;
  views_seeded: number | null;
  is_mapped: boolean;
  is_ingested: boolean;
  ad_id: string | null;
  created_at: string;
  updated_at: string;
}

interface CatalogSummary {
  total_entries: number;
  mapped_entries: number;
  unmapped_entries: number;
  ingested_entries: number;
  not_ingested_entries: number;
  low_confidence_dates: number;
  unique_brands: number;
}

interface CatalogImport {
  id: string;
  created_at: string;
  updated_at: string;
  status: string;
  source_file_path: string;
  original_filename: string;
  rows_total: number | null;
  rows_ok: number | null;
  rows_failed: number | null;
  last_error: string | null;
  job_id: string | null;
  initiated_by: string | null;
  job_status: string | null;
  job_stage: string | null;
  job_progress: number | null;
}

interface FilterOption {
  brand_name?: string;
  decade?: string;
  country?: string;
  count: number;
}

type TabType = "catalog" | "imports";
type FilterType = "all" | "unmapped" | "not_ingested" | "low_confidence";

export default function CatalogPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>("catalog");

  // Catalog state
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<CatalogSummary | null>(null);
  const [brands, setBrands] = useState<FilterOption[]>([]);
  const [decades, setDecades] = useState<FilterOption[]>([]);
  const [countries, setCountries] = useState<FilterOption[]>([]);
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedBrand, setSelectedBrand] = useState<string>("");
  const [selectedDecade, setSelectedDecade] = useState<string>("");
  const [selectedCountry, setSelectedCountry] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  // Imports state
  const [imports, setImports] = useState<CatalogImport[]>([]);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Selection state for batch operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [enqueuing, setEnqueuing] = useState(false);

  const getAdminKey = () => sessionStorage.getItem("admin_key") || "";

  useEffect(() => {
    const key = sessionStorage.getItem("admin_key");
    if (key) {
      setIsAuthenticated(true);
      fetchCatalog(key);
      fetchImports(key);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchCatalog = useCallback(async (key: string) => {
    try {
      const params = new URLSearchParams();
      if (filter !== "all") params.set("filter", filter);
      if (selectedBrand) params.set("brand", selectedBrand);
      if (selectedDecade) params.set("decade", selectedDecade);
      if (selectedCountry) params.set("country", selectedCountry);
      if (searchQuery) params.set("search", searchQuery);
      params.set("limit", limit.toString());
      params.set("offset", offset.toString());

      const res = await fetch(`/api/admin/catalog?${params}`, {
        headers: { "x-admin-key": key },
      });

      if (res.ok) {
        const data = await res.json();
        setEntries(data.entries || []);
        setTotal(data.total || 0);
        setSummary(data.summary || null);
        setBrands(data.filters?.brands || []);
        setDecades(data.filters?.decades || []);
        setCountries(data.filters?.countries || []);
      }
    } catch (e) {
      console.error("Failed to fetch catalog:", e);
    } finally {
      setLoading(false);
    }
  }, [filter, selectedBrand, selectedDecade, selectedCountry, searchQuery, offset]);

  const fetchImports = useCallback(async (key: string) => {
    try {
      const res = await fetch("/api/admin/catalog/imports?limit=50", {
        headers: { "x-admin-key": key },
      });
      if (res.ok) {
        const data = await res.json();
        setImports(data.imports || []);
      }
    } catch (e) {
      console.error("Failed to fetch imports:", e);
    }
  }, []);

  const handleRefresh = useCallback(() => {
    const key = getAdminKey();
    if (activeTab === "catalog") {
      fetchCatalog(key);
    } else {
      fetchImports(key);
    }
  }, [activeTab, fetchCatalog, fetchImports]);

  // Refetch when filters change
  useEffect(() => {
    if (isAuthenticated) {
      setOffset(0);
      fetchCatalog(getAdminKey());
    }
  }, [filter, selectedBrand, selectedDecade, selectedCountry, searchQuery, isAuthenticated, fetchCatalog]);

  // Refetch when offset changes
  useEffect(() => {
    if (isAuthenticated) {
      fetchCatalog(getAdminKey());
    }
  }, [offset, isAuthenticated, fetchCatalog]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadProgress("Uploading...");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/admin/catalog/upload", {
        method: "POST",
        headers: { "x-admin-key": getAdminKey() },
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        setUploadProgress(`Upload complete! Import ID: ${data.import_id}`);
        setTimeout(() => {
          setUploadProgress(null);
          fetchImports(getAdminKey());
          setActiveTab("imports");
        }, 2000);
      } else {
        setUploadProgress(`Error: ${data.error}`);
        setTimeout(() => setUploadProgress(null), 5000);
      }
    } catch (e) {
      console.error("Upload failed:", e);
      setUploadProgress("Upload failed. Please try again.");
      setTimeout(() => setUploadProgress(null), 5000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.size === entries.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(entries.map((e) => e.id)));
    }
  };

  const handleSelectEntry = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleEnqueueSelected = async () => {
    const entriesToEnqueue = entries.filter((e) => selectedIds.has(e.id) && !e.is_ingested);
    if (entriesToEnqueue.length === 0) return;

    setEnqueuing(true);
    try {
      const res = await fetch("/api/admin/catalog/enqueue", {
        method: "POST",
        headers: {
          "x-admin-key": getAdminKey(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          catalog_ids: entriesToEnqueue.map((e) => e.id),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        alert(`Enqueued ${data.enqueued} jobs. ${data.skipped} already in queue or ingested.`);
        setSelectedIds(new Set());
        fetchCatalog(getAdminKey());
      } else {
        const data = await res.json();
        alert(`Error: ${data.error}`);
      }
    } catch (e) {
      console.error("Enqueue failed:", e);
      alert("Failed to enqueue jobs");
    } finally {
      setEnqueuing(false);
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
            <Badge variant="transmission">Catalog</Badge>
          </div>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleUpload}
              className="hidden"
            />
            <Button
              variant="primary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? "Uploading..." : "Upload CSV"}
            </Button>
            <Button variant="ghost" onClick={handleRefresh}>Refresh</Button>
          </div>
        </div>
      </header>

      {uploadProgress && (
        <div className="bg-transmission/20 border-b border-transmission/30 px-6 py-3">
          <p className="font-mono text-sm text-transmission max-w-7xl mx-auto">{uploadProgress}</p>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-display text-display-md font-bold text-signal mb-2">Ad Catalog</h1>
              <p className="font-mono text-antenna">Manage and ingest ads from CSV catalogs</p>
            </div>
          </div>

          {/* Summary Cards */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-8">
              <StatCard label="Total" value={summary.total_entries} />
              <StatCard label="Mapped" value={summary.mapped_entries} variant="success" />
              <StatCard label="Unmapped" value={summary.unmapped_entries} variant={summary.unmapped_entries > 0 ? "warning" : "default"} />
              <StatCard label="Ingested" value={summary.ingested_entries} variant="success" />
              <StatCard label="Not Ingested" value={summary.not_ingested_entries} variant="info" />
              <StatCard label="Low Confidence" value={summary.low_confidence_dates} variant={summary.low_confidence_dates > 0 ? "warning" : "default"} />
              <StatCard label="Brands" value={summary.unique_brands} />
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-white/10 pb-4">
            <TabButton active={activeTab === "catalog"} onClick={() => setActiveTab("catalog")} count={total}>
              Catalog
            </TabButton>
            <TabButton active={activeTab === "imports"} onClick={() => setActiveTab("imports")} count={imports.length}>
              Imports
            </TabButton>
          </div>

          <AnimatePresence mode="wait">
            {activeTab === "catalog" && (
              <motion.div key="catalog" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {/* Filters */}
                <div className="flex flex-wrap gap-4 mb-6 p-4 bg-static/30 rounded-lg border border-white/5">
                  <div className="flex items-center gap-2">
                    <label className="font-mono text-xs text-antenna">Filter:</label>
                    <select
                      value={filter}
                      onChange={(e) => setFilter(e.target.value as FilterType)}
                      className="bg-void border border-white/20 rounded px-3 py-1.5 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
                    >
                      <option value="all">All</option>
                      <option value="unmapped">Unmapped</option>
                      <option value="not_ingested">Not Ingested</option>
                      <option value="low_confidence">Low Confidence Dates</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="font-mono text-xs text-antenna">Brand:</label>
                    <select
                      value={selectedBrand}
                      onChange={(e) => setSelectedBrand(e.target.value)}
                      className="bg-void border border-white/20 rounded px-3 py-1.5 font-mono text-sm text-signal focus:outline-none focus:border-transmission max-w-[200px]"
                    >
                      <option value="">All Brands</option>
                      {brands.map((b) => (
                        <option key={b.brand_name} value={b.brand_name}>{b.brand_name} ({b.count})</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="font-mono text-xs text-antenna">Decade:</label>
                    <select
                      value={selectedDecade}
                      onChange={(e) => setSelectedDecade(e.target.value)}
                      className="bg-void border border-white/20 rounded px-3 py-1.5 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
                    >
                      <option value="">All Decades</option>
                      {decades.map((d) => (
                        <option key={d.decade} value={d.decade}>{d.decade} ({d.count})</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <label className="font-mono text-xs text-antenna">Country:</label>
                    <select
                      value={selectedCountry}
                      onChange={(e) => setSelectedCountry(e.target.value)}
                      className="bg-void border border-white/20 rounded px-3 py-1.5 font-mono text-sm text-signal focus:outline-none focus:border-transmission"
                    >
                      <option value="">All Countries</option>
                      {countries.map((c) => (
                        <option key={c.country} value={c.country}>{c.country} ({c.count})</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex-1 min-w-[200px]">
                    <input
                      type="text"
                      placeholder="Search by ID, brand, or title..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full bg-void border border-white/20 rounded px-3 py-1.5 font-mono text-sm text-signal focus:outline-none focus:border-transmission placeholder:text-antenna"
                    />
                  </div>
                </div>

                {/* Batch Actions */}
                {selectedIds.size > 0 && (
                  <div className="flex items-center gap-4 mb-4 p-3 bg-transmission/10 rounded-lg border border-transmission/30">
                    <span className="font-mono text-sm text-signal">{selectedIds.size} selected</span>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleEnqueueSelected}
                      disabled={enqueuing}
                    >
                      {enqueuing ? "Enqueuing..." : "Enqueue for Ingestion"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
                      Clear Selection
                    </Button>
                  </div>
                )}

                {/* Catalog Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">
                          <input
                            type="checkbox"
                            checked={selectedIds.size === entries.length && entries.length > 0}
                            onChange={handleSelectAll}
                            className="rounded border-white/20"
                          />
                        </th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">External ID</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Brand</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Title</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Air Date</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Decade</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Status</th>
                        <th className="text-left py-3 px-2 font-mono text-xs text-antenna uppercase tracking-wider">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entries.map((entry) => (
                        <tr
                          key={entry.id}
                          className="border-b border-white/5 hover:bg-white/5 transition-colors"
                        >
                          <td className="py-3 px-2">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(entry.id)}
                              onChange={() => handleSelectEntry(entry.id)}
                              className="rounded border-white/20"
                            />
                          </td>
                          <td className="py-3 px-2 font-mono text-signal">{entry.external_id}</td>
                          <td className="py-3 px-2 font-mono text-antenna">{entry.brand_name || "-"}</td>
                          <td className="py-3 px-2 font-mono text-antenna max-w-[200px] truncate">{entry.title || "-"}</td>
                          <td className="py-3 px-2 font-mono text-antenna">
                            {entry.air_date ? new Date(entry.air_date).toLocaleDateString() : entry.air_date_raw || "-"}
                            {entry.date_parse_warning && (
                              <span className="ml-1 text-yellow-400" title={entry.date_parse_warning}>!</span>
                            )}
                          </td>
                          <td className="py-3 px-2 font-mono text-antenna">{entry.decade || "-"}</td>
                          <td className="py-3 px-2">
                            <div className="flex gap-1">
                              {entry.is_ingested ? (
                                <span className="px-2 py-0.5 text-xs rounded bg-green-500/20 text-green-400">Ingested</span>
                              ) : entry.is_mapped ? (
                                <span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">Mapped</span>
                              ) : (
                                <span className="px-2 py-0.5 text-xs rounded bg-gray-500/20 text-gray-400">Unmapped</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-2">
                            <ConfidenceBadge value={entry.date_parse_confidence} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {entries.length === 0 && (
                  <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5 mt-4">
                    <p className="font-mono text-antenna">No catalog entries found</p>
                  </div>
                )}

                {/* Pagination */}
                {total > limit && (
                  <div className="flex items-center justify-between mt-6 pt-6 border-t border-white/10">
                    <span className="font-mono text-sm text-antenna">
                      Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
                    </span>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - limit))}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={offset + limit >= total}
                        onClick={() => setOffset(offset + limit)}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === "imports" && (
              <motion.div key="imports" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="space-y-3">
                  {imports.length === 0 ? (
                    <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5">
                      <p className="font-mono text-antenna">No imports yet. Upload a CSV file to get started.</p>
                    </div>
                  ) : (
                    imports.map((imp) => <ImportCard key={imp.id} importData={imp} />)
                  )}
                </div>
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

function StatCard({ label, value, variant = "default" }: { label: string; value: number; variant?: "default" | "info" | "success" | "error" | "warning" }) {
  const colors = {
    default: "text-signal",
    info: "text-blue-400",
    success: "text-green-400",
    error: "text-red-400",
    warning: "text-yellow-400",
  };
  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className={clsx("font-display font-bold text-2xl", colors[variant])}>
        {value.toLocaleString()}
      </div>
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mt-1">{label}</div>
    </div>
  );
}

function TabButton({ children, active, onClick, count }: { children: React.ReactNode; active: boolean; onClick: () => void; count?: number }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "px-4 py-2 font-mono text-sm rounded-t transition-colors flex items-center gap-2",
        active ? "bg-static/50 text-signal border-b-2 border-transmission" : "text-antenna hover:text-signal"
      )}
    >
      {children}
      {count !== undefined && (
        <span className="px-2 py-0.5 rounded-full text-xs bg-white/10 text-antenna">{count.toLocaleString()}</span>
      )}
    </button>
  );
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-antenna">-</span>;

  const percentage = Math.round(value * 100);
  const color = value >= 0.9 ? "text-green-400 bg-green-500/20" : value >= 0.8 ? "text-yellow-400 bg-yellow-500/20" : "text-red-400 bg-red-500/20";

  return (
    <span className={clsx("px-2 py-0.5 text-xs rounded font-mono", color)}>
      {percentage}%
    </span>
  );
}

function ImportCard({ importData }: { importData: CatalogImport }) {
  const statusColors: Record<string, string> = {
    UPLOADED: "bg-gray-500/20 text-gray-400",
    PROCESSING: "bg-blue-500/20 text-blue-400",
    SUCCEEDED: "bg-green-500/20 text-green-400",
    FAILED: "bg-red-500/20 text-red-400",
  };

  const progress = importData.job_progress != null ? Math.round(importData.job_progress * 100) : null;

  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className={clsx("px-2 py-0.5 rounded text-xs font-mono", statusColors[importData.status] || statusColors.UPLOADED)}>
              {importData.status}
            </span>
            {importData.job_stage && (
              <span className="font-mono text-xs text-antenna">Stage: {importData.job_stage}</span>
            )}
            {progress !== null && (
              <span className="font-mono text-xs text-antenna">{progress}%</span>
            )}
          </div>
          <h3 className="font-mono text-signal truncate mb-1">{importData.original_filename}</h3>
          <div className="flex items-center gap-4 text-xs font-mono text-antenna">
            <span>Created: {new Date(importData.created_at).toLocaleString()}</span>
            {importData.rows_total && (
              <span>
                Rows: {importData.rows_ok || 0}/{importData.rows_total}
                {importData.rows_failed ? ` (${importData.rows_failed} failed)` : ""}
              </span>
            )}
          </div>
          {importData.last_error && (
            <div className="mt-2 p-2 bg-red-500/10 rounded text-xs font-mono text-red-400 truncate">
              {importData.last_error}
            </div>
          )}
        </div>
      </div>
      {importData.status === "PROCESSING" && progress !== null && (
        <div className="mt-3 h-2 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-blue-500"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      )}
    </div>
  );
}
