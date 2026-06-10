import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { Activity, Database, Zap, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/_app/monitoring")({
  component: MonitoringPage,
});

const ingest = Array.from({ length: 24 }, (_, i) => ({
  t: `${i}:00`,
  records: 8400 + Math.sin(i / 3) * 1200 + (i > 7 && i < 10 ? 1800 : 0) + (i > 16 && i < 20 ? 2100 : 0),
}));

const latency = Array.from({ length: 18 }, (_, i) => ({
  t: `${i * 5}m`,
  p50: 120 + Math.sin(i / 2) * 25,
  p95: 220 + Math.sin(i / 2 + 1) * 60,
}));

type PipeStatus = "healthy" | "warning" | "error";

function StatusDot({ status, pulse }: { status: PipeStatus; pulse?: boolean }) {
  const color =
    status === "healthy" ? "bg-success" : status === "warning" ? "bg-warning" : "bg-destructive";
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${color}`} />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  );
}

function MonitoringPage() {
  const [loading, setLoading] = useState(true);
  const [secondsAgo, setSecondsAgo] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 1500);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const i = setInterval(() => setSecondsAgo((s) => s + 1), 1000);
    return () => clearInterval(i);
  }, []);

  const kafkaLagMs = 84;
  const sparkBatchS = 4.2;
  const pipelineStatusFor = (ms: number, warn: number, err: number): PipeStatus =>
    ms > err ? "error" : ms > warn ? "warning" : "healthy";

  const pipelines: { name: string; v: string; status: PipeStatus; pulse?: boolean }[] = [
    { name: "Kafka · traffic-stream", v: `Lag ${kafkaLagMs} ms`, status: pipelineStatusFor(kafkaLagMs, 500, 2000) },
    { name: "Kafka · weather-stream", v: "Lag 112 ms", status: "healthy" },
    { name: "Spark Structured Stream", v: `Batch ${sparkBatchS} s`, status: pipelineStatusFor(sparkBatchS * 1000, 10000, 30000) },
    { name: "Feature Store", v: "Sync 18 s ago", status: "healthy" },
    { name: "TomTom Flow API", v: "99.6% · 184ms", status: "healthy" },
    { name: "OpenWeather API", v: "Retry x2", status: "error", pulse: true },
  ];


  return (
    <PlaceholderPage title="Monitoring" subtitle="Pipeline health, data quality, and model performance">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { l: "Records / hour", v: "9.4k", i: Database, tone: "primary" },
            { l: "API success rate", v: "99.6%", i: CheckCircle2, tone: "success" },
            { l: "Data delay", v: "12 s", i: Zap, tone: "primary" },
            { l: "Active issues", v: "1", i: AlertTriangle, tone: "warning" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl bg-card p-5">
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.tone === "success" ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]" : s.tone === "warning" ? "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]" : "bg-primary-soft text-accent-foreground"}`}>
                <s.i className="h-5 w-5" />
              </div>
              {loading ? (
                <>
                  <div className="mt-4 h-7 w-20 animate-pulse rounded-md bg-secondary" />
                  <div className="mt-2 h-3 w-24 animate-pulse rounded-md bg-secondary" />
                </>
              ) : (
                <div className="animate-fade-in">
                  <div className="mt-4 text-2xl font-semibold">{s.v}</div>
                  <div className="text-xs text-muted-foreground">{s.l}</div>
                </div>
              )}
            </div>

          ))}
        </div>

        <div className="col-span-12 lg:col-span-8 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Ingestion Throughput</h3>
              <p className="text-xs text-muted-foreground">Traffic + weather records · last 24h</p>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground">Source: TomTom · OpenWeather</span>
          </div>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ingest}>
                <defs>
                  <linearGradient id="m1" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="oklch(0.58 0.21 285)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="t" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Area type="monotone" dataKey="records" stroke="oklch(0.58 0.21 285)" strokeWidth={2.5} fill="url(#m1)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 rounded-3xl bg-card p-6">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold">Pipeline Status</h3>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[oklch(0.93_0.07_155)] px-2 py-0.5 text-[10px] font-medium text-[oklch(0.4_0.15_155)]">
              <span className="relative inline-flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
              </span>
              Live
            </span>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {pipelines.map((p) => (
              <div key={p.name} className="flex items-center justify-between rounded-xl border border-border px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <StatusDot status={p.status} pulse={p.pulse} />
                  <span>{p.name}</span>
                </div>
                <span
                  className={`text-[11px] ${
                    p.status === "healthy"
                      ? "text-muted-foreground"
                      : p.status === "warning"
                      ? "text-[oklch(0.5_0.15_70)]"
                      : "text-destructive"
                  } ${p.pulse ? "animate-pulse rounded-full bg-destructive/10 px-2 py-0.5 font-medium" : ""}`}
                >
                  {p.v}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 text-[11px] text-muted-foreground">
            Last refreshed {secondsAgo}s ago
          </div>
        </div>


        <div className="col-span-12 lg:col-span-7 rounded-3xl bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold">Prediction Latency</h3>
              <p className="text-xs text-muted-foreground">p50 / p95 over last 90 min (ms)</p>
            </div>
            <div className="flex gap-2 text-xs">
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5"><span className="h-2 w-2 rounded-full bg-primary" /> p50</span>
              <span className="flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1.5"><span className="h-2 w-2 rounded-full bg-warning" /> p95</span>
            </div>
          </div>
          <div className="mt-4 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latency}>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="t" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="p50" fill="oklch(0.58 0.21 285)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="p95" fill="oklch(0.78 0.16 70)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 rounded-3xl bg-card p-6">
          <h3 className="text-base font-semibold">Model & Data Quality</h3>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {[
              { l: "MAE", v: "3.21", s: "− 0.12 vs last week" },
              { l: "RMSE", v: "5.07", s: "− 0.08 vs last week" },
              { l: "Drift score", v: "0.14", s: "Stable" },
              { l: "Missing values", v: "0.42%", s: "Threshold 1.0%" },
              { l: "Duplicate rate", v: "0.08%", s: "Threshold 0.5%" },
              { l: "Invalid coords", v: "12", s: "in last 1h" },
            ].map((m) => (
              <div key={m.l} className="rounded-2xl border border-border p-3">
                <div className="text-[11px] text-muted-foreground">{m.l}</div>
                <div className="mt-1 text-lg font-semibold">{m.v}</div>
                <div className="mt-1 text-[10px] text-muted-foreground">{m.s}</div>
              </div>
            ))}
          </div>
          <button className="mt-4 w-full rounded-2xl bg-primary-soft py-3 text-sm font-medium text-accent-foreground">
            <Activity className="mr-2 inline h-4 w-4" /> Trigger model retrain
          </button>
        </div>
      </div>
    </PlaceholderPage>
  );
}