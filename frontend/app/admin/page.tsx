"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Button, Badge } from "@/components/ui";
import { AtomicStarburst } from "@/components/ui/Starburst";

interface AdminStats {
  total_ads: number;
  total_brands: number;
  recent_count?: number;
  ads_with_embeddings?: number;
}

export default function AdminDashboard() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [adminKey, setAdminKey] = useState("");
  const [error, setError] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);

  // Check for existing auth on mount
  useEffect(() => {
    const storedKey = sessionStorage.getItem("admin_key");
    if (storedKey) {
      // Re-verify stored key via API
      verifyKey(storedKey, true);
    } else {
      setLoading(false);
    }
  }, []);

  const verifyKey = async (key: string, isReauth: boolean = false) => {
    setVerifying(true);
    setError("");

    try {
      const response = await fetch("/api/admin/verify", {
        method: "POST",
        headers: {
          "x-admin-key": key,
        },
      });

      if (response.ok) {
        sessionStorage.setItem("admin_key", key);
        setIsAuthenticated(true);
        fetchStats(key);
      } else {
        const data = await response.json();
        if (isReauth) {
          // Silent fail for re-auth, just clear stored key
          sessionStorage.removeItem("admin_key");
        } else {
          setError(data.error || "Invalid admin key");
        }
        setLoading(false);
      }
    } catch (e) {
      console.error("Verification failed:", e);
      if (!isReauth) {
        setError("Verification failed. Please try again.");
      }
      setLoading(false);
    } finally {
      setVerifying(false);
    }
  };

  const fetchStats = async (key: string) => {
    try {
      const response = await fetch("/api/stats", {
        headers: {
          "x-admin-key": key,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminKey.trim()) {
      setError("Please enter an admin key");
      return;
    }
    await verifyKey(adminKey);
  };

  const handleLogout = () => {
    sessionStorage.removeItem("admin_key");
    setIsAuthenticated(false);
    setAdminKey("");
    setStats(null);
  };

  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <div className="text-center mb-8">
            <AtomicStarburst size={60} color="#E63946" className="mx-auto mb-4" />
            <h1 className="font-display text-3xl font-bold text-signal mb-2">
              Admin Access
            </h1>
            <p className="font-mono text-sm text-antenna">
              TellyAds Content Management System
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                Admin Key
              </label>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                className={clsx(
                  "w-full px-4 py-3 bg-static/50 border rounded",
                  "font-mono text-signal placeholder:text-antenna",
                  "focus:outline-none focus:ring-2 focus:ring-transmission focus:border-transparent",
                  error ? "border-transmission" : "border-white/10"
                )}
                placeholder="Enter admin key"
                autoFocus
                disabled={verifying || loading}
              />
              {error && (
                <p className="mt-2 font-mono text-sm text-transmission">{error}</p>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={verifying || loading}
            >
              {verifying ? "Verifying..." : "Access Dashboard"}
            </Button>
          </form>

          <div className="mt-8 text-center">
            <Link
              href="/"
              className="font-mono text-sm text-antenna hover:text-signal transition-colors"
            >
              Back to TellyAds
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="starburst" />
      </div>
    );
  }

  // Admin dashboard
  return (
    <div className="min-h-screen bg-void">
      {/* Header */}
      <header className="border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-transmission rounded-sm flex items-center justify-center">
                <span className="font-display text-sm font-bold text-signal">T</span>
              </div>
              <span className="font-display font-bold text-signal">TellyAds</span>
            </Link>
            <Badge variant="transmission">Admin</Badge>
          </div>

          <button
            onClick={handleLogout}
            className="font-mono text-sm text-antenna hover:text-signal transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-display text-display-md font-bold text-signal mb-2">
            Dashboard
          </h1>
          <p className="font-mono text-antenna mb-12">
            Manage your TellyAds archive
          </p>

          {/* Stats cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
            <StatCard
              label="Total Ads"
              value={stats?.total_ads?.toLocaleString() || "0"}
              icon="📺"
            />
            <StatCard
              label="Total Brands"
              value={stats?.total_brands?.toLocaleString() || "0"}
              icon="🏷️"
            />
            <StatCard
              label="This Week"
              value={stats?.recent_count?.toString() || "0"}
              icon="📈"
            />
            <StatCard
              label="With Embeddings"
              value={stats?.ads_with_embeddings?.toString() || "0"}
              icon="🔍"
            />
          </div>

          {/* Action cards */}
          <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-6">
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <ActionCard
              title="Editorial"
              description="Publish & manage ad visibility"
              href="/admin/editorial"
              icon="📝"
            />
            <ActionCard
              title="Upload New Ad"
              description="Add a new commercial to the archive"
              href="/admin/upload"
              icon="➕"
            />
            <ActionCard
              title="Manage Ads"
              description="Edit or remove existing ads"
              href="/admin/manage"
              icon="📋"
            />
            <ActionCard
              title="View Queue"
              description="Check processing pipeline status"
              href="/admin/queue"
              icon="🔄"
            />
          </div>

          {/* Quick links */}
          <div className="mt-12 pt-8 border-t border-white/10">
            <h2 className="font-mono text-label uppercase tracking-ultra-wide text-antenna mb-4">
              External Links
            </h2>
            <div className="flex flex-wrap gap-4">
              <QuickLink href="/" label="View Site" />
              <QuickLink href="/browse" label="Browse Archive" />
              <QuickLink href="https://supabase.com/dashboard" label="Supabase Dashboard" external />
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="p-6 bg-static/30 rounded-lg border border-white/5">
      <div className="flex items-center justify-between mb-4">
        <span className="text-2xl">{icon}</span>
      </div>
      <div className="font-display text-3xl font-bold text-signal mb-1">{value}</div>
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna">
        {label}
      </div>
    </div>
  );
}

function ActionCard({
  title,
  description,
  href,
  icon,
}: {
  title: string;
  description: string;
  href: string;
  icon: string;
}) {
  return (
    <Link href={href}>
      <div
        className={clsx(
          "group p-6 bg-static/30 rounded-lg border border-white/5",
          "transition-all duration-300",
          "hover:bg-static/50 hover:border-transmission/30 hover:-translate-y-1"
        )}
      >
        <span className="text-3xl block mb-4">{icon}</span>
        <h3 className="font-display text-lg font-semibold text-signal mb-2 group-hover:text-transmission transition-colors">
          {title}
        </h3>
        <p className="font-mono text-sm text-antenna">{description}</p>
      </div>
    </Link>
  );
}

function QuickLink({
  href,
  label,
  external = false,
}: {
  href: string;
  label: string;
  external?: boolean;
}) {
  const props = external
    ? { target: "_blank", rel: "noopener noreferrer" }
    : {};

  return (
    <Link
      href={href}
      {...props}
      className="px-4 py-2 font-mono text-sm text-antenna bg-static/50 border border-white/10 rounded hover:text-signal hover:border-white/20 transition-colors"
    >
      {label}
      {external && " ↗"}
    </Link>
  );
}
