import { createFileRoute } from "@tanstack/react-router";
import useSWR from "swr";
import { Activity, AlertTriangle, CheckCircle2, Cloud, Database, Gauge, Zap } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { apiGet } from "@/lib/api/client";

export const Route = createFileRoute("/_app/monitoring")({
  component: MonitoringPage,
});

type PipeStatus = "healthy" | "degraded" | "unhealthy";

type PipelineStatus = {
  component: string;
  status: PipeStatus;
  lag_messages: number;
  last_update: string;
  details: Record<string, unknown>;
};

type ModelMetric = {
  horizon_minutes: number;
  mae: number;
  rmse: number;
  r2_score: number;
  rows: number;
  feature_count: number;
  artifact: string;
};

type MonitoringModel = {
  ready: boolean;
  model_dir: string;
  models: ModelMetric[];
  data_quality: {
    segments: number;
    record_count: number;
    missing_bucket_ratio: number | null;
    correct_interval_ratio: number | null;
    train_candidate_15m: number;
    train_candidate_60m: number;
    freshness_status: PipeStatus;
    interval_status: PipeStatus;
  };
};

type DashboardTrend = {
  timestamp: string;
  avg_speed: number;
  avg_jam_factor: number;
};

type DashboardTrends = {
  points: DashboardTrend[];
  available_points: number;
  max_timestamp?: string | null;
};

type DashboardSummary = {
  monitored_segments: number;
  active_alerts: number;
  avg_speed: number | null;
  avg_jam_factor: number | null;
  latest_timestamp?: string | null;
};

type SystemStatus = {
  api: {
    status: string;
    uptime_seconds: number;
    generated_at: string;
  };
  data: {
    status: string;
    gold_row_count: number;
    segment_count: number;
    latest_data_timestamp?: string | null;
    data_freshness_minutes?: number | null;
  };
  model: {
    loaded: boolean;
    ready: boolean;
    model_name?: string | null;
    model_family?: string | null;
    required_feature_count?: number | null;
    average_feature_coverage_ratio?: number | null;
    feature_coverage_status: string;
  };
  performance: {
    last_benchmark_at?: string | null;
    forecast_p95_ms?: number | null;
    dashboard_summary_p95_ms?: number | null;
    predicted_hotspots_p95_ms?: number | null;
    status: string;
  };
  streaming: {
    kafka_enabled: boolean;
    status: string;
    last_demo_at?: string | null;
  };
  local_stack?: {
    status: string;
    components: Record<string, { status: string; url?: string; endpoint?: string; bootstrap_servers?: string; database?: string }>;
  };
  cloud?: {
    status: string;
    s3: { status: string; bucket?: string | null; region?: string | null; warehouse?: string | null; verification?: string };
    neo4j_aura: { status: string; uri?: string | null; database?: string | null; verification?: string };
  };
};

function StatusDot({ status, pulse }: { status: PipeStatus; pulse?: boolean }) {
  const color =
    status === "healthy" ? "bg-success" : status === "degraded" ? "bg-warning" : "bg-destructive";
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${color}`} />}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  );
}

function formatCount(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return String(Math.round(value));
}

function formatPercent(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function formatAge(timestamp?: string | null) {
  if (!timestamp) return "n/a";
  const diffSeconds = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 1000));
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  if (diffSeconds < 3600) return `${Math.round(diffSeconds / 60)}m ago`;
  if (diffSeconds < 86400) return `${Math.round(diffSeconds / 3600)}h ago`;
  return `${Math.round(diffSeconds / 86400)}d ago`;
}

function formatSeconds(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  if (value < 60) return `${Math.round(value)}s`;
  if (value < 3600) return `${Math.round(value / 60)}m`;
  return `${(value / 3600).toFixed(1)}h`;
}

function formatMs(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)} ms` : "not measured";
}

function MonitoringPage() {
  const { data: system, error: systemError, isLoading: systemLoading } = useSWR<SystemStatus>(
    "/system/status",
    apiGet,
    { refreshInterval: 30_000 }
  );
  const { data: pipeline, error: pipelineError, isLoading: pipelineLoading } = useSWR<PipelineStatus[]>(
    "/monitoring/pipeline",
    apiGet,
    { refreshInterval: 30_000 }
  );
  const { data: model, error: modelError, isLoading: modelLoading } = useSWR<MonitoringModel>(
    "/monitoring/model",
    apiGet,
    { refreshInterval: 60_000 }
  );
  const { data: trends, error: trendsError } = useSWR<DashboardTrends>(
    "/dashboard/trends?city=hanoi&hours=168",
    apiGet,
    { refreshInterval: 60_000 }
  );
  const { data: summary, error: summaryError } = useSWR<DashboardSummary>(
    "/dashboard/summary?city=hanoi",
    apiGet,
    { refreshInterval: 30_000 }
  );

  const apiError = systemError || pipelineError || modelError || trendsError || summaryError;
  const loading = systemLoading || pipelineLoading || modelLoading;
  const unhealthy = (pipeline ?? []).filter((item) => item.status === "unhealthy").length;
  const degraded = (pipeline ?? []).filter((item) => item.status === "degraded").length;
  const latestTraffic = pipeline?.find((item) => item.component === "gold_traffic_features");
  const quality = model?.data_quality;
  const chartData = (trends?.points ?? []).map((point) => ({
    t: new Date(point.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" }),
    avg_speed: point.avg_speed,
    avg_jam_factor: point.avg_jam_factor,
  }));
  const latencyData = (model?.models ?? []).map((item) => ({
    horizon: `${item.horizon_minutes}m`,
    mae: item.mae,
    rmse: item.rmse,
  }));

  return (
    <PlaceholderPage title="Monitoring" subtitle="Local pipeline health, data quality, and forecast model readiness">
      <div className="grid grid-cols-12 gap-4">
        {apiError && (
          <div className="col-span-12 rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
            Monitoring API unavailable: {apiError.message}
          </div>
        )}

        <div className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-4">
          <SummaryCard icon={Activity} label="API uptime" value={formatSeconds(system?.api.uptime_seconds)} detail={system?.api.status ?? "unknown"} tone={system?.api.status === "ok" ? "success" : "warning"} loading={loading} />
          <SummaryCard icon={Database} label="Gold records" value={formatCount(system?.data.gold_row_count ?? quality?.record_count)} detail={`${formatCount(system?.data.segment_count ?? quality?.segments)} segments`} tone="primary" loading={loading} />
          <SummaryCard icon={CheckCircle2} label="Model loaded" value={system?.model.loaded ? "Loaded" : "Not loaded"} detail={system?.model.model_name ?? `${model?.models.length ?? 0} horizons`} tone={system?.model.loaded || model?.ready ? "success" : "warning"} loading={loading} />
          <SummaryCard icon={Zap} label="Data freshness" value={system?.data.latest_data_timestamp ? formatAge(system.data.latest_data_timestamp) : formatAge(latestTraffic?.last_update)} detail={system?.data.status ?? latestTraffic?.status ?? "unknown"} tone={(system?.data.status ?? latestTraffic?.status) === "ok" || latestTraffic?.status === "healthy" ? "success" : "warning"} loading={loading} />
        </div>

        <div className="col-span-12 grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <QualityTile label="Feature coverage" value={formatPercent(system?.model.average_feature_coverage_ratio)} detail={system?.model.feature_coverage_status ?? "not measured"} />
          <QualityTile label="Forecast p95" value={formatMs(system?.performance.forecast_p95_ms)} detail={system?.performance.status ?? "not measured"} />
          <QualityTile label="Hotspots p95" value={formatMs(system?.performance.predicted_hotspots_p95_ms)} detail={system?.performance.last_benchmark_at ? `measured ${formatAge(system.performance.last_benchmark_at)}` : "not measured"} />
          <QualityTile label="Streaming" value={system?.streaming.kafka_enabled ? "Enabled" : "Not enabled"} detail={system?.streaming.status ?? "not available"} />
          <QualityTile label="Local stack" value={system?.local_stack?.status ?? "unknown"} detail={Object.keys(system?.local_stack?.components ?? {}).join(", ") || "not reported"} />
          <QualityTile label="Cloud stack" value={system?.cloud?.status ?? "unknown"} detail={`S3 ${system?.cloud?.s3.status ?? "n/a"} · Aura ${system?.cloud?.neo4j_aura.status ?? "n/a"}`} />
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-8">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Traffic Feature Trend</h3>
              <p className="text-xs text-muted-foreground">Hourly average speed and jam factor from local Gold traffic features</p>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground">
              {trends?.available_points ?? 0} points
            </span>
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="speedGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="t" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="avg_speed" name="Avg speed" stroke="oklch(0.58 0.21 285)" strokeWidth={2.5} fill="url(#speedGradient)" />
                <Area type="monotone" dataKey="avg_jam_factor" name="Avg jam" stroke="oklch(0.72 0.17 35)" strokeWidth={2} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-4">
          <h3 className="text-base font-semibold">Pipeline Status</h3>
          <div className="mt-4 space-y-3 text-sm">
            {(pipeline ?? []).map((item) => (
              <div key={item.component} className="rounded-xl border border-border px-3 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <StatusDot status={item.status} pulse={item.status === "unhealthy"} />
                    <span className="truncate">{item.component.replaceAll("_", " ")}</span>
                  </div>
                  <span className={`shrink-0 text-[11px] capitalize ${item.status === "healthy" ? "text-muted-foreground" : item.status === "degraded" ? "text-[oklch(0.5_0.15_70)]" : "text-destructive"}`}>
                    {item.status}
                  </span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">
                  Updated {formatAge(item.last_update)}
                </div>
              </div>
            ))}
            {!pipeline?.length && (
              <div className="rounded-xl bg-secondary px-3 py-2.5 text-sm text-muted-foreground">
                {loading ? "Loading pipeline status..." : "No pipeline components returned."}
              </div>
            )}
            <div className="rounded-xl border border-border px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <StatusDot status={unhealthy ? "unhealthy" : degraded ? "degraded" : "healthy"} />
                  <span className="truncate">active issues</span>
                </div>
                <span className="shrink-0 text-[11px] text-muted-foreground">{unhealthy + degraded}</span>
              </div>
              <div className="mt-1 text-[11px] text-muted-foreground">
                {unhealthy} unhealthy · {degraded} degraded
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-7">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Forecast Model Error</h3>
              <p className="text-xs text-muted-foreground">Metrics from local model artifact training summary</p>
            </div>
            <div className="flex gap-2 text-xs">
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5"><span className="h-2 w-2 rounded-full bg-primary" /> MAE</span>
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5"><span className="h-2 w-2 rounded-full bg-warning" /> RMSE</span>
            </div>
          </div>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyData}>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="horizon" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="mae" fill="oklch(0.58 0.21 285)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="rmse" fill="oklch(0.78 0.16 70)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-5">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Model & Data Quality</h3>
            <Gauge className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {(model?.models ?? []).map((item) => (
              <QualityTile key={item.horizon_minutes} label={`${item.horizon_minutes}m MAE`} value={item.mae.toFixed(2)} detail={`${formatCount(item.rows)} rows · ${item.feature_count} features`} />
            ))}
            <QualityTile label="Missing buckets" value={formatPercent(quality?.missing_bucket_ratio)} detail={quality?.freshness_status ?? "unknown"} />
            <QualityTile label="5m interval OK" value={formatPercent(quality?.correct_interval_ratio)} detail={quality?.interval_status ?? "unknown"} />
            <QualityTile label="15m candidates" value={formatCount(quality?.train_candidate_15m)} detail="train-ready segments" />
            <QualityTile label="60m candidates" value={formatCount(quality?.train_candidate_60m)} detail="train-ready segments" />
          </div>
          <div className="mt-4 rounded-2xl bg-primary-soft px-4 py-3 text-xs text-accent-foreground">
            Model directory: <span className="font-mono">{model?.model_dir ?? "n/a"}</span>
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Local & Cloud Stack</h3>
              <p className="text-xs text-muted-foreground">Configured runtime dependencies from /system/status without exposing secrets</p>
            </div>
            <Cloud className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {Object.entries(system?.local_stack?.components ?? {}).map(([name, item]) => (
              <QualityTile
                key={name}
                label={name.replaceAll("_", " ")}
                value={item.status}
                detail={item.url ?? item.endpoint ?? item.bootstrap_servers ?? item.database ?? "local service"}
              />
            ))}
            <QualityTile label="AWS S3" value={system?.cloud?.s3.status ?? "unknown"} detail={system?.cloud?.s3.bucket ? `${system.cloud.s3.bucket} · ${system.cloud.s3.region}` : "not configured"} />
            <QualityTile label="Neo4j AuraDB" value={system?.cloud?.neo4j_aura.status ?? "unknown"} detail={system?.cloud?.neo4j_aura.database ?? system?.cloud?.neo4j_aura.uri ?? "not configured"} />
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  detail,
  tone,
  loading,
}: {
  icon: typeof Database;
  label: string;
  value: string;
  detail: string;
  tone: "primary" | "success" | "warning";
  loading: boolean;
}) {
  const iconClass =
    tone === "success"
      ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]"
      : tone === "warning"
        ? "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]"
        : "bg-primary-soft text-accent-foreground";
  return (
    <div className="rounded-2xl bg-card p-5">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      {loading ? (
        <>
          <div className="mt-4 h-7 w-20 animate-pulse rounded-md bg-secondary" />
          <div className="mt-2 h-3 w-24 animate-pulse rounded-md bg-secondary" />
        </>
      ) : (
        <div>
          <div className="mt-4 truncate text-2xl font-semibold">{value}</div>
          <div className="truncate text-xs text-muted-foreground">{label} · {detail}</div>
        </div>
      )}
    </div>
  );
}

function QualityTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border p-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-1 truncate text-[10px] text-muted-foreground">{detail}</div>
    </div>
  );
}
