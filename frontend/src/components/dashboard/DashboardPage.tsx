import {
  Activity,
  AlertTriangle,
  Gauge,
  Map as MapIcon,
  TrendingUp,
  Cpu,
  Zap,
  ArrowUpRight,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useState } from "react";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";



const trend = Array.from({ length: 24 }, (_, i) => ({
  hour: `${i}:00`,
  speed: 28 + Math.sin(i / 3) * 12 + (i > 7 && i < 10 ? -8 : 0) + (i > 16 && i < 20 ? -10 : 0),
  jam: 4 + Math.cos(i / 3) * 1.5 + (i > 7 && i < 10 ? 2 : 0) + (i > 16 && i < 20 ? 3 : 0),
}));

const segments = [
  { name: "Mon", value: 38 },
  { name: "Tue", value: 45 },
  { name: "Wed", value: 32 },
  { name: "Thu", value: 58 },
  { name: "Fri", value: 72 },
  { name: "Sat", value: 41 },
  { name: "Sun", value: 29 },
];

function StatCard({
  icon: Icon,
  label,
  value,
  delta,
  tone = "primary",
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  delta?: string;
  tone?: "primary" | "warning" | "success" | "destructive";
}) {
  const toneMap: Record<string, string> = {
    primary: "bg-primary-soft text-accent-foreground",
    warning: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    success: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    destructive: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  };
  return (
    <div className="rounded-2xl bg-card p-5">
      <div className="flex items-start justify-between">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneMap[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
        {delta && <span className="text-xs font-medium text-muted-foreground">{delta}</span>}
      </div>
      <div className="mt-4 text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function DashboardPage() {
  return (
    <div className="grid grid-cols-12 gap-4">
      {/* HERO */}
      <div className="col-span-12 xl:col-span-9">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primary to-[oklch(0.45_0.22_290)] p-8 text-primary-foreground">
          <div className="absolute -right-10 -top-10 h-60 w-60 rounded-full bg-white/10 blur-3xl" />
          <div className="absolute right-20 top-10 text-white/20">
            <Sparkle />
          </div>
          <div className="relative">
            <div className="text-[11px] font-semibold tracking-widest text-white/70">REAL-TIME ANALYTICS</div>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold leading-tight">
              Cognitive Traffic Intelligence for a Smarter City
            </h2>
            <button className="mt-6 inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background">
              View Live Map
              <ArrowUpRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* metric strip */}
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={MapIcon} label="Monitored segments" value="2,481" delta="+ 124" />
          <StatCard icon={AlertTriangle} label="Active alerts" value="17" delta="+ 3" tone="destructive" />
          <StatCard icon={Gauge} label="Avg city speed" value="34 km/h" delta="− 2.1%" tone="warning" />
          <StatCard icon={Activity} label="Avg jam factor" value="5.4" delta="+ 0.8" tone="success" />
        </div>

        {/* trend chart */}
        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Traffic Trend</h3>
              <p className="text-xs text-muted-foreground">Average speed & jam factor — last 24h</p>
            </div>
            <div className="flex gap-2 text-xs">
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5">
                <span className="h-2 w-2 rounded-full bg-primary" /> Speed
              </span>
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5">
                <span className="h-2 w-2 rounded-full bg-warning" /> Jam factor
              </span>
            </div>
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="hour" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "white",
                    border: "1px solid oklch(0.92 0.01 280)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
                <Area type="monotone" dataKey="speed" stroke="oklch(0.58 0.21 285)" strokeWidth={2.5} fill="url(#g1)" />
                <Area type="monotone" dataKey="jam" stroke="oklch(0.78 0.16 70)" strokeWidth={2} fill="transparent" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* category cards row */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            { label: "Free Flow", count: "1,842 / 2,481", color: "success" },
            { label: "Slow Traffic", count: "412 / 2,481", color: "warning" },
            { label: "Congested", count: "227 / 2,481", color: "destructive" },
          ].map((c) => (
            <div key={c.label} className="flex items-center justify-between rounded-2xl bg-card p-5">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                    c.color === "success"
                      ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]"
                      : c.color === "warning"
                      ? "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]"
                      : "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]"
                  }`}
                >
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">{c.count}</div>
                  <div className="font-semibold">{c.label}</div>
                </div>
              </div>
              <button className="text-muted-foreground">⋮</button>
            </div>
          ))}
        </div>

        {/* live corridor tracking */}
        <div className="mt-4">
          <LiveCorridorTracking />
        </div>



        {/* recent alerts table */}
        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Recent Alerts</h3>
            <a className="text-xs text-primary underline">See all</a>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="text-left">
                  <th className="pb-3 font-medium">Location</th>
                  <th className="pb-3 font-medium">Severity</th>
                  <th className="pb-3 font-medium">Cause</th>
                  <th className="pb-3 font-medium">Detected</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {[
                  { loc: "Cau Giay, Hanoi", sev: "High", cause: "Peak hour + rain", t: "2m ago" },
                  { loc: "District 1, HCMC", sev: "Critical", cause: "Accident reported", t: "8m ago" },
                  { loc: "Dong Da, Hanoi", sev: "Medium", cause: "Public event", t: "21m ago" },
                ].map((r) => (
                  <tr key={r.loc} className="border-t border-border">
                    <td className="py-3 font-medium">{r.loc}</td>
                    <td>
                      <SeverityBadge level={r.sev} />
                    </td>
                    <td className="text-muted-foreground">{r.cause}</td>
                    <td className="text-muted-foreground">{r.t}</td>
                    <td>
                      <button className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground hover:bg-secondary">
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR */}
      <div className="col-span-12 xl:col-span-3">
        <div className="rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">System Health</h3>
            <span className="text-muted-foreground">⋮</span>
          </div>
          <div className="mt-5 flex flex-col items-center">
            <div className="relative">
              <svg width="160" height="160" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="68" fill="none" stroke="oklch(0.93 0.06 285)" strokeWidth="6" />
                <circle
                  cx="80"
                  cy="80"
                  r="68"
                  fill="none"
                  stroke="oklch(0.58 0.21 285)"
                  strokeWidth="6"
                  strokeDasharray="427"
                  strokeDashoffset="76"
                  strokeLinecap="round"
                  transform="rotate(-90 80 80)"
                />
              </svg>
              <div className="absolute inset-3 flex items-center justify-center rounded-full bg-primary-soft">
                <Cpu className="h-12 w-12 text-accent-foreground" />
              </div>
              <div className="absolute right-0 top-3 rounded-full bg-primary px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                82%
              </div>
            </div>
            <div className="mt-4 text-center">
              <div className="text-lg font-semibold">All Systems Healthy ⚡</div>
              <div className="mt-1 text-xs text-muted-foreground">
                Kafka, Spark & API operating within thresholds.
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-secondary p-4">
            <div className="mb-2 text-xs text-muted-foreground">Predictions / day</div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={segments}>
                  <XAxis dataKey="name" stroke="oklch(0.5 0.02 270)" fontSize={10} tickLine={false} axisLine={false} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {segments.map((_, i) => (
                      <Bar key={i} dataKey="value" fill={i === 4 ? "oklch(0.58 0.21 285)" : "oklch(0.85 0.08 285)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold">Model Performance</h3>
            <button className="flex h-7 w-7 items-center justify-center rounded-full border border-border">
              <TrendingUp className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="mt-4 flex flex-col gap-3">
            {[
              { name: "MAE", v: "3.21", sub: "v2024.11" },
              { name: "RMSE", v: "5.07", sub: "v2024.11" },
              { name: "Latency", v: "184 ms", sub: "p95" },
            ].map((m) => (
              <div key={m.name} className="flex items-center justify-between rounded-2xl border border-border p-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-soft text-accent-foreground">
                    <Activity className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{m.name}</div>
                    <div className="text-[11px] text-muted-foreground">{m.sub}</div>
                  </div>
                </div>
                <div className="text-sm font-semibold">{m.v}</div>
              </div>
            ))}
            <button className="rounded-2xl bg-primary-soft py-3 text-sm font-medium text-accent-foreground">
              Open Monitoring
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SeverityBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    Low: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    Medium: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    High: "bg-primary-soft text-accent-foreground",
    Critical: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  };
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${map[level]}`}>{level}</span>
  );
}

function Sparkle() {
  return (
    <svg width="120" height="120" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5z" />
    </svg>
  );
}

// Default segment ids representing the most congested currently active corridors.
const CONGESTED_DEFAULTS = [
  "HN_001",
  "HN_002",
  "HN_003",
];

type UpstreamSegment = {
  id: string;
  name: string;
  road_class: string;
  speed_kmh: number;
  status: "free" | "slow" | "congested";
};

type UpstreamResponse = {
  segment_id: string;
  updated_at: string;
  chain: UpstreamSegment[];
};

const fetcher = (url: string) =>
  apiGet<UpstreamResponse>(url);

function StatusBadge({ status }: { status: UpstreamSegment["status"] }) {
  const map = {
    free: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    slow: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    congested: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  } as const;
  const label = { free: "Free", slow: "Slow", congested: "Congested" }[status];
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${map[status]}`}>
      {label}
    </span>
  );
}

function LiveCorridorTracking() {
  const [segmentId, setSegmentId] = useSWRSafeState(CONGESTED_DEFAULTS[0]);
  const { data, error, isLoading, isValidating } = useSWR<UpstreamResponse>(
    `/segments/${segmentId}/upstream`,
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: false }
  );

  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Live Corridor Tracking</h3>
          <p className="text-xs text-muted-foreground">
            Upstream chain for the most congested active segment · auto-refresh 60s
            {isValidating && !isLoading ? " · refreshing…" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={segmentId}
            onChange={(e) => setSegmentId(e.target.value)}
            className="rounded-full border border-border bg-background px-3 py-1.5 text-xs"
          >
            {CONGESTED_DEFAULTS.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        {error ? (
          <div className="rounded-2xl bg-secondary p-4 text-sm text-muted-foreground">
            Couldn't load upstream chain.
          </div>
        ) : isLoading || !data ? (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-secondary" />
            ))}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr className="text-left">
                <th className="pb-3 font-medium">#</th>
                <th className="pb-3 font-medium">Segment</th>
                <th className="pb-3 font-medium">Speed</th>
                <th className="pb-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.chain.map((seg, idx) => (
                <tr key={seg.id} className="border-t border-border">
                  <td className="py-3 text-muted-foreground">{idx + 1}</td>
                  <td className="py-3">
                    <div className="font-medium">{seg.name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {seg.id} · {seg.road_class}
                    </div>
                  </td>
                  <td className="py-3 font-medium">{seg.speed_kmh} km/h</td>
                  <td className="py-3">
                    <StatusBadge status={seg.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Local hook to avoid pulling extra imports at the top of the file.
function useSWRSafeState<T>(initial: T) {
  return useState<T>(initial);
}
