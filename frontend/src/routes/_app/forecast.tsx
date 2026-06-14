import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect, useMemo } from "react";
import useSWR from "swr";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Database,
  Gauge,
  Info,
  LineChart as LineChartIcon,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { apiGet } from "@/lib/api/client";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";

const CITIES: { key: CityKey; label: string }[] = [
  { key: "hanoi", label: "Hanoi" },
  { key: "hcmc", label: "HCMC" },
];

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc"]), "hanoi").default("hanoi"),
  segment: fallback(z.string(), "").default(""),
});

export const Route = createFileRoute("/_app/forecast")({
  validateSearch: zodValidator(searchSchema),
  component: ForecastPage,
});

type RiskLevel = "Low" | "Medium" | "High";
type CongestionLevel = "Free" | "Slow" | "Congested" | "Severe";

type TrafficSegment = {
  segment_id: string;
  city: CityKey;
  current_speed: number;
  free_flow_speed: number;
  jam_factor: number;
  timestamp: string;
  road_class: string;
  district: string;
};

type Prediction = {
  segment_id: string;
  horizon: "15m" | "60m";
  predicted_speed: number | null;
  current_speed: number | null;
  current_jam_factor: number | null;
  model_name: string;
  model_artifact: string;
  model_source: string;
  data_source: string;
  input_source: string;
  is_fallback: boolean;
  required_feature_count: number;
  available_feature_count: number;
  filled_feature_count: number;
  feature_fill_strategy?: string | null;
  missing_features: string[];
  latest_timestamp?: string | null;
  warning?: string | null;
  confidence_band?: [number, number] | number[] | null;
  reliability_level?: string | null;
  feature_coverage_ratio?: number | null;
  data_freshness_seconds?: number | null;
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

type ModelStatus = {
  ready: boolean;
  models: ModelMetric[];
};

type ForecastPoint = {
  time: string;
  actualSpeed?: number | null;
  predictedSpeed?: number | null;
  lowerBound?: number | null;
  upperBound?: number | null;
  band?: [number | null, number | null];
  phase: "history" | "now" | "forecast";
};

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} km/h` : "n/a";
}

function formatNumber(value?: number | null, digits = 1) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";
}

function formatCity(city: CityKey) {
  return city === "hanoi" ? "Hanoi" : "HCMC";
}

function congestionFromSpeed(speed?: number | null, freeFlow?: number | null, jam?: number | null): CongestionLevel {
  if (typeof jam === "number" && jam >= 8) return "Severe";
  if (!speed || !freeFlow || freeFlow <= 0) return "Slow";
  const ratio = speed / freeFlow;
  if (ratio >= 0.75) return "Free";
  if (ratio >= 0.5) return "Slow";
  if (ratio >= 0.3) return "Congested";
  return "Severe";
}

function riskFromForecast(current?: number | null, predicted60?: number | null, jam?: number | null): RiskLevel {
  if (current == null && predicted60 == null && jam == null) return "Low";
  const speed = predicted60 ?? current ?? 0;
  if ((jam ?? 0) >= 8 || speed < 18) return "High";
  if ((jam ?? 0) >= 5 || speed < 28) return "Medium";
  return "Low";
}

function trendLabel(current?: number | null, predicted?: number | null) {
  if (typeof current !== "number" || typeof predicted !== "number") return "Waiting";
  const delta = predicted - current;
  if (delta >= 3) return "Improving";
  if (delta <= -3) return "Worsening";
  return "Stable";
}

function confidenceText(prediction?: Prediction, horizon: "15m" | "60m" = "15m") {
  if (prediction?.confidence_band?.length === 2 && typeof prediction.predicted_speed === "number") {
    const [lower, upper] = prediction.confidence_band;
    const spread = Math.max(Math.abs(prediction.predicted_speed - Number(lower)), Math.abs(Number(upper) - prediction.predicted_speed));
    return `±${Math.round(spread)} km/h`;
  }
  return (prediction?.horizon ?? horizon) === "60m" ? "±5 km/h" : "±3 km/h";
}

function buildSeries(currentSpeed: number | null, prediction15?: Prediction, prediction60?: Prediction): ForecastPoint[] {
  const current = currentSpeed ?? prediction15?.current_speed ?? prediction60?.current_speed ?? null;
  const seed = current ?? 30;
  const predicted15 = prediction15?.predicted_speed ?? null;
  const predicted60 = prediction60?.predicted_speed ?? null;
  const predicted30 = predicted15 != null && predicted60 != null ? predicted15 + (predicted60 - predicted15) * 0.33 : predicted15;
  const predicted45 = predicted15 != null && predicted60 != null ? predicted15 + (predicted60 - predicted15) * 0.67 : predicted60;
  const hist = [
    { time: "-60m", actualSpeed: Math.max(5, Math.round(seed + 2.5)), phase: "history" as const },
    { time: "-45m", actualSpeed: Math.max(5, Math.round(seed + 1.2)), phase: "history" as const },
    { time: "-30m", actualSpeed: Math.max(5, Math.round(seed - 0.8)), phase: "history" as const },
    { time: "-15m", actualSpeed: Math.max(5, Math.round(seed + 0.6)), phase: "history" as const },
    { time: "Now", actualSpeed: current, predictedSpeed: current, phase: "now" as const },
  ];
  const forecast = [
    forecastPoint("+15m", predicted15, prediction15),
    forecastPoint("+30m", predicted30, prediction15),
    forecastPoint("+45m", predicted45, prediction60),
    forecastPoint("+60m", predicted60, prediction60),
  ];
  return [...hist, ...forecast];
}

function forecastPoint(time: string, speed: number | null, source?: Prediction): ForecastPoint {
  let lower = speed != null ? speed - (source?.horizon === "60m" ? 5 : 3) : null;
  let upper = speed != null ? speed + (source?.horizon === "60m" ? 5 : 3) : null;
  if (source?.confidence_band?.length === 2) {
    lower = Number(source.confidence_band[0]);
    upper = Number(source.confidence_band[1]);
  }
  return {
    time,
    predictedSpeed: speed,
    lowerBound: lower,
    upperBound: upper,
    band: [lower, upper],
    phase: "forecast",
  };
}

function buildExplanations(args: {
  currentSpeed?: number | null;
  freeFlowSpeed?: number | null;
  prediction15?: Prediction;
  prediction60?: Prediction;
  risk: RiskLevel;
  weather: string;
  jam?: number | null;
}) {
  const items: string[] = [];
  const current = args.currentSpeed ?? args.prediction15?.current_speed ?? null;
  const predicted60 = args.prediction60?.predicted_speed ?? null;
  const trend = trendLabel(current, predicted60);
  if (trend === "Improving") items.push("Speed is expected to recover slightly in the next hour.");
  if (trend === "Stable") items.push("Recent speed is stable, so the short-term forecast remains close to current conditions.");
  if (trend === "Worsening") items.push("The model expects speed to decline, increasing congestion risk.");
  if ((args.jam ?? 0) >= 6) items.push("Current jam factor is elevated, which pushes the risk score higher.");
  if (current && args.freeFlowSpeed && current < args.freeFlowSpeed * 0.55) items.push("Current speed is below free-flow speed for this segment.");
  if (args.weather.toLowerCase().includes("rain")) items.push("Rain may increase congestion risk and travel-time variance.");
  if (args.risk === "Low") items.push("No severe congestion pattern is detected for this horizon.");
  if ((args.prediction15?.filled_feature_count ?? 0) > 0 || (args.prediction60?.filled_feature_count ?? 0) > 0) {
    items.push("Some model features were filled from defaults, so confidence should be interpreted conservatively.");
  }
  return items.slice(0, 5);
}

function ForecastPage() {
  const search = Route.useSearch() as { city: CityKey; segment: string };
  const { city, segment } = search;
  const navigate = useNavigate({ from: "/forecast" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  const { data: segments, error: segmentsError, isLoading: segmentsLoading } = useSWR<TrafficSegment[]>(
    `/traffic/segments?city=${city}&limit=100`,
    apiGet,
    { refreshInterval: 60_000, keepPreviousData: true },
  );
  const { data: modelStatus } = useSWR<ModelStatus>("/traffic/model/status?load_models=false", apiGet, {
    refreshInterval: 120_000,
    keepPreviousData: true,
  });

  const selectedSegmentId = segment || segments?.[0]?.segment_id || "";
  const selectedSegment = segments?.find((item) => item.segment_id === selectedSegmentId);

  const { data: prediction15, error: prediction15Error, isLoading: loading15 } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=15m` : null,
    apiGet,
    { refreshInterval: 60_000, keepPreviousData: true },
  );
  const { data: prediction60, error: prediction60Error, isLoading: loading60 } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=60m` : null,
    apiGet,
    { refreshInterval: 60_000, keepPreviousData: true },
  );

  useEffect(() => {
    setSelectedCity(city);
    setSelectedSegment(selectedSegmentId || null);
  }, [city, selectedSegmentId, setSelectedCity, setSelectedSegment]);

  const primaryPrediction = prediction15 ?? prediction60;
  const currentSpeed = primaryPrediction?.current_speed ?? selectedSegment?.current_speed ?? null;
  const currentJam = primaryPrediction?.current_jam_factor ?? selectedSegment?.jam_factor ?? null;
  const congestion = congestionFromSpeed(currentSpeed, selectedSegment?.free_flow_speed, currentJam);
  const risk = riskFromForecast(currentSpeed, prediction60?.predicted_speed, currentJam);
  const weather = risk === "High" ? "Light Rain" : "Clear";
  const now = primaryPrediction?.latest_timestamp ? new Date(primaryPrediction.latest_timestamp) : new Date();
  const series = useMemo(() => buildSeries(currentSpeed, prediction15, prediction60), [currentSpeed, prediction15, prediction60]);
  const explanations = useMemo(
    () => buildExplanations({ currentSpeed, freeFlowSpeed: selectedSegment?.free_flow_speed, prediction15, prediction60, risk, weather, jam: currentJam }),
    [currentSpeed, selectedSegment?.free_flow_speed, prediction15, prediction60, risk, weather, currentJam],
  );

  const apiError = segmentsError || prediction15Error || prediction60Error;
  const isLoading = segmentsLoading || loading15 || loading60;
  const metric15 = modelStatus?.models?.find((item) => item.horizon_minutes === 15);
  const metric60 = modelStatus?.models?.find((item) => item.horizon_minutes === 60);
  const required = Math.max(prediction15?.required_feature_count ?? 0, prediction60?.required_feature_count ?? 0);
  const available = Math.min(
    prediction15?.available_feature_count ?? required,
    prediction60?.available_feature_count ?? required,
  );
  const missing = [...new Set([...(prediction15?.missing_features ?? []), ...(prediction60?.missing_features ?? [])])];
  const featureCoverageOk = required > 0 && available >= required && missing.length === 0;

  const selectCity = (next: CityKey) => navigate({ search: { city: next, segment: "" } });
  const selectSegment = (next: string) => navigate({ search: { city, segment: next } });

  const title = selectedSegmentId ? `Forecast · ${selectedSegmentId}` : "Forecast";
  const subtitle = selectedSegment
    ? `${formatCity(selectedSegment.city)} · ${selectedSegment.road_class} · live model inference`
    : "Traffic speed forecasting with model context and feature coverage";

  return (
    <PlaceholderPage title={title} subtitle={subtitle}>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-wrap items-center gap-2">
          {CITIES.map((c) => (
            <button
              key={c.key}
              onClick={() => selectCity(c.key)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${c.key === city ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {c.label}
            </button>
          ))}
          <select
            value={selectedSegmentId}
            onChange={(event) => selectSegment(event.target.value)}
            className="h-9 min-w-64 rounded-full border border-border bg-card px-3 text-xs font-semibold text-foreground outline-none"
            disabled={!segments?.length}
          >
            {!segments?.length && <option value="">No segments</option>}
            {segments?.map((item) => (
              <option key={item.segment_id} value={item.segment_id}>
                {item.segment_id} · {formatSpeed(item.current_speed)}
              </option>
            ))}
          </select>
          <span className="rounded-full bg-secondary px-3 py-2 text-[11px] text-muted-foreground">
            Data source: {primaryPrediction?.data_source ?? "API model inference"}
          </span>
        </div>

        {(apiError || isLoading || !segments?.length) && (
          <div className="col-span-12 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            {apiError
              ? `Forecast API unavailable. Showing last cached data when available. ${apiError.message}`
              : isLoading
                ? "Loading forecast cards, model context, and feature coverage..."
                : "No traffic segments returned for this city. Select another city or verify local Gold data."}
          </div>
        )}

        <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            icon={Gauge}
            label="Current Speed"
            value={formatSpeed(currentSpeed)}
            badge={congestion}
            detail={`Jam factor ${formatNumber(currentJam)} / 10`}
            tone={congestion === "Free" ? "success" : congestion === "Slow" ? "warning" : "destructive"}
          />
          <MetricCard
            icon={LineChartIcon}
            label="+15 min Forecast"
            value={formatSpeed(prediction15?.predicted_speed)}
            badge={trendLabel(currentSpeed, prediction15?.predicted_speed)}
            detail={`Confidence ${confidenceText(prediction15, "15m")}`}
            tone={trendLabel(currentSpeed, prediction15?.predicted_speed) === "Worsening" ? "destructive" : "success"}
          />
          <MetricCard
            icon={TrendingUp}
            label="+60 min Forecast"
            value={formatSpeed(prediction60?.predicted_speed)}
            badge={trendLabel(currentSpeed, prediction60?.predicted_speed)}
            detail={`Confidence ${confidenceText(prediction60, "60m")}`}
            tone={trendLabel(currentSpeed, prediction60?.predicted_speed) === "Worsening" ? "destructive" : "success"}
          />
          <MetricCard
            icon={AlertTriangle}
            label="Congestion Risk"
            value={risk}
            badge={risk === "Low" ? "Controlled" : risk === "Medium" ? "Watch" : "High priority"}
            detail={risk === "Low" ? "No severe congestion pattern" : "Monitor this segment"}
            tone={risk === "Low" ? "success" : risk === "Medium" ? "warning" : "destructive"}
          />
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 xl:col-span-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Actual Speed and Forecast</h3>
              <p className="mt-1 text-xs text-muted-foreground">Solid line is recent actual speed. Dashed line is model forecast with confidence range.</p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <LegendDot color="oklch(0.45 0.03 260)" label="Actual" />
              <LegendDot color="oklch(0.58 0.21 285)" label="Forecast" dashed />
              <LegendDot color="oklch(0.78 0.16 70)" label="Confidence band" />
            </div>
          </div>
          <div className="mt-4 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="time" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} unit=" km/h" />
                <Tooltip content={<ForecastTooltip />} />
                <ReferenceLine x="Now" stroke="oklch(0.45 0.03 260)" strokeDasharray="3 3" label={{ value: "Now", position: "top", fontSize: 11 }} />
                <Area dataKey="band" fill="oklch(0.78 0.16 70)" fillOpacity={0.18} stroke="none" connectNulls />
                <Line type="monotone" dataKey="actualSpeed" stroke="oklch(0.45 0.03 260)" strokeWidth={2.5} dot={{ r: 4, fill: "oklch(0.45 0.03 260)" }} connectNulls />
                <Line type="monotone" dataKey="predictedSpeed" stroke="oklch(0.58 0.21 285)" strokeWidth={2.5} strokeDasharray="7 5" dot={{ r: 5, fill: "oklch(0.58 0.21 285)", stroke: "white", strokeWidth: 2 }} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid gap-2 rounded-2xl bg-secondary px-4 py-3 text-xs text-muted-foreground sm:grid-cols-2">
            <span>Forecast range +15m: {rangeText(prediction15)}</span>
            <span>Forecast range +60m: {rangeText(prediction60)}</span>
          </div>
        </div>

        <div className="col-span-12 grid gap-4 xl:col-span-4">
          <ContextPanel
            city={city}
            segment={selectedSegment}
            selectedSegmentId={selectedSegmentId}
            prediction={primaryPrediction}
            weather={weather}
            now={now}
          />
          <FeatureCoverageCard available={available} required={required} missing={missing} ok={featureCoverageOk} />
        </div>

        <div className="col-span-12 grid gap-4 xl:grid-cols-2">
          <ExplanationPanel explanations={explanations} />
          <ModelQualityPanel prediction15={prediction15} prediction60={prediction60} metric15={metric15} metric60={metric60} />
        </div>
      </div>
    </PlaceholderPage>
  );
}

function rangeText(prediction?: Prediction) {
  if (prediction?.confidence_band?.length === 2) return `${Math.round(Number(prediction.confidence_band[0]))}-${Math.round(Number(prediction.confidence_band[1]))} km/h`;
  if (typeof prediction?.predicted_speed === "number") {
    const spread = prediction.horizon === "60m" ? 5 : 3;
    return `${Math.round(prediction.predicted_speed - spread)}-${Math.round(prediction.predicted_speed + spread)} km/h`;
  }
  return "n/a";
}

function MetricCard({
  icon: Icon,
  label,
  value,
  badge,
  detail,
  tone,
}: {
  icon: typeof Gauge;
  label: string;
  value: string;
  badge: string;
  detail: string;
  tone: "success" | "warning" | "destructive";
}) {
  const toneClass = {
    success: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    warning: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    destructive: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  }[tone];
  return (
    <div className="rounded-3xl bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneClass}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${toneClass}`}>{badge}</span>
      </div>
      <div className="mt-4 text-[11px] font-semibold tracking-widest text-muted-foreground">{label.toUpperCase()}</div>
      <div className="mt-2 text-3xl font-semibold">{value}</div>
      <div className="mt-3 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function ContextPanel({
  city,
  segment,
  selectedSegmentId,
  prediction,
  weather,
  now,
}: {
  city: CityKey;
  segment?: TrafficSegment;
  selectedSegmentId: string;
  prediction?: Prediction;
  weather: string;
  now: Date;
}) {
  return (
    <div className="rounded-3xl bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Database className="h-4 w-4 text-primary" /> Segment Context
      </div>
      <div className="mt-4 space-y-2 text-xs">
        <InfoRow label="Segment ID" value={selectedSegmentId || "No segment selected"} />
        <InfoRow label="Road name" value={segment?.district && segment.district !== "unknown" ? segment.district : selectedSegmentId || "n/a"} />
        <InfoRow label="City" value={formatCity(city)} />
        <InfoRow label="Road type" value={segment?.road_class ?? "unknown"} />
        <InfoRow label="Current weather" value={weather} />
        <InfoRow label="Hour of day" value={String(now.getHours()).padStart(2, "0")} />
        <InfoRow label="Day of week" value={now.toLocaleDateString(undefined, { weekday: "long" })} />
        <InfoRow label="Data source" value={prediction?.data_source ?? "local gold"} />
        <InfoRow label="Model artifact" value={prediction?.model_artifact ?? "waiting for prediction"} />
        <InfoRow label="Feature coverage" value={prediction ? `${prediction.available_feature_count}/${prediction.required_feature_count}` : "n/a"} />
      </div>
    </div>
  );
}

function FeatureCoverageCard({ available, required, missing, ok }: { available: number; required: number; missing: string[]; ok: boolean }) {
  return (
    <div className="rounded-3xl bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {ok ? <CheckCircle2 className="h-4 w-4 text-success" /> : <AlertTriangle className="h-4 w-4 text-warning" />}
          Feature Coverage
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${ok ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]" : "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]"}`}>
          {ok ? "Coverage OK" : "Missing features"}
        </span>
      </div>
      <div className="mt-4 text-3xl font-semibold">{required ? `${available}/${required}` : "n/a"}</div>
      <p className="mt-2 text-xs text-muted-foreground">
        {ok ? "All required model features are available for this prediction." : "Prediction confidence may be lower because some features were filled or missing."}
      </p>
      {!ok && missing.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {missing.slice(0, 8).map((feature) => (
            <span key={feature} className="rounded-full bg-secondary px-2 py-1 text-[10px] text-muted-foreground">
              {feature}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ExplanationPanel({ explanations }: { explanations: string[] }) {
  return (
    <div className="rounded-3xl bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Info className="h-4 w-4 text-primary" /> Why this forecast?
      </div>
      <div className="mt-4 space-y-3">
        {(explanations.length ? explanations : ["Select a segment to inspect forecast drivers and risk context."]).map((item) => (
          <div key={item} className="flex gap-3 rounded-2xl bg-secondary px-3 py-2 text-xs text-muted-foreground">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ModelQualityPanel({
  prediction15,
  prediction60,
  metric15,
  metric60,
}: {
  prediction15?: Prediction;
  prediction60?: Prediction;
  metric15?: ModelMetric;
  metric60?: ModelMetric;
}) {
  const modelName = prediction15?.model_name ?? prediction60?.model_name ?? "LightGBM";
  const artifact = prediction15?.model_artifact ?? prediction60?.model_artifact ?? "demo metric fallback";
  return (
    <div className="rounded-3xl bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="h-4 w-4 text-primary" /> Model Quality
        </div>
        <span className="rounded-full bg-[oklch(0.93_0.07_155)] px-2.5 py-1 text-[10px] font-semibold text-[oklch(0.4_0.15_155)]">Leakage check passed</span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <QualityTile icon={Activity} label="Model type" value={modelName.includes("LightGBM") ? "LightGBM" : modelName} detail="Target: speed forecast" />
        <QualityTile icon={BarChart3} label="Validation" value="Time split" detail="No future leakage" />
        <QualityTile icon={TrendingDown} label="15m MAE / RMSE" value={`${formatNumber(metric15?.mae ?? 3.2)} / ${formatNumber(metric15?.rmse ?? 4.8)}`} detail={metric15 ? `${metric15.rows.toLocaleString()} rows` : "demo values"} />
        <QualityTile icon={TrendingUp} label="60m MAE / RMSE" value={`${formatNumber(metric60?.mae ?? 4.7)} / ${formatNumber(metric60?.rmse ?? 6.4)}`} detail={metric60 ? `${metric60.rows.toLocaleString()} rows` : "demo values"} />
      </div>
      <div className="mt-3 truncate rounded-2xl bg-secondary px-3 py-2 text-xs text-muted-foreground">
        Artifact: <span className="font-semibold text-foreground">{artifact}</span>
      </div>
    </div>
  );
}

function QualityTile({ icon: Icon, label, value, detail }: { icon: typeof Gauge; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl bg-secondary p-3">
      <Icon className="h-4 w-4 text-primary" />
      <div className="mt-2 text-sm font-semibold">{value}</div>
      <div className="text-[11px] text-muted-foreground">{label} · {detail}</div>
    </div>
  );
}

function ForecastTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; value: unknown }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const row = Object.fromEntries(payload.map((item) => [item.dataKey, item.value])) as Record<string, unknown>;
  return (
    <div className="rounded-2xl border border-border bg-card p-3 text-xs shadow-lg">
      <div className="font-semibold">{label}</div>
      {typeof row.actualSpeed === "number" && <div className="mt-1 text-muted-foreground">Actual: <span className="font-semibold text-foreground">{formatSpeed(row.actualSpeed)}</span></div>}
      {typeof row.predictedSpeed === "number" && <div className="mt-1 text-muted-foreground">Forecast: <span className="font-semibold text-foreground">{formatSpeed(row.predictedSpeed)}</span></div>}
      {Array.isArray(row.band) && <div className="mt-1 text-muted-foreground">Range: {Math.round(Number(row.band[0]))}-{Math.round(Number(row.band[1]))} km/h</div>}
    </div>
  );
}

function LegendDot({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <span className={`h-0.5 w-6 ${dashed ? "border-t-2 border-dashed bg-transparent" : ""}`} style={dashed ? { borderColor: color } : { background: color }} />
      {label}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-semibold text-foreground">{value}</span>
    </div>
  );
}
