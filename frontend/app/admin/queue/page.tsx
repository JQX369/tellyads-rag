"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Button, Badge } from "@/components/ui";

interface QueueStats {
  stats: {
    total: number;
    by_status: Record<string, number>;
    oldest_pending?: string;
    newest_completed?: string;
  };
  health: "healthy" | "degraded" | "critical";
  summary: {
    running: number;
    pending: number;
    failed: number;
    has_dead_letter: boolean;
  };
}

interface Job {
  id: string;
  status: string;
  stage?: string;
  progress?: number;
  attempts: number;
  max_attempts: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  last_error?: string;
  error_code?: string;
  input: {
    source_type?: string;
    s3_key?: string;
    external_id?: string;
  };
  output?: Record<string, unknown>;
}

export default function QueuePage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeTab, setActiveTab] = useState<"running" | "failed" | "history">("running");
  const [refreshing, setRefreshing] = useState(false);

  const getAdminKey = () => sessionStorage.getItem("admin_key") || "";

  // Check auth on mount
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
    setRefreshing(true);
    try {
      // Fetch stats and jobs in parallel
      const [statsRes, jobsRes] = await Promise.all([
        fetch("/api/ingest/stats", { headers: { "x-admin-key": key } }),
        fetch("/api/ingest/jobs?limit=50", { headers: { "x-admin-key": key } }),
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData.jobs || []);
      }
    } catch (e) {
      console.error("Failed to fetch queue data:", e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const handleRetry = async (jobId: string) => {
    const key = getAdminKey();
    try {
      const res = await fetch(`/api/ingest/jobs/${jobId}`, {
        method: "POST",
        headers: {
          "x-admin-key": key,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "retry" }),
      });
      if (res.ok) {
        fetchData(key);
      }
    } catch (e) {
      console.error("Retry failed:", e);
    }
  };

  const handleCancel = async (jobId: string) => {
    const key = getAdminKey();
    try {
      const res = await fetch(`/api/ingest/jobs/${jobId}`, {
        method: "POST",
        headers: {
          "x-admin-key": key,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action: "cancel" }),
      });
      if (res.ok) {
        fetchData(key);
      }
    } catch (e) {
      console.error("Cancel failed:", e);
    }
  };

  // Auto-refresh every 10 seconds when viewing running jobs
  useEffect(() => {
    if (!isAuthenticated || activeTab !== "running") return;

    const interval = setInterval(() => {
      const key = getAdminKey();
      if (key) fetchData(key);
    }, 10000);

    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab, fetchData]);

  if (!isAuthenticated && !loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center p-6">
        <div className="text-center">
          <h1 className="font-display text-2xl font-bold text-signal mb-4">
            Authentication Required
          </h1>
          <p className="font-mono text-antenna mb-6">
            Please login from the admin dashboard first.
          </p>
          <Link href="/admin">
            <Button variant="primary">Go to Admin Login</Button>
          </Link>
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

  const runningJobs = jobs.filter((j) => j.status === "RUNNING");
  const failedJobs = jobs.filter((j) => j.status === "FAILED");
  const historyJobs = jobs.filter((j) => ["SUCCEEDED", "CANCELLED"].includes(j.status));

  const displayJobs = activeTab === "running" ? runningJobs :
                      activeTab === "failed" ? failedJobs : historyJobs;

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
            <Badge variant="transmission">Queue</Badge>
          </div>

          <Button
            variant="ghost"
            onClick={() => fetchData(getAdminKey())}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </Button>
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
                Ingestion Queue
              </h1>
              <p className="font-mono text-antenna">
                Monitor and manage the ad processing pipeline
              </p>
            </div>

            {stats && (
              <HealthBadge health={stats.health} />
            )}
          </div>

          {/* Stats cards */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <StatCard
                label="Running"
                value={stats.summary.running}
                variant="info"
              />
              <StatCard
                label="Pending"
                value={stats.summary.pending}
                variant="default"
              />
              <StatCard
                label="Failed"
                value={stats.summary.failed}
                variant={stats.summary.failed > 0 ? "error" : "default"}
              />
              <StatCard
                label="Total Processed"
                value={stats.stats.total}
                variant="success"
              />
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 mb-6 border-b border-white/10 pb-4">
            <TabButton
              active={activeTab === "running"}
              onClick={() => setActiveTab("running")}
              count={runningJobs.length}
            >
              Running
            </TabButton>
            <TabButton
              active={activeTab === "failed"}
              onClick={() => setActiveTab("failed")}
              count={failedJobs.length}
              variant={failedJobs.length > 0 ? "error" : undefined}
            >
              Failed
            </TabButton>
            <TabButton
              active={activeTab === "history"}
              onClick={() => setActiveTab("history")}
              count={historyJobs.length}
            >
              History
            </TabButton>
          </div>

          {/* Job list */}
          {displayJobs.length === 0 ? (
            <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5">
              <p className="font-mono text-antenna">
                {activeTab === "running" && "No jobs currently running"}
                {activeTab === "failed" && "No failed jobs"}
                {activeTab === "history" && "No completed jobs yet"}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {displayJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onRetry={() => handleRetry(job.id)}
                  onCancel={() => handleCancel(job.id)}
                />
              ))}
            </div>
          )}

          {/* Back link */}
          <div className="mt-12 pt-8 border-t border-white/10">
            <Link
              href="/admin"
              className="font-mono text-sm text-antenna hover:text-signal transition-colors"
            >
              &larr; Back to Dashboard
            </Link>
          </div>
        </motion.div>
      </main>
    </div>
  );
}

function HealthBadge({ health }: { health: "healthy" | "degraded" | "critical" }) {
  const config = {
    healthy: { label: "Healthy", className: "bg-green-500/20 text-green-400 border-green-500/30" },
    degraded: { label: "Degraded", className: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" },
    critical: { label: "Critical", className: "bg-red-500/20 text-red-400 border-red-500/30" },
  };

  const { label, className } = config[health];

  return (
    <span className={clsx("px-3 py-1 rounded-full font-mono text-sm border", className)}>
      {label}
    </span>
  );
}

function StatCard({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: number;
  variant?: "default" | "info" | "success" | "error";
}) {
  const colors = {
    default: "text-signal",
    info: "text-blue-400",
    success: "text-green-400",
    error: "text-red-400",
  };

  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className={clsx("font-display text-3xl font-bold", colors[variant])}>
        {value.toLocaleString()}
      </div>
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mt-1">
        {label}
      </div>
    </div>
  );
}

function TabButton({
  children,
  active,
  onClick,
  count,
  variant,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  count?: number;
  variant?: "error";
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "px-4 py-2 font-mono text-sm rounded-t transition-colors flex items-center gap-2",
        active
          ? "bg-static/50 text-signal border-b-2 border-transmission"
          : "text-antenna hover:text-signal"
      )}
    >
      {children}
      {count !== undefined && (
        <span
          className={clsx(
            "px-2 py-0.5 rounded-full text-xs",
            variant === "error" && count > 0
              ? "bg-red-500/20 text-red-400"
              : "bg-white/10 text-antenna"
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function JobCard({
  job,
  onRetry,
  onCancel,
}: {
  job: Job;
  onRetry: () => void;
  onCancel: () => void;
}) {
  const statusColors: Record<string, string> = {
    QUEUED: "bg-gray-500/20 text-gray-400",
    RUNNING: "bg-blue-500/20 text-blue-400",
    SUCCEEDED: "bg-green-500/20 text-green-400",
    FAILED: "bg-red-500/20 text-red-400",
    RETRY: "bg-yellow-500/20 text-yellow-400",
    CANCELLED: "bg-gray-500/20 text-gray-400",
  };

  const identifier = job.input.external_id || job.input.s3_key || job.id.slice(0, 8);
  const createdDate = new Date(job.created_at).toLocaleString();

  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5 hover:border-white/10 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className={clsx("px-2 py-0.5 rounded text-xs font-mono", statusColors[job.status])}>
              {job.status}
            </span>
            {job.stage && (
              <span className="font-mono text-xs text-antenna">
                Stage: {job.stage}
              </span>
            )}
            {job.progress !== undefined && job.progress > 0 && (
              <span className="font-mono text-xs text-antenna">
                {Math.round(job.progress * 100)}%
              </span>
            )}
          </div>

          <h3 className="font-mono text-signal truncate mb-1">
            {identifier}
          </h3>

          <div className="flex items-center gap-4 text-xs font-mono text-antenna">
            <span>Created: {createdDate}</span>
            <span>Attempts: {job.attempts}/{job.max_attempts}</span>
          </div>

          {job.last_error && (
            <div className="mt-2 p-2 bg-red-500/10 rounded text-xs font-mono text-red-400 truncate">
              {job.last_error}
            </div>
          )}
        </div>

        <div className="flex gap-2 shrink-0">
          {job.status === "FAILED" && (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              Retry
            </Button>
          )}
          {["QUEUED", "RETRY"].includes(job.status) && (
            <Button variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Progress bar for running jobs */}
      {job.status === "RUNNING" && job.progress !== undefined && (
        <div className="mt-3 h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-500"
            style={{ width: `${Math.round(job.progress * 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
