"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
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
  locked_by?: string;
  last_heartbeat_at?: string;
  input: {
    source_type?: string;
    s3_key?: string;
    url?: string;
    external_id?: string;
    metadata?: Record<string, unknown>;
  };
  output?: {
    ad_id?: string;
    warnings?: string[];
    extraction_version?: string;
    already_existed?: boolean;
    elapsed_seconds?: number;
  };
}

interface RunningJob {
  id: string;
  created_at: string;
  processing_started_at: string;
  last_heartbeat_at: string;
  running_seconds: number;
  heartbeat_age_seconds: number;
  stage: string;
  progress: number;
  attempts: number;
  max_attempts: number;
  locked_by: string;
  s3_key?: string;
  external_id?: string;
  source_type?: string;
}

interface TimingStats {
  status: string;
  count: number;
  avg_duration_seconds: number;
  min_duration_seconds: number;
  max_duration_seconds: number;
  p50_seconds: number;
  p95_seconds: number;
}

interface ThroughputData {
  hour: string;
  completed: number;
  succeeded: number;
  failed: number;
}

interface StageFailure {
  stage: string;
  total: number;
  failed: number;
  failure_rate: number;
}

type TabType = "overview" | "running" | "failed" | "history";

export default function QueuePage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runningJobs, setRunningJobs] = useState<RunningJob[]>([]);
  const [timingStats, setTimingStats] = useState<TimingStats[]>([]);
  const [throughput, setThroughput] = useState<ThroughputData[]>([]);
  const [stageFailures, setStageFailures] = useState<StageFailure[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [refreshing, setRefreshing] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

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
    setRefreshing(true);
    try {
      const [statsRes, jobsRes, runningRes, timingRes, stagesRes] = await Promise.all([
        fetch("/api/ingest/stats", { headers: { "x-admin-key": key } }),
        fetch("/api/ingest/jobs?limit=100", { headers: { "x-admin-key": key } }),
        fetch("/api/ingest/monitor/running", { headers: { "x-admin-key": key } }),
        fetch("/api/ingest/monitor/timing", { headers: { "x-admin-key": key } }),
        fetch("/api/ingest/monitor/stages", { headers: { "x-admin-key": key } }),
      ]);

      if (statsRes.ok) setStats(await statsRes.json());
      if (jobsRes.ok) setJobs((await jobsRes.json()).jobs || []);
      if (runningRes.ok) setRunningJobs((await runningRes.json()).jobs || []);
      if (timingRes.ok) {
        const d = await timingRes.json();
        setTimingStats(d.stats || []);
        setThroughput(d.throughput || []);
      }
      if (stagesRes.ok) setStageFailures((await stagesRes.json()).stageFailures || []);
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
        headers: { "x-admin-key": key, "Content-Type": "application/json" },
        body: JSON.stringify({ action: "retry" }),
      });
      if (res.ok) {
        fetchData(key);
        setSelectedJob(null);
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
        headers: { "x-admin-key": key, "Content-Type": "application/json" },
        body: JSON.stringify({ action: "cancel" }),
      });
      if (res.ok) {
        fetchData(key);
        setSelectedJob(null);
      }
    } catch (e) {
      console.error("Cancel failed:", e);
    }
  };

  const fetchJobDetail = async (jobId: string) => {
    const key = getAdminKey();
    try {
      const res = await fetch(`/api/ingest/jobs/${jobId}`, { headers: { "x-admin-key": key } });
      if (res.ok) setSelectedJob(await res.json());
    } catch (e) {
      console.error("Failed to fetch job detail:", e);
    }
  };

  useEffect(() => {
    if (!isAuthenticated || (activeTab !== "running" && activeTab !== "overview")) return;
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

  const failedJobs = jobs.filter((j) => j.status === "FAILED");
  const historyJobs = jobs.filter((j) => ["SUCCEEDED", "CANCELLED"].includes(j.status));

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
            <Badge variant="transmission">Queue</Badge>
          </div>
          <Button variant="ghost" onClick={() => fetchData(getAdminKey())} disabled={refreshing}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-display text-display-md font-bold text-signal mb-2">Ingestion Queue</h1>
              <p className="font-mono text-antenna">Monitor and manage the ad processing pipeline</p>
            </div>
            {stats && <HealthBadge health={stats.health} />}
          </div>

          <div className="flex gap-2 mb-6 border-b border-white/10 pb-4">
            <TabButton active={activeTab === "overview"} onClick={() => setActiveTab("overview")}>Overview</TabButton>
            <TabButton active={activeTab === "running"} onClick={() => setActiveTab("running")} count={runningJobs.length} variant={runningJobs.length > 0 ? "info" : undefined}>Running</TabButton>
            <TabButton active={activeTab === "failed"} onClick={() => setActiveTab("failed")} count={failedJobs.length} variant={failedJobs.length > 0 ? "error" : undefined}>Failed</TabButton>
            <TabButton active={activeTab === "history"} onClick={() => setActiveTab("history")} count={historyJobs.length}>History</TabButton>
          </div>

          <AnimatePresence mode="wait">
            {activeTab === "overview" && (
              <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <OverviewTab stats={stats} timingStats={timingStats} throughput={throughput} stageFailures={stageFailures} />
              </motion.div>
            )}
            {activeTab === "running" && (
              <motion.div key="running" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <RunningTab jobs={runningJobs} onViewDetail={fetchJobDetail} />
              </motion.div>
            )}
            {activeTab === "failed" && (
              <motion.div key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <JobList jobs={failedJobs} onRetry={handleRetry} onCancel={handleCancel} onViewDetail={fetchJobDetail} emptyMessage="No failed jobs" />
              </motion.div>
            )}
            {activeTab === "history" && (
              <motion.div key="history" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <JobList jobs={historyJobs} onRetry={handleRetry} onCancel={handleCancel} onViewDetail={fetchJobDetail} emptyMessage="No completed jobs yet" />
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-12 pt-8 border-t border-white/10">
            <Link href="/admin" className="font-mono text-sm text-antenna hover:text-signal transition-colors">&larr; Back to Dashboard</Link>
          </div>
        </motion.div>
      </main>

      <JobDetailDrawer job={selectedJob} onClose={() => setSelectedJob(null)} onRetry={handleRetry} onCancel={handleCancel} />
    </div>
  );
}

function OverviewTab({ stats, timingStats, throughput, stageFailures }: { stats: QueueStats | null; timingStats: TimingStats[]; throughput: ThroughputData[]; stageFailures: StageFailure[] }) {
  const succeededStats = timingStats.find((s) => s.status === "SUCCEEDED");

  return (
    <div className="space-y-8">
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Running" value={stats.summary.running} variant="info" />
          <StatCard label="Pending" value={stats.summary.pending} variant="default" />
          <StatCard label="Failed" value={stats.summary.failed} variant={stats.summary.failed > 0 ? "error" : "default"} />
          <StatCard label="Total Processed" value={stats.stats.total} variant="success" />
          <StatCard label="Dead Letter" value={stats.summary.has_dead_letter ? "Yes" : "No"} variant={stats.summary.has_dead_letter ? "error" : "default"} isText />
        </div>
      )}

      {succeededStats && (
        <div className="p-6 bg-static/30 rounded-lg border border-white/5">
          <h3 className="font-display text-lg font-bold text-signal mb-4">Processing Duration</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MiniStat label="Average" value={formatDuration(succeededStats.avg_duration_seconds)} />
            <MiniStat label="P50 (Median)" value={formatDuration(succeededStats.p50_seconds)} />
            <MiniStat label="P95" value={formatDuration(succeededStats.p95_seconds)} />
            <MiniStat label="Min / Max" value={`${formatDuration(succeededStats.min_duration_seconds)} / ${formatDuration(succeededStats.max_duration_seconds)}`} />
          </div>
        </div>
      )}

      {throughput.length > 0 && (
        <div className="p-6 bg-static/30 rounded-lg border border-white/5">
          <h3 className="font-display text-lg font-bold text-signal mb-4">Throughput (Last 24h)</h3>
          <div className="space-y-2">
            {throughput.slice(0, 12).map((t) => (
              <div key={t.hour} className="flex items-center gap-4 text-sm font-mono">
                <span className="text-antenna w-32">{new Date(t.hour).toLocaleString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>
                <div className="flex-1 flex items-center gap-2">
                  <div className="h-4 bg-green-500/50 rounded" style={{ width: `${Math.min(t.succeeded * 5, 100)}%` }} />
                  {t.failed > 0 && <div className="h-4 bg-red-500/50 rounded" style={{ width: `${Math.min(t.failed * 5, 100)}%` }} />}
                </div>
                <span className="text-signal w-16 text-right">{t.succeeded}{t.failed > 0 && <span className="text-red-400"> / {t.failed}</span>}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {stageFailures.length > 0 && (
        <div className="p-6 bg-static/30 rounded-lg border border-white/5">
          <h3 className="font-display text-lg font-bold text-signal mb-4">Stage Failure Rates</h3>
          <div className="space-y-2">
            {stageFailures.filter((s) => s.total >= 5).slice(0, 10).map((s) => (
              <div key={s.stage} className="flex items-center gap-4 text-sm font-mono">
                <span className="text-antenna w-40 truncate">{s.stage}</span>
                <div className="flex-1 h-2 bg-white/10 rounded overflow-hidden">
                  <div className={clsx("h-full rounded", s.failure_rate > 20 ? "bg-red-500" : s.failure_rate > 5 ? "bg-yellow-500" : "bg-green-500")} style={{ width: `${Math.min(s.failure_rate, 100)}%` }} />
                </div>
                <span className={clsx("w-16 text-right", s.failure_rate > 20 ? "text-red-400" : s.failure_rate > 5 ? "text-yellow-400" : "text-green-400")}>{s.failure_rate}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function RunningTab({ jobs, onViewDetail }: { jobs: RunningJob[]; onViewDetail: (id: string) => void }) {
  if (jobs.length === 0) {
    return <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5"><p className="font-mono text-antenna">No jobs currently running</p></div>;
  }

  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <div key={job.id} className="p-4 bg-static/30 rounded-lg border border-white/5 hover:border-white/10 transition-colors cursor-pointer" onClick={() => onViewDetail(job.id)}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-2">
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-blue-500/20 text-blue-400">RUNNING</span>
                <span className="font-mono text-xs text-antenna">Stage: {job.stage || "unknown"}</span>
                <span className="font-mono text-xs text-antenna">{Math.round((job.progress || 0) * 100)}%</span>
              </div>
              <h3 className="font-mono text-signal truncate mb-1">{job.external_id || job.s3_key || job.id.slice(0, 8)}</h3>
              <div className="flex items-center gap-4 text-xs font-mono text-antenna">
                <span>Running: {formatDuration(job.running_seconds)}</span>
                <span>Heartbeat: {job.heartbeat_age_seconds}s ago</span>
                <span>Attempts: {job.attempts}/{job.max_attempts}</span>
                <span>Worker: {job.locked_by?.slice(0, 20)}</span>
              </div>
            </div>
          </div>
          <div className="mt-3 h-2 bg-white/10 rounded-full overflow-hidden">
            <motion.div className="h-full bg-blue-500" initial={{ width: 0 }} animate={{ width: `${Math.round((job.progress || 0) * 100)}%` }} transition={{ duration: 0.5 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function JobList({ jobs, onRetry, onCancel, onViewDetail, emptyMessage }: { jobs: Job[]; onRetry: (id: string) => void; onCancel: (id: string) => void; onViewDetail: (id: string) => void; emptyMessage: string }) {
  if (jobs.length === 0) {
    return <div className="text-center py-12 bg-static/20 rounded-lg border border-white/5"><p className="font-mono text-antenna">{emptyMessage}</p></div>;
  }
  return (
    <div className="space-y-3">
      {jobs.map((job) => <JobCard key={job.id} job={job} onRetry={() => onRetry(job.id)} onCancel={() => onCancel(job.id)} onViewDetail={() => onViewDetail(job.id)} />)}
    </div>
  );
}

function JobDetailDrawer({ job, onClose, onRetry, onCancel }: { job: Job | null; onClose: () => void; onRetry: (id: string) => void; onCancel: (id: string) => void }) {
  if (!job) return null;

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
        <div className="absolute inset-0 bg-black/50" />
        <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 25, stiffness: 300 }} className="relative w-full max-w-xl bg-void border-l border-white/10 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
          <div className="p-6">
            <div className="flex items-start justify-between mb-6">
              <div>
                <h2 className="font-display text-xl font-bold text-signal mb-1">Job Details</h2>
                <p className="font-mono text-xs text-antenna">{job.id}</p>
              </div>
              <button onClick={onClose} className="p-2 hover:bg-white/10 rounded transition-colors"><span className="text-antenna text-xl">×</span></button>
            </div>

            <div className="mb-6"><JobStatusBadge status={job.status} /></div>

            <div className="flex gap-2 mb-8">
              {job.status === "FAILED" && <Button variant="primary" size="sm" onClick={() => onRetry(job.id)}>Retry Job</Button>}
              {["QUEUED", "RETRY"].includes(job.status) && <Button variant="ghost" size="sm" onClick={() => onCancel(job.id)}>Cancel Job</Button>}
            </div>

            <div className="space-y-6">
              <DetailSection title="Input">
                <pre className="text-xs font-mono text-antenna whitespace-pre-wrap overflow-auto max-h-48 bg-static/30 p-3 rounded">{JSON.stringify(job.input, null, 2)}</pre>
              </DetailSection>

              <DetailSection title="Timeline">
                <div className="space-y-2 text-sm font-mono">
                  <TimelineRow label="Created" value={job.created_at} />
                  <TimelineRow label="Started" value={job.started_at} />
                  <TimelineRow label="Completed" value={job.completed_at} />
                  <TimelineRow label="Last Heartbeat" value={job.last_heartbeat_at} />
                </div>
              </DetailSection>

              <DetailSection title="Processing">
                <div className="space-y-2 text-sm font-mono">
                  <DetailRow label="Stage" value={job.stage || "-"} />
                  <DetailRow label="Progress" value={job.progress ? `${Math.round(job.progress * 100)}%` : "-"} />
                  <DetailRow label="Attempts" value={`${job.attempts} / ${job.max_attempts}`} />
                  <DetailRow label="Worker" value={job.locked_by || "-"} />
                </div>
              </DetailSection>

              {job.last_error && (
                <DetailSection title="Last Error">
                  {job.error_code && <div className="mb-2"><span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-mono rounded">{job.error_code}</span></div>}
                  <pre className="text-xs font-mono text-red-400 whitespace-pre-wrap overflow-auto max-h-32 bg-red-500/10 p-3 rounded">{job.last_error}</pre>
                </DetailSection>
              )}

              {job.output && (
                <DetailSection title="Output">
                  {job.output.ad_id && <div className="mb-2"><Link href={`/advert/${job.output.ad_id}`} className="text-transmission hover:underline text-sm font-mono">View Ad →</Link></div>}
                  <pre className="text-xs font-mono text-antenna whitespace-pre-wrap overflow-auto max-h-48 bg-static/30 p-3 rounded">{JSON.stringify(job.output, null, 2)}</pre>
                </DetailSection>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function HealthBadge({ health }: { health: "healthy" | "degraded" | "critical" }) {
  const config = { healthy: { label: "Healthy", className: "bg-green-500/20 text-green-400 border-green-500/30" }, degraded: { label: "Degraded", className: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" }, critical: { label: "Critical", className: "bg-red-500/20 text-red-400 border-red-500/30" } };
  const { label, className } = config[health];
  return <span className={clsx("px-3 py-1 rounded-full font-mono text-sm border", className)}>{label}</span>;
}

function StatCard({ label, value, variant = "default", isText = false }: { label: string; value: number | string; variant?: "default" | "info" | "success" | "error"; isText?: boolean }) {
  const colors = { default: "text-signal", info: "text-blue-400", success: "text-green-400", error: "text-red-400" };
  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5">
      <div className={clsx("font-display font-bold", colors[variant], isText ? "text-lg" : "text-3xl")}>{typeof value === "number" ? value.toLocaleString() : value}</div>
      <div className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mt-1">{label}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return <div><div className="font-mono text-lg text-signal">{value}</div><div className="font-mono text-xs text-antenna">{label}</div></div>;
}

function TabButton({ children, active, onClick, count, variant }: { children: React.ReactNode; active: boolean; onClick: () => void; count?: number; variant?: "error" | "info" }) {
  return (
    <button onClick={onClick} className={clsx("px-4 py-2 font-mono text-sm rounded-t transition-colors flex items-center gap-2", active ? "bg-static/50 text-signal border-b-2 border-transmission" : "text-antenna hover:text-signal")}>
      {children}
      {count !== undefined && count > 0 && <span className={clsx("px-2 py-0.5 rounded-full text-xs", variant === "error" ? "bg-red-500/20 text-red-400" : variant === "info" ? "bg-blue-500/20 text-blue-400" : "bg-white/10 text-antenna")}>{count}</span>}
    </button>
  );
}

function JobCard({ job, onRetry, onCancel, onViewDetail }: { job: Job; onRetry: () => void; onCancel: () => void; onViewDetail: () => void }) {
  const statusColors: Record<string, string> = { QUEUED: "bg-gray-500/20 text-gray-400", RUNNING: "bg-blue-500/20 text-blue-400", SUCCEEDED: "bg-green-500/20 text-green-400", FAILED: "bg-red-500/20 text-red-400", RETRY: "bg-yellow-500/20 text-yellow-400", CANCELLED: "bg-gray-500/20 text-gray-400" };
  const identifier = job.input.external_id || job.input.s3_key || job.id.slice(0, 8);
  const createdDate = new Date(job.created_at).toLocaleString();

  return (
    <div className="p-4 bg-static/30 rounded-lg border border-white/5 hover:border-white/10 transition-colors cursor-pointer" onClick={onViewDetail}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className={clsx("px-2 py-0.5 rounded text-xs font-mono", statusColors[job.status])}>{job.status}</span>
            {job.stage && <span className="font-mono text-xs text-antenna">Stage: {job.stage}</span>}
          </div>
          <h3 className="font-mono text-signal truncate mb-1">{identifier}</h3>
          <div className="flex items-center gap-4 text-xs font-mono text-antenna">
            <span>Created: {createdDate}</span>
            <span>Attempts: {job.attempts}/{job.max_attempts}</span>
          </div>
          {job.last_error && <div className="mt-2 p-2 bg-red-500/10 rounded text-xs font-mono text-red-400 truncate">{job.last_error}</div>}
        </div>
        <div className="flex gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {job.status === "FAILED" && <Button variant="ghost" size="sm" onClick={onRetry}>Retry</Button>}
          {["QUEUED", "RETRY"].includes(job.status) && <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>}
        </div>
      </div>
    </div>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  const statusColors: Record<string, string> = { QUEUED: "bg-gray-500/20 text-gray-400 border-gray-500/30", RUNNING: "bg-blue-500/20 text-blue-400 border-blue-500/30", SUCCEEDED: "bg-green-500/20 text-green-400 border-green-500/30", FAILED: "bg-red-500/20 text-red-400 border-red-500/30", RETRY: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30", CANCELLED: "bg-gray-500/20 text-gray-400 border-gray-500/30" };
  return <span className={clsx("px-3 py-1 rounded-full font-mono text-sm border", statusColors[status])}>{status}</span>;
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <div><h3 className="font-mono text-xs uppercase tracking-ultra-wide text-antenna mb-2">{title}</h3>{children}</div>;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between"><span className="text-antenna">{label}</span><span className="text-signal">{value}</span></div>;
}

function TimelineRow({ label, value }: { label: string; value?: string }) {
  return <div className="flex justify-between"><span className="text-antenna">{label}</span><span className="text-signal">{value ? new Date(value).toLocaleString() : "-"}</span></div>;
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "-";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}
