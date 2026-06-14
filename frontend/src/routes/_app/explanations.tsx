import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect, useMemo } from "react";
import useSWR from "swr";
import { Activity, Brain, CloudRain, Database, History, Info, MapPin, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
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
  horizon: fallback(z.enum(["15m", "60m"]), "15m").default("15m"),
});

export const Route = createFileRoute("/_app/explanations")({
  validateSearch: zodValidator(searchSchema),
  component: ExplanationsPage,
});

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
  data_source: string;
  filled_feature_count: number;
  required_feature_count: number;
  available_feature_count: number;
  latest_timestamp?: string | null;
};

type ExplanationFeature = {
  name: string;
  value: number | string | boolean | null;
  baseline_value: number | string | boolean | null;
  shap_value: number;
  direction: "raises_speed" | "lowers_speed";
};

type Explanation = {
  prediction_id: string;
  segment_id: string;
  horizon: "15m" | "60m";
  predicted_speed: number;
  current_speed: number | null;
  current_jam_factor: number | null;
  model_name: string;
  model_artifact: string;
  data_source: string;
  attribution_method: string;
  required_feature_count: number;
  available_feature_count: number;
  filled_feature_count: number;
  missing_features: string[];
  top_features: ExplanationFeature[];
  weather_context: Record<string, number | string | null>;
  baseline_context: Record<string, number | string>;
};

const FEATURE_LABELS: Record<string, string> = {
  congestion_ratio: "Congestion ratio",
  hour_of_day: "Hour of day",
  speed_lag_1: "Speed 15 min ago",
  speed_lag_2: "Speed 30 min ago",
  speed_lag_3: "Speed 45 min ago",
  speed_lag_4: "Speed 60 min ago",
  is_peak_hour: "Peak hour flag",
  day_of_week: "Day of week",
  currentSpeed: "Current speed",
  freeFlowSpeed: "Free-flow speed",
  jamFactor: "Jam factor",
  weather_temperature: "Weather temperature",
  weather_humidity: "Weather humidity",
  weather_rain_1h: "Rain in last hour",
  weather_visibility: "Visibility",
};

function formatSpeed(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} km/h` : "n/a";
}

function formatValue(value: ExplanationFeature["value"]) {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "true" : "false";
  return value ?? "n/a";
}

function featureLabel(name: string) {
  return FEATURE_LABELS[name] ?? name.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function validNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value !== 0 ? value : null;
}

function formatContextSpeed(value: unknown) {
  const numeric = validNumber(value);
  return numeric == null ? "unavailable" : formatSpeed(numeric);
}

function weatherAvailable(weather?: Record<string, number>) {
  if (!weather) return false;
  return Boolean(validNumber(weather.temperature) || validNumber(weather.humidity) || validNumber(weather.visibility) || validNumber(weather.rain_1h));
}

function baselineP50(explanation?: Explanation) {
  return validNumber(explanation?.baseline_context?.p50);
}

function reliabilityLevel(explanation?: Explanation): "High" | "Medium" | "Low" {
  const required = explanation?.required_feature_count ?? 0;
  const available = explanation?.available_feature_count ?? 0;
  if (!required || available / required < 0.9 || (explanation?.missing_features?.length ?? 0) > 5) return "Low";
  return weatherAvailable(explanation?.weather_context) ? "High" : "Medium";
}

function reliabilityText(level: "High" | "Medium" | "Low") {
  if (level === "High") return "Full feature coverage and context data available";
  if (level === "Medium") return "Feature coverage is full, weather context is unavailable";
  return "Many features are missing or filled from defaults";
}

function buildNarrative(explanation?: Explanation, prediction?: Prediction) {
  const predicted = explanation?.predicted_speed ?? prediction?.predicted_speed ?? null;
  const features = explanation?.top_features ?? [];
  const negative = features.find((item) => item.shap_value < 0);
  const positive = features.find((item) => item.shap_value > 0);
  const baseline = baselineP50(explanation);
  const summary = predicted == null
    ? "Select a segment to generate a plain-language model explanation."
    : `The model predicts ${formatSpeed(predicted)} for the next ${explanation?.horizon ?? prediction?.horizon ?? "15m"} because ${
        negative ? featureLabel(negative.name).toLowerCase() + " decreases the expected speed" : "recent conditions keep the forecast close to baseline"
      }${positive ? `, while ${featureLabel(positive.name).toLowerCase()} supports higher speed` : ""}.`;
  const bullets = [
    negative ? `${featureLabel(negative.name)} decreases the forecast.` : "No strong negative driver is dominant.",
    positive ? `${featureLabel(positive.name)} increases the forecast.` : "Positive feature impact is limited.",
    features.some((item) => item.name.includes("lag") || item.name.toLowerCase().includes("speed"))
      ? "Recent speed history is included in the forecast."
      : "Recent speed signal is not a dominant contributor.",
    weatherAvailable(explanation?.weather_context) ? "Weather impact is included in the model context." : "Weather impact is neutral or unavailable.",
    baseline ? "The forecast remains comparable with the historical median baseline." : "Historical baseline is unavailable for this prediction.",
  ];
  return { summary, bullets };
}

function ExplanationsPage() {
  const search = Route.useSearch() as { city: CityKey; segment: string; horizon: "15m" | "60m" };
  const { city, segment, horizon } = search;
  const navigate = useNavigate({ from: "/explanations" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  const { data: segments, error: segmentsError, isLoading: segmentsLoading } = useSWR<TrafficSegment[]>(
    `/traffic/segments?city=${city}&limit=100`,
    apiGet,
    { refreshInterval: 60_000 }
  );

  const selectedSegmentId = segment || segments?.[0]?.segment_id || "";
  const selectedSegment = segments?.find((item) => item.segment_id === selectedSegmentId);

  const { data: prediction, error: predictionError, isLoading: predictionLoading } = useSWR<Prediction>(
    selectedSegmentId ? `/traffic/predict/${encodeURIComponent(selectedSegmentId)}?horizon=${horizon}` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );
  const { data: explanation, error: explanationError, isLoading: explanationLoading } = useSWR<Explanation>(
    selectedSegmentId ? `/predictions/${encodeURIComponent(selectedSegmentId)}/explain?horizon=${horizon}&top_n=10` : null,
    apiGet,
    { refreshInterval: 60_000 }
  );

  useEffect(() => {
    setSelectedCity(city);
    setSelectedSegment(selectedSegmentId || null);
  }, [city, selectedSegmentId, setSelectedCity, setSelectedSegment]);

  const apiError = segmentsError || predictionError || explanationError;
  const loading = segmentsLoading || predictionLoading || explanationLoading;
  const maxImpact = useMemo(
    () => Math.max(1, ...((explanation?.top_features ?? []).map((feature) => Math.abs(feature.shap_value)))),
    [explanation]
  );
  const reliability = reliabilityLevel(explanation);
  const narrative = buildNarrative(explanation, prediction);
  const baselineMedian = baselineP50(explanation);
  const predictedSpeed = explanation?.predicted_speed ?? prediction?.predicted_speed ?? null;
  const featureAdjustment = typeof predictedSpeed === "number" && baselineMedian != null ? predictedSpeed - baselineMedian : null;

  const setCity = (next: CityKey) => navigate({ search: { city: next, segment: "", horizon } });
  const setSegment = (next: string) => navigate({ search: { city, segment: next, horizon } });
  const setHorizon = (next: "15m" | "60m") => navigate({ search: { city, segment: selectedSegmentId, horizon: next } });

  return (
    <PlaceholderPage title="Explanations" subtitle="Model-derived feature attribution for local traffic forecasts">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-wrap items-center gap-2">
          {CITIES.map((item) => (
            <button
              key={item.key}
              onClick={() => setCity(item.key)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${item.key === city ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {item.label}
            </button>
          ))}
          <select
            value={selectedSegmentId}
            onChange={(event) => setSegment(event.target.value)}
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
          <div className="flex rounded-full bg-card p-1">
            {(["15m", "60m"] as const).map((item) => (
              <button
                key={item}
                onClick={() => setHorizon(item)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold ${item === horizon ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {(apiError || loading || !selectedSegmentId) && (
          <div className="col-span-12 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            {apiError
              ? `Explanation API unavailable: ${apiError.message}`
              : loading
                ? "Loading model explanation..."
                : "Select a segment to explain."}
          </div>
        )}

        <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-4">
          <MetricCard icon={Brain} label="Predicted" value={formatSpeed(explanation?.predicted_speed ?? prediction?.predicted_speed)} detail={`${horizon} forecast`} />
          <MetricCard icon={Activity} label="Current" value={formatSpeed(explanation?.current_speed ?? prediction?.current_speed ?? selectedSegment?.current_speed)} detail={`Jam ${explanation?.current_jam_factor ?? prediction?.current_jam_factor ?? selectedSegment?.jam_factor ?? "n/a"}`} />
          <MetricCard icon={Database} label="Model" value={explanation?.model_name ?? prediction?.model_name ?? "n/a"} detail={explanation?.model_artifact ?? prediction?.model_artifact ?? "Waiting for API"} />
          <MetricCard icon={MapPin} label="Segment" value={selectedSegmentId || "n/a"} detail={selectedSegment?.district ?? city} />
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-base font-semibold">
              <Info className="h-4 w-4 text-primary" />
              Why this prediction?
            </div>
            <ReliabilityBadge level={reliability} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{reliabilityText(reliability)}</p>
          <p className="mt-3 text-sm leading-relaxed text-foreground">{narrative.summary}</p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {narrative.bullets.slice(0, 5).map((item) => (
              <div key={item} className="flex gap-2 rounded-2xl bg-secondary px-3 py-2 text-xs text-muted-foreground">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6 lg:col-span-4">
          <div className="flex items-center gap-2 text-base font-semibold">
            <Brain className="h-4 w-4 text-primary" />
            Prediction Breakdown
          </div>
          <div className="mt-4 space-y-3 text-sm">
            <BreakdownRow label="Baseline speed" value={baselineMedian == null ? "unavailable" : formatSpeed(baselineMedian)} />
            <BreakdownRow label="Feature adjustments" value={featureAdjustment == null ? "unavailable" : `${featureAdjustment >= 0 ? "+" : ""}${featureAdjustment.toFixed(1)} km/h`} />
            <BreakdownRow label="Final prediction" value={formatSpeed(predictedSpeed)} strong />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-8 rounded-3xl bg-card p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Top Feature Contributions</h3>
              <p className="text-xs text-muted-foreground">Green features increase the predicted speed. Red features decrease the predicted speed.</p>
            </div>
            <span className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground">
              {explanation?.available_feature_count ?? prediction?.available_feature_count ?? 0}/{explanation?.required_feature_count ?? prediction?.required_feature_count ?? 0} features
            </span>
          </div>
          <div className="mt-5 space-y-3">
            {(explanation?.top_features ?? []).map((feature) => {
              const lowersSpeed = feature.shap_value < 0;
              const width = `${Math.max(6, (Math.abs(feature.shap_value) / maxImpact) * 100)}%`;
              const Icon = lowersSpeed ? TrendingDown : TrendingUp;
              return (
                <div key={feature.name} className="flex items-center gap-3">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${lowersSpeed ? "bg-destructive/10 text-destructive" : "bg-success/10 text-success"}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{featureLabel(feature.name)}</span>
                        <span className="block truncate text-[10px] text-muted-foreground">{feature.name}</span>
                      </span>
                      <span className={`text-xs font-semibold ${lowersSpeed ? "text-destructive" : "text-success"}`}>
                        {feature.shap_value > 0 ? "+" : ""}{feature.shap_value.toFixed(2)} km/h
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
                        <div className={`h-full rounded-full ${lowersSpeed ? "bg-destructive" : "bg-success"}`} style={{ width }} />
                      </div>
                      <span className="w-40 truncate text-right text-[11px] text-muted-foreground">
                        {formatValue(feature.value)} vs {formatValue(feature.baseline_value)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            {explanation && !explanation.top_features.length && (
              <div className="rounded-2xl bg-secondary px-4 py-3 text-sm text-muted-foreground">
                The model returned no non-zero single-feature contributions for this segment.
              </div>
            )}
          </div>
        </div>

        <div className="col-span-12 space-y-4 lg:col-span-4">
          <ContextPanel icon={CloudRain} title="Weather Context">
            {weatherAvailable(explanation?.weather_context) ? (
              <>
                <ContextRow label="Temperature" value={validNumber(explanation?.weather_context.temperature) == null ? "unavailable" : `${validNumber(explanation?.weather_context.temperature)?.toFixed(1)} C`} />
                <ContextRow label="Humidity" value={validNumber(explanation?.weather_context.humidity) == null ? "unavailable" : `${validNumber(explanation?.weather_context.humidity)?.toFixed(0)}%`} />
                <ContextRow label="Rain 1h" value={validNumber(explanation?.weather_context.rain_1h) == null ? "0.0 mm" : `${validNumber(explanation?.weather_context.rain_1h)?.toFixed(1)} mm`} />
                <ContextRow label="Visibility" value={validNumber(explanation?.weather_context.visibility) == null ? "unavailable" : `${validNumber(explanation?.weather_context.visibility)?.toFixed(0)} m`} />
              </>
            ) : (
              <>
                <ContextRow label="Status" value="Weather data unavailable" />
                <ContextRow label="Source" value="OpenWeatherMap" />
                <ContextRow label="Fallback" value="neutral weather features used" />
              </>
            )}
          </ContextPanel>
          <ContextPanel icon={History} title="Baseline Context">
            <ContextRow label="Lower historical baseline" value={formatContextSpeed(explanation?.baseline_context.p15)} />
            <ContextRow label="Median historical baseline" value={formatContextSpeed(explanation?.baseline_context.p50)} />
            <ContextRow label="Upper historical baseline" value={formatContextSpeed(explanation?.baseline_context.p85)} />
            <ContextRow label="Typical speed at selected hour" value={formatContextSpeed(explanation?.baseline_context.typical_hour_avg)} />
          </ContextPanel>
          <ContextPanel icon={Database} title="Attribution">
            <ContextRow label="Method" value={explanation?.attribution_method?.replaceAll("_", " ") ?? "n/a"} />
            <ContextRow label="Source" value={explanation?.data_source ?? prediction?.data_source ?? "n/a"} />
            <ContextRow label="Filled features" value={`${explanation?.filled_feature_count ?? prediction?.filled_feature_count ?? 0}`} />
            <p className="pt-2 text-xs leading-relaxed text-muted-foreground">
              Each feature is replaced with its baseline value one at a time. The change in prediction is used as the feature contribution.
            </p>
          </ContextPanel>
        </div>
      </div>
    </PlaceholderPage>
  );
}

function MetricCard({ icon: Icon, label, value, detail }: { icon: typeof Brain; label: string; value: string; detail: string }) {
  return (
    <div className="rounded-3xl bg-card p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold tracking-widest text-muted-foreground">{label.toUpperCase()}</div>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div className="mt-3 truncate text-2xl font-semibold">{value}</div>
      <div className="mt-3 truncate rounded-xl bg-secondary px-3 py-2 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function ReliabilityBadge({ level }: { level: "High" | "Medium" | "Low" }) {
  const className =
    level === "High"
      ? "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]"
      : level === "Medium"
        ? "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]"
        : "bg-destructive/10 text-destructive";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold ${className}`}>
      <ShieldCheck className="h-3.5 w-3.5" />
      {level} reliability
    </span>
  );
}

function BreakdownRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl bg-secondary px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`truncate text-right ${strong ? "text-base font-semibold" : "font-medium"}`}>{value}</span>
    </div>
  );
}

function ContextPanel({ icon: Icon, title, children }: { icon: typeof Brain; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-primary" />
        {title}
      </div>
      <div className="mt-3 space-y-2 text-xs">{children}</div>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-right font-semibold">{value}</span>
    </div>
  );
}
