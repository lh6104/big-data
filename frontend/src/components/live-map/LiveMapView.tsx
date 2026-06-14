import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Circle, CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  AlertTriangle,
  BarChart3,
  CloudRain,
  Clock,
  Gauge,
  Layers,
  MapPin,
  RefreshCw,
  ShieldAlert,
  ThermometerSun,
  TrendingDown,
  Wind,
  X,
} from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

type City = "All" | "Hanoi" | "HCMC";
type ConcreteCity = Exclude<City, "All">;
type Congestion = "All" | "Free" | "Slow" | "Congested" | "Severe";
type RoadType = "All" | "Highway" | "Arterial" | "Collector" | "Local";
type CoverageDensity = "Low" | "Medium" | "High";
type WeatherCondition = "Clear" | "Cloudy" | "Light Rain" | "Heavy Rain" | "Low Visibility";
type WeatherRisk = "Low" | "Medium" | "High";
type AlertType = "Sudden Speed Drop" | "Severe Congestion" | "Rain Impact" | "Travel Time Spike";

type Segment = {
  segment_id: string;
  name: string;
  road_type: Exclude<RoadType, "All">;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  currentSpeed: number;
  freeFlowSpeed: number;
  jamFactor: number;
  confidence: number;
  city: ConcreteCity;
  weather: { condition: string; temp: number; visibilityKm: number };
  updatedAt: string;
  incident?: string;
  source?: string;
  provider?: string;
  speedRatio?: number;
  congestionLevel?: Exclude<Congestion, "All">;
  travelTimeDelayMin?: number;
};

type SegmentView = Segment & {
  congestionLevel: Exclude<Congestion, "All">;
  speedRatio: number;
  travelTimeDelayMin: number;
  weatherCondition: WeatherCondition;
  weatherRisk: WeatherRisk;
  speedTrend: Array<{ time: string; speed: number }>;
  jamTrend: Array<{ time: string; jamFactor: number }>;
};

type Hotspot = {
  cluster_id: string;
  label: string;
  center_lat: number;
  center_lon: number;
  severity: "Critical" | "High" | "Medium" | "Low";
  segment_count: number;
  avg_speed: number;
  city: ConcreteCity;
};

type TrafficAlert = {
  id: string;
  type: AlertType;
  roadName: string;
  city: ConcreteCity;
  severity: "Low" | "Medium" | "High";
  possibleCause: string;
  timestamp: string;
  coordinate: [number, number];
  segmentId?: string;
};

type WeatherZone = {
  id: string;
  city: ConcreteCity;
  label: WeatherCondition;
  risk: WeatherRisk;
  center: [number, number];
  radius: number;
};

type LiveMapSegmentResponse = {
  segments: Array<{
    id: string;
    name: string;
    city: "hanoi" | "hcmc";
    roadType: Exclude<RoadType, "All"> | "highway" | "arterial" | "collector" | "local";
    geometry: { type: "LineString"; coordinates: [number, number][] };
    currentSpeed: number;
    freeFlowSpeed: number;
    speedRatio: number;
    jamFactor: number;
    congestionLevel: Exclude<Congestion, "All">;
    travelTimeDelayMin: number;
    source: string;
    provider?: string;
    latestTimestamp?: string;
    confidence?: number;
  }>;
};

type ApiHotspot = {
  hotspot_id: string;
  cluster_id: number;
  city: "hanoi" | "hcmc";
  center_lat: number;
  center_lon: number;
  radius_km: number;
  num_segments: number;
  avg_congestion: number;
  avg_jam_factor: number;
  severity: "critical" | "high" | "medium" | "low";
  detected_at: string;
};

const CITY_CENTER: Record<City, { lat: number; lng: number; zoom: number }> = {
  All: { lat: 16.2, lng: 106.4, zoom: 6 },
  Hanoi: { lat: 21.0285, lng: 105.8542, zoom: 13 },
  HCMC: { lat: 10.7769, lng: 106.7009, zoom: 13 },
};

const CONG_COLOR: Record<Exclude<Congestion, "All">, string> = {
  Free: "#16a34a",
  Slow: "#f59e0b",
  Congested: "#ef4444",
  Severe: "#7f1d1d",
};

const SEVERITY_COLOR: Record<TrafficAlert["severity"], string> = {
  Low: "#f59e0b",
  Medium: "#ef4444",
  High: "#7f1d1d",
};

const WEATHER_COLOR: Record<WeatherCondition, string> = {
  Clear: "#22c55e",
  Cloudy: "#94a3b8",
  "Light Rain": "#38bdf8",
  "Heavy Rain": "#2563eb",
  "Low Visibility": "#60a5fa",
};

const WEATHER_ZONES: WeatherZone[] = [
  { id: "hn-rain-west", city: "Hanoi", label: "Light Rain", risk: "Medium", center: [21.017, 105.79], radius: 2600 },
  { id: "hn-heavy-south", city: "Hanoi", label: "Heavy Rain", risk: "High", center: [20.985, 105.84], radius: 2200 },
  { id: "hn-visibility-north", city: "Hanoi", label: "Low Visibility", risk: "Medium", center: [21.075, 105.83], radius: 2400 },
  { id: "hcm-rain-core", city: "HCMC", label: "Light Rain", risk: "Medium", center: [10.778, 106.7], radius: 2600 },
  { id: "hcm-heavy-east", city: "HCMC", label: "Heavy Rain", risk: "High", center: [10.81, 106.76], radius: 3000 },
  { id: "hcm-visibility-south", city: "HCMC", label: "Low Visibility", risk: "Medium", center: [10.72, 106.72], radius: 2600 },
];

function severityLabel(severity: ApiHotspot["severity"]): Hotspot["severity"] {
  if (severity === "critical") return "Critical";
  if (severity === "high") return "High";
  if (severity === "medium") return "Medium";
  return "Low";
}

function congestionFromSpeedRatio(speedRatio: number): Exclude<Congestion, "All"> {
  if (speedRatio >= 0.75) return "Free";
  if (speedRatio >= 0.5) return "Slow";
  if (speedRatio >= 0.3) return "Congested";
  return "Severe";
}

function roadTypeLabel(roadType: Segment["road_type"] | string): Exclude<RoadType, "All"> {
  const normalized = String(roadType).toLowerCase();
  if (normalized === "highway") return "Highway";
  if (normalized === "collector") return "Collector";
  if (normalized === "local") return "Local";
  return "Arterial";
}

function sourceLabel(source?: string) {
  if (!source) return "Local Gold Data";
  if (source === "tomtom") return "TomTom API";
  if (source === "curated_demo") return "Curated road demo";
  if (source === "local_gold") return "Local Gold Data";
  return source.replaceAll("_", " ");
}

function sourceRank(source?: string) {
  if (source === "tomtom") return 0;
  if (source === "local_gold") return 1;
  if (source === "curated_demo") return 2;
  return 3;
}

function midpoint(segment: Segment): [number, number] {
  const coordinates = segment.geometry.coordinates;
  const point = coordinates[Math.max(0, Math.floor(coordinates.length / 2))] ?? coordinates[0];
  return [point?.[1] ?? CITY_CENTER[segment.city].lat, point?.[0] ?? CITY_CENTER[segment.city].lng];
}

function stableValue(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return hash;
}

function weatherForSegment(segment: Segment, refreshKey: number): { condition: WeatherCondition; risk: WeatherRisk } {
  if (segment.jamFactor >= 8) return { condition: "Heavy Rain", risk: "High" };
  if (segment.jamFactor >= 6) return { condition: "Light Rain", risk: "Medium" };
  const pick = (stableValue(segment.segment_id) + refreshKey) % 5;
  if (pick === 0) return { condition: "Low Visibility", risk: "Medium" };
  if (pick === 1) return { condition: "Cloudy", risk: "Low" };
  return { condition: "Clear", risk: "Low" };
}

function buildTrends(segment: Segment, refreshKey: number) {
  const base = stableValue(segment.segment_id) % 7;
  const times = ["-25m", "-20m", "-15m", "-10m", "-5m", "now"];
  const speedTrend = times.map((time, idx) => {
    const drift = Math.sin((idx + base + refreshKey) * 0.9) * 4;
    return { time, speed: Math.max(5, Math.round(segment.currentSpeed + drift + (idx - 3) * 0.8)) };
  });
  const jamTrend = times.map((time, idx) => {
    const drift = Math.cos((idx + base + refreshKey) * 0.7) * 0.8;
    return { time, jamFactor: Number(Math.min(10, Math.max(0, segment.jamFactor + drift)).toFixed(1)) };
  });
  return { speedTrend, jamTrend };
}

function enhanceSegment(segment: Segment, refreshKey: number): SegmentView {
  const weather = weatherForSegment(segment, refreshKey);
  const trends = buildTrends(segment, refreshKey);
  const speedRatio = segment.speedRatio ?? (segment.freeFlowSpeed > 0 ? segment.currentSpeed / segment.freeFlowSpeed : 0);
  const travelTimeDelayMin = segment.travelTimeDelayMin ?? Math.max(0, Math.round((1 - speedRatio) * 18 + segment.jamFactor * 0.6));
  return {
    ...segment,
    congestionLevel: segment.congestionLevel ?? congestionFromSpeedRatio(speedRatio),
    speedRatio,
    travelTimeDelayMin,
    weatherCondition: weather.condition,
    weatherRisk: weather.risk,
    ...trends,
  };
}

function FlyTo({ city }: { city: City }) {
  const map = useMap();
  useEffect(() => {
    const c = CITY_CENTER[city];
    map.flyTo([c.lat, c.lng], c.zoom, { duration: 0.8 });
  }, [city, map]);
  return null;
}

function FocusSelected({ segment }: { segment: SegmentView | null }) {
  const map = useMap();
  useEffect(() => {
    if (!segment) return;
    map.flyTo(midpoint(segment), Math.max(map.getZoom(), 13), { duration: 0.45 });
  }, [segment?.segment_id, map]);
  return null;
}

function ViewportTracker({ onViewportChange }: { onViewportChange: (viewport: { bbox: string; zoom: number }) => void }) {
  const report = (map: LeafletMap) => {
    const bounds = map.getBounds();
    onViewportChange({
      bbox: [
        bounds.getWest().toFixed(5),
        bounds.getSouth().toFixed(5),
        bounds.getEast().toFixed(5),
        bounds.getNorth().toFixed(5),
      ].join(","),
      zoom: map.getZoom(),
    });
  };

  const map = useMapEvents({
    moveend: () => report(map),
    zoomend: () => report(map),
  });

  useEffect(() => {
    report(map);
  }, [map, onViewportChange]);

  return null;
}

function densityLimit(density: CoverageDensity, zoom: number) {
  const base = density === "Low" ? 45 : density === "High" ? 220 : 120;
  if (zoom <= 11) return Math.min(base, density === "High" ? 90 : 55);
  if (zoom >= 15) return density === "High" ? 240 : density === "Medium" ? 150 : 65;
  return base;
}

export function LiveMapView({
  onViewForecast,
  city: cityProp,
  onCityChange,
}: {
  onViewForecast: (segmentId: string) => void;
  city?: City;
  onCityChange?: (city: City) => void;
}) {
  const [internalCity, setInternalCity] = useState<City>("Hanoi");
  const city = cityProp ?? internalCity;
  const setCity = (next: City) => {
    setBbox(null);
    setZoom(CITY_CENTER[next].zoom);
    setSelectedId(null);
    setInternalCity(next);
    onCityChange?.(next);
  };
  const [congestion, setCongestion] = useState<Congestion>("All");
  const [roadType, setRoadType] = useState<RoadType>("All");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [bbox, setBbox] = useState<string | null>(null);
  const [zoom, setZoom] = useState(CITY_CENTER[city].zoom);
  const [coverageDensity, setCoverageDensity] = useState<CoverageDensity>("Medium");
  const [mounted, setMounted] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [layers, setLayers] = useState({
    roadSegments: true,
    heatmap: false,
    weather: true,
    alerts: true,
  });

  const apiCity = city === "All" ? "all" : city === "Hanoi" ? "hanoi" : "hcmc";
  const segmentLimit = densityLimit(coverageDensity, zoom);
  const segmentEndpoint = `/segments/live-map?city=${apiCity}&limit=${segmentLimit}&density=${coverageDensity.toLowerCase()}&zoom=${Math.round(zoom)}${bbox ? `&bbox=${bbox}` : ""}&refresh=${refreshKey}`;
  const { data: liveMapData, error: segmentError, isLoading: segmentsLoading, mutate: reloadSegments } =
    useSWR<LiveMapSegmentResponse>(segmentEndpoint, apiGet, {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    });
  const { data: hotspotData, error: hotspotError, isLoading: hotspotsLoading, mutate: reloadHotspots } =
    useSWR<ApiHotspot[]>(`/hotspots?city=${apiCity}&refresh=${refreshKey}`, apiGet, {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    });

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (segmentError) console.error("Live Map segments API unavailable", segmentError);
  }, [segmentError]);

  useEffect(() => {
    if (hotspotError) console.error("Live Map hotspots API unavailable", hotspotError);
  }, [hotspotError]);

  const apiSegments = useMemo<Segment[]>(() => {
    if (!liveMapData?.segments?.length) return [];
    return [...liveMapData.segments].sort((a, b) => sourceRank(a.source) - sourceRank(b.source)).map((segment) => ({
      segment_id: segment.id,
      name: segment.name,
      road_type: roadTypeLabel(segment.roadType),
      geometry: segment.geometry,
      currentSpeed: segment.currentSpeed,
      freeFlowSpeed: segment.freeFlowSpeed,
      jamFactor: segment.jamFactor,
      confidence: segment.confidence ?? 1,
      city: segment.city === "hcmc" ? "HCMC" : "Hanoi",
      weather: { condition: "OpenWeatherMap", temp: segment.city === "hcmc" ? 31 : 27, visibilityKm: 8 },
      updatedAt: segment.latestTimestamp ?? new Date().toISOString(),
      source: segment.source,
      provider: segment.provider,
      speedRatio: segment.speedRatio,
      congestionLevel: segment.congestionLevel,
      travelTimeDelayMin: segment.travelTimeDelayMin,
    }));
  }, [liveMapData]);

  const enhancedSegments = useMemo(
    () => apiSegments.map((segment) => enhanceSegment(segment, refreshKey)),
    [apiSegments, refreshKey],
  );

  const apiHotspots = useMemo<Hotspot[]>(() => {
    if (!hotspotData?.length) return [];
    return hotspotData.map((hotspot) => ({
      cluster_id: hotspot.hotspot_id,
      label: `Cluster ${hotspot.cluster_id}`,
      center_lat: hotspot.center_lat,
      center_lon: hotspot.center_lon,
      severity: severityLabel(hotspot.severity),
      segment_count: hotspot.num_segments,
      avg_speed: Math.max(0, Math.round(50 - hotspot.avg_congestion)),
      city: hotspot.city === "hanoi" ? "Hanoi" : "HCMC",
    }));
  }, [hotspotData]);

  const filteredSegments = useMemo(() => {
    return enhancedSegments
      .filter((s) => (city === "All" ? true : s.city === city))
      .filter((s) => (roadType === "All" ? true : s.road_type === roadType))
      .filter((s) => (congestion === "All" ? true : s.congestionLevel === congestion));
  }, [enhancedSegments, city, roadType, congestion]);

  const filteredHotspots = useMemo(() => apiHotspots.filter((h) => (city === "All" ? true : h.city === city)), [apiHotspots, city]);
  const selected = useMemo(
    () => filteredSegments.find((segment) => segment.segment_id === selectedId) ?? enhancedSegments.find((segment) => segment.segment_id === selectedId) ?? null,
    [filteredSegments, enhancedSegments, selectedId],
  );
  const selectedSegmentId = selected?.segment_id ?? null;

  const visibleWeatherZones = useMemo(
    () => WEATHER_ZONES.filter((zone) => (city === "All" ? true : zone.city === city)),
    [city],
  );

  const alerts = useMemo<TrafficAlert[]>(() => {
    return filteredSegments
      .filter((segment) => segment.jamFactor >= 5.5 || segment.weatherRisk !== "Low")
      .sort((a, b) => b.jamFactor - a.jamFactor)
      .slice(0, 8)
      .map((segment, idx) => {
        const alertTypes: AlertType[] = ["Sudden Speed Drop", "Severe Congestion", "Rain Impact", "Travel Time Spike"];
        const type = segment.weatherRisk === "High" ? "Rain Impact" : segment.jamFactor >= 8 ? "Severe Congestion" : alertTypes[idx % alertTypes.length];
        return {
          id: `alert-${segment.segment_id}`,
          type,
          roadName: segment.name,
          city: segment.city,
          severity: segment.jamFactor >= 8 || segment.weatherRisk === "High" ? "High" : segment.jamFactor >= 6 ? "Medium" : "Low",
          possibleCause: segment.weatherRisk === "High" ? "Rain + peak hour" : segment.jamFactor >= 8 ? "Demand surge + incident risk" : "Travel time spike",
          timestamp: lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          coordinate: midpoint(segment),
          segmentId: segment.segment_id,
        };
      });
  }, [filteredSegments, lastUpdated]);

  const topCongested = useMemo(
    () => [...filteredSegments].sort((a, b) => b.jamFactor - a.jamFactor).slice(0, 5),
    [filteredSegments],
  );

  const sourceCounts = enhancedSegments.reduce<Record<string, number>>((counts, segment) => {
    const key = sourceLabel(segment.source);
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
  const primarySource = Object.entries(sourceCounts).sort((a, b) => b[1] - a[1])[0];
  const dataSourceLabel = segmentError || hotspotError
    ? "Unavailable"
    : primarySource
      ? `${primarySource[0]} (${primarySource[1]})`
      : "API / Local Gold Data";
  const segmentStatusMessage = segmentError
    ? "Segments API unavailable. No fallback data is shown."
    : !segmentsLoading && liveMapData && enhancedSegments.length === 0
      ? "No traffic segments returned for this city."
      : "";
  const hotspotStatusMessage = hotspotError
    ? "Hotspots API unavailable. No fallback hotspots are shown."
    : !hotspotsLoading && hotspotData && filteredHotspots.length === 0
      ? "No hotspots returned for this city."
      : "";

  const avgSpeed = filteredSegments.length
    ? filteredSegments.reduce((total, segment) => total + segment.currentSpeed, 0) / filteredSegments.length
    : 0;
  const congestedCount = filteredSegments.filter((segment) => segment.congestionLevel === "Congested" || segment.congestionLevel === "Severe").length;
  const highWeatherRisk = filteredSegments.filter((segment) => segment.weatherRisk === "High").length;
  const mediumWeatherRisk = filteredSegments.filter((segment) => segment.weatherRisk === "Medium").length;
  const weatherRisk = highWeatherRisk > 0 ? "High" : mediumWeatherRisk > 0 ? "Medium" : "Low";
  const center = CITY_CENTER[city];

  const handleViewportChange = useCallback((viewport: { bbox: string; zoom: number }) => {
    setBbox((current) => (current === viewport.bbox ? current : viewport.bbox));
    setZoom((current) => (current === viewport.zoom ? current : viewport.zoom));
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((key) => key + 1);
    reloadSegments();
    reloadHotspots();
    window.setTimeout(() => {
      setLastUpdated(new Date());
      setIsRefreshing(false);
    }, 1200);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard icon={Gauge} title="Average Speed" value={`${avgSpeed.toFixed(1)} km/h`} detail={avgSpeed < 25 ? "Below normal" : "Stable flow"} tone={avgSpeed < 25 ? "warning" : "success"} />
        <KpiCard icon={TrendingDown} title="Congested Segments" value={`${congestedCount} / ${filteredSegments.length}`} detail={`${topCongested[0]?.name ?? "No severe road"} leading`} tone={congestedCount > 0 ? "destructive" : "success"} />
        <KpiCard icon={ShieldAlert} title="Active Alerts" value={String(alerts.length)} detail={alerts.length ? "Map markers enabled" : "No active anomalies"} tone={alerts.length ? "destructive" : "success"} />
        <KpiCard icon={CloudRain} title="Weather Risk" value={weatherRisk} detail={`${visibleWeatherZones.length} weather zones`} tone={weatherRisk === "High" ? "destructive" : weatherRisk === "Medium" ? "warning" : "success"} />
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 rounded-3xl bg-card p-4 shadow-sm lg:col-span-8">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-semibold tracking-widest text-muted-foreground">CITY</span>
            {(["Hanoi", "HCMC", "All"] as City[]).map((c) => (
              <button
                key={c}
                onClick={() => setCity(c)}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  city === c ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                }`}
              >
                {c}
              </button>
            ))}
            <span className="ml-2 text-[10px] font-semibold tracking-widest text-muted-foreground">CONGESTION</span>
            {(["All", "Free", "Slow", "Congested", "Severe"] as Congestion[]).map((c) => (
              <button
                key={c}
                onClick={() => setCongestion(c)}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  congestion === c ? "bg-primary-soft text-accent-foreground" : "bg-secondary text-muted-foreground"
                }`}
              >
                {c}
              </button>
            ))}
            <span className="ml-2 text-[10px] font-semibold tracking-widest text-muted-foreground">ROAD</span>
            {(["All", "Highway", "Arterial", "Collector", "Local"] as RoadType[]).map((r) => (
              <button
                key={r}
                onClick={() => setRoadType(r)}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  roadType === r ? "bg-primary-soft text-accent-foreground" : "bg-secondary text-muted-foreground"
                }`}
              >
                {r}
              </button>
            ))}
            <span className="ml-2 text-[10px] font-semibold tracking-widest text-muted-foreground">COVERAGE</span>
            {(["Low", "Medium", "High"] as CoverageDensity[]).map((density) => (
              <button
                key={density}
                onClick={() => setCoverageDensity(density)}
                className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
                  coverageDensity === density ? "bg-primary-soft text-accent-foreground" : "bg-secondary text-muted-foreground"
                }`}
              >
                {density}
              </button>
            ))}
            <button
              onClick={() => setLayers((current) => ({ ...current, weather: !current.weather }))}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold ${
                layers.weather ? "bg-blue-100 text-blue-700" : "bg-secondary text-muted-foreground"
              }`}
            >
              <CloudRain className="h-3 w-3" /> Weather Overlay: {layers.weather ? "On" : "Off"}
            </button>
            <button
              onClick={handleRefresh}
              className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-[11px] font-semibold text-background"
              disabled={isRefreshing}
            >
              <RefreshCw className={`h-3 w-3 ${isRefreshing ? "animate-spin" : ""}`} /> {isRefreshing ? "Refreshing" : "Refresh"}
            </button>
          </div>

          <LayerControls layers={layers} setLayers={setLayers} />

          {(segmentStatusMessage || hotspotStatusMessage) && (
            <div className="mb-3 rounded-2xl border border-border bg-secondary px-3 py-2 text-xs font-medium text-muted-foreground">
              {[segmentStatusMessage, hotspotStatusMessage].filter(Boolean).join(" ")}
            </div>
          )}
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-secondary px-3 py-2 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{filteredSegments.length} displayed road segments</span>
            <span>Coverage mode: {coverageDensity}</span>
            <span>Zoom: {Math.round(zoom)}</span>
            <span>Road geometry: OSM/local Gold/curated</span>
            <span>Traffic source: {dataSourceLabel}</span>
            <span>Last updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          </div>

          <div className="relative h-[590px] overflow-hidden rounded-2xl">
            {mounted ? (
              <MapContainer center={[center.lat, center.lng]} zoom={center.zoom} scrollWheelZoom className="h-full w-full">
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <FlyTo city={city} />
                <FocusSelected segment={selected} />
                <ViewportTracker onViewportChange={handleViewportChange} />

                {layers.weather && visibleWeatherZones.map((zone) => (
                  <Circle
                    key={zone.id}
                    center={zone.center}
                    radius={zone.radius}
                    pathOptions={{
                      color: WEATHER_COLOR[zone.label],
                      fillColor: WEATHER_COLOR[zone.label],
                      fillOpacity: zone.risk === "High" ? 0.22 : 0.14,
                      weight: 1.5,
                    }}
                  >
                    <Popup>
                      <div className="text-xs">
                        <div className="font-semibold">{zone.label}</div>
                        <div>Risk: {zone.risk}</div>
                        <div>Source: OpenWeatherMap demo zone</div>
                      </div>
                    </Popup>
                  </Circle>
                ))}

                {layers.heatmap && filteredHotspots.map((h) => (
                  <Circle
                    key={`heat-${h.cluster_id}`}
                    center={[h.center_lat, h.center_lon]}
                    radius={Math.min(450 + h.segment_count * 120, 3200)}
                    pathOptions={{
                      color: "#ef4444",
                      fillColor: h.severity === "Critical" ? "#7f1d1d" : "#ef4444",
                      fillOpacity: 0.12,
                      weight: 0,
                    }}
                  />
                ))}

                {layers.roadSegments && filteredSegments.map((s) => {
                  const color = CONG_COLOR[s.congestionLevel];
                  const positions = s.geometry.coordinates.map(([lng, lat]) => [lat, lng]) as [number, number][];
                  const isSelected = selectedSegmentId === s.segment_id;
                  return (
                    <Fragment key={s.segment_id}>
                      <Polyline
                        positions={positions}
                        pathOptions={{ color, weight: 22, opacity: 0.001, interactive: true, bubblingMouseEvents: false }}
                        eventHandlers={{ click: () => setSelectedId(s.segment_id) }}
                      />
                      {isSelected && (
                        <Polyline
                          positions={positions}
                          pathOptions={{ color: "#111827", weight: 10, opacity: 0.38, interactive: false }}
                        />
                      )}
                      <Polyline
                        positions={positions}
                        pathOptions={{
                          color,
                          weight: isSelected ? 8 : zoom <= 12 ? (s.road_type === "Highway" ? 6.5 : 5.3) : zoom >= 15 ? (s.road_type === "Local" || s.road_type === "Collector" ? 3.2 : 4.2) : (s.road_type === "Highway" ? 5.5 : 4.7),
                          opacity: isSelected ? 1 : zoom >= 15 ? 0.76 : 0.84,
                        }}
                        eventHandlers={{ click: () => setSelectedId(s.segment_id) }}
                      />
                    </Fragment>
                  );
                })}

                {layers.alerts && alerts.map((alert) => (
                  <CircleMarker
                    key={alert.id}
                    center={alert.coordinate}
                    radius={7}
                    pathOptions={{
                      color: SEVERITY_COLOR[alert.severity],
                      fillColor: SEVERITY_COLOR[alert.severity],
                      fillOpacity: 0.95,
                      weight: 2,
                    }}
                    eventHandlers={{ click: () => alert.segmentId && setSelectedId(alert.segmentId) }}
                  >
                    <Popup>
                      <div className="space-y-1 text-xs">
                        <div className="font-semibold">Alert: {alert.type}</div>
                        <div>Road: {alert.roadName}</div>
                        <div>Severity: {alert.severity}</div>
                        <div>Possible cause: {alert.possibleCause}</div>
                        <div>Updated: {alert.timestamp}</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            ) : (
              <div className="flex h-full items-center justify-center bg-secondary text-xs text-muted-foreground">Loading map...</div>
            )}

            <MapLegend dataSourceLabel={dataSourceLabel} />
            {(segmentsLoading || hotspotsLoading || isRefreshing) && (
              <div className="absolute right-4 top-4 z-[1000] rounded-2xl bg-card/95 px-3 py-2 text-xs text-muted-foreground shadow backdrop-blur">
                Loading live map data...
              </div>
            )}
          </div>
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-5 shadow-sm lg:col-span-4">
          {selected ? (
            <SegmentDetail
              segment={selected}
              onClose={() => setSelectedId(null)}
              onViewForecast={onViewForecast}
              topCongested={topCongested}
              onSelectSegment={setSelectedId}
            />
          ) : (
            <EmptyPanel
              city={city}
              filteredSegments={filteredSegments.length}
              alerts={alerts.length}
              weatherAvailable={visibleWeatherZones.length > 0}
              dataSourceLabel={dataSourceLabel}
              coverageDensity={coverageDensity}
              topCongested={topCongested}
              onSelectSegment={setSelectedId}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  icon: Icon,
  title,
  value,
  detail,
  tone,
}: {
  icon: typeof Gauge;
  title: string;
  value: string;
  detail: string;
  tone: "success" | "warning" | "destructive";
}) {
  const toneClass = {
    success: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
    warning: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
    destructive: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  }[tone];
  return (
    <div className="rounded-2xl bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${toneClass}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">LIVE</span>
      </div>
      <div className="mt-3 text-[11px] font-medium text-muted-foreground">{title}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      <div className="mt-1 truncate text-[11px] text-muted-foreground">{detail}</div>
    </div>
  );
}

function LayerControls({
  layers,
  setLayers,
}: {
  layers: { roadSegments: boolean; heatmap: boolean; weather: boolean; alerts: boolean };
  setLayers: React.Dispatch<React.SetStateAction<{ roadSegments: boolean; heatmap: boolean; weather: boolean; alerts: boolean }>>;
}) {
  const items: Array<[keyof typeof layers, string]> = [
    ["roadSegments", "Road Segments"],
    ["heatmap", "Congestion Heatmap"],
    ["weather", "Weather Overlay"],
    ["alerts", "Alert Markers"],
  ];
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-border bg-background px-3 py-2">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-widest text-muted-foreground">
        <Layers className="h-3.5 w-3.5" /> LAYERS
      </div>
      {items.map(([key, label]) => (
        <button
          key={key}
          onClick={() => setLayers((current) => ({ ...current, [key]: !current[key] }))}
          className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors ${
            layers[key] ? "bg-primary-soft text-accent-foreground" : "bg-secondary text-muted-foreground"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function MapLegend({ dataSourceLabel }: { dataSourceLabel: string }) {
  const items = [
    ["Free", CONG_COLOR.Free],
    ["Slow", CONG_COLOR.Slow],
    ["Congested", CONG_COLOR.Congested],
    ["Severe", CONG_COLOR.Severe],
    ["Weather Impact", "#2563eb"],
  ] as const;
  return (
    <div className="absolute bottom-4 left-4 z-[1000] w-[min(92%,520px)] rounded-2xl bg-card/95 p-3 shadow-lg backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] font-semibold tracking-widest text-muted-foreground">TRAFFIC LEGEND</div>
        <div className="text-[10px] text-muted-foreground">Weather: <span className="font-semibold text-foreground">OpenWeatherMap</span></div>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs">
        {items.map(([label, color]) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="h-2.5 w-7 rounded-full" style={{ background: color, opacity: label === "Weather Impact" ? 0.45 : 1 }} />
            {label}
          </span>
        ))}
      </div>
      <div className="mt-2 grid gap-1 text-[11px] text-muted-foreground sm:grid-cols-2">
        <div>Traffic: <span className="font-semibold text-foreground">{dataSourceLabel}</span></div>
        <div>Alerts: speed drop, congestion, rain impact</div>
      </div>
    </div>
  );
}

function SegmentDetail({
  segment,
  onClose,
  onViewForecast,
  topCongested,
  onSelectSegment,
}: {
  segment: SegmentView;
  onClose: () => void;
  onViewForecast: (id: string) => void;
  topCongested: SegmentView[];
  onSelectSegment: (id: string) => void;
}) {
  const updated = new Date(segment.updatedAt);
  const insight = segment.weatherRisk === "High"
    ? "Traffic slowdown is likely affected by rain and peak-hour pressure."
    : segment.congestionLevel === "Severe"
      ? "Severe congestion suggests an incident risk or travel time spike."
      : segment.congestionLevel === "Slow"
        ? "Traffic is slower than normal but still moving through the corridor."
        : "Traffic is near free-flow conditions with low operational risk.";

  return (
    <div className="min-h-full">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-base font-semibold">
            <MapPin className="h-4 w-4 shrink-0 text-primary" />
            <span className="truncate">{segment.name}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <StatusBadge label={segment.congestionLevel} type="congestion" />
            <StatusBadge label={`Weather: ${segment.weatherCondition}`} type="weather" />
            <StatusBadge label={`Risk: ${segment.weatherRisk}`} type="risk" />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {segment.city} · {segment.road_type} · {segment.segment_id}
          </p>
        </div>
        <button onClick={onClose} className="rounded-full bg-secondary p-1.5 text-muted-foreground hover:text-foreground" aria-label="Close">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-4 rounded-2xl border border-border bg-secondary/40 p-3 text-xs font-medium leading-relaxed text-foreground">
        {insight}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <MetricTile icon={Gauge} label="Current speed" value={`${segment.currentSpeed.toFixed(1)} km/h`} />
        <MetricTile icon={Wind} label="Free-flow speed" value={`${segment.freeFlowSpeed.toFixed(1)} km/h`} />
        <MetricTile icon={BarChart3} label="Speed ratio" value={`${Math.round(segment.speedRatio * 100)}%`} />
        <MetricTile icon={Clock} label="Delay" value={`${segment.travelTimeDelayMin} min`} />
        <MetricTile icon={AlertTriangle} label="Jam factor" value={segment.jamFactor.toFixed(1)} />
        <MetricTile icon={ThermometerSun} label="Weather" value={segment.weatherCondition} />
      </div>

      <div className="mt-4 grid gap-3">
        <TrendCard title="Speed Trend" data={segment.speedTrend} dataKey="speed" color="#2563eb" unit="km/h" />
        <TrendCard title="Jam Factor Trend" data={segment.jamTrend} dataKey="jamFactor" color="#ef4444" unit="" />
      </div>

      <div className="mt-4 rounded-2xl border border-border p-3">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <CloudRain className="h-4 w-4 text-primary" /> Weather Context
        </div>
        <dl className="mt-3 space-y-1.5 text-xs">
          <InfoRow label="Condition" value={segment.weatherCondition} />
          <InfoRow label="Risk" value={segment.weatherRisk} />
          <InfoRow label="Temperature" value={`${segment.weather.temp}°C`} />
          <InfoRow label="Visibility" value={segment.weatherCondition === "Low Visibility" ? "3.5 km" : `${segment.weather.visibilityKm} km`} />
          <InfoRow label="Last update" value={Number.isNaN(updated.getTime()) ? "n/a" : updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })} />
        </dl>
      </div>

      <TopCongestedList segments={topCongested} onSelectSegment={onSelectSegment} />

      <button
        onClick={() => onViewForecast(segment.segment_id)}
        className="mt-4 w-full rounded-xl bg-foreground py-3 text-sm font-semibold text-background hover:opacity-90"
      >
        View Forecast
      </button>
    </div>
  );
}

function EmptyPanel({
  city,
  filteredSegments,
  alerts,
  weatherAvailable,
  dataSourceLabel,
  coverageDensity,
  topCongested,
  onSelectSegment,
}: {
  city: City;
  filteredSegments: number;
  alerts: number;
  weatherAvailable: boolean;
  dataSourceLabel: string;
  coverageDensity: CoverageDensity;
  topCongested: SegmentView[];
  onSelectSegment: (id: string) => void;
}) {
  return (
    <div className="flex min-h-full flex-col">
      <div className="rounded-2xl bg-secondary/60 p-5">
        <MapPin className="h-8 w-8 text-primary" />
        <div className="mt-3 text-sm font-semibold">Select a road segment</div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Inspect live speed, jam factor, weather context, alert status, and recent trends for each monitored corridor.
        </p>
      </div>
      <div className="mt-4 rounded-2xl border border-border p-4 text-xs">
        <div className="font-semibold text-foreground">Current View</div>
        <div className="mt-3 space-y-2 text-muted-foreground">
          <InfoRow label="City" value={city} />
          <InfoRow label="Displayed segments" value={String(filteredSegments)} />
          <InfoRow label="Coverage mode" value={coverageDensity} />
          <InfoRow label="Active alerts" value={String(alerts)} />
          <InfoRow label="Weather overlay" value={weatherAvailable ? "Available" : "Unavailable"} />
          <InfoRow label="Road geometry" value="OSM/local Gold/curated" />
          <InfoRow label="Traffic source" value={dataSourceLabel} />
        </div>
      </div>
      <div className="mt-4 rounded-2xl bg-primary-soft p-4 text-xs text-accent-foreground">
        Available actions: toggle overlays, filter congestion, click alert markers, or open forecast from a selected segment.
      </div>
      <TopCongestedList segments={topCongested} onSelectSegment={onSelectSegment} />
    </div>
  );
}

function MetricTile({ icon: Icon, label, value }: { icon: typeof Gauge; label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-secondary p-3">
      <Icon className="h-4 w-4 text-primary" />
      <div className="mt-2 truncate text-lg font-semibold">{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function TrendCard({
  title,
  data,
  dataKey,
  color,
  unit,
}: {
  title: string;
  data: Array<Record<string, string | number>>;
  dataKey: string;
  color: string;
  unit: string;
}) {
  return (
    <div className="rounded-2xl border border-border p-3">
      <div className="text-xs font-semibold">{title}</div>
      <div className="mt-2 h-28">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="time" hide />
            <YAxis hide domain={["dataMin - 2", "dataMax + 2"]} />
            <Tooltip
              formatter={(value) => [`${value}${unit ? ` ${unit}` : ""}`, title]}
              contentStyle={{ borderRadius: 12, border: "1px solid oklch(0.92 0.01 280)", fontSize: 12 }}
            />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function TopCongestedList({ segments, onSelectSegment }: { segments: SegmentView[]; onSelectSegment: (id: string) => void }) {
  return (
    <div className="mt-4 rounded-2xl border border-border p-3">
      <div className="text-xs font-semibold">Top Congested Segments</div>
      <div className="mt-3 space-y-2">
        {segments.length === 0 ? (
          <div className="text-xs text-muted-foreground">No congested segments in the current view.</div>
        ) : (
          segments.map((segment, idx) => (
            <button
              key={segment.segment_id}
              onClick={() => onSelectSegment(segment.segment_id)}
              className="flex w-full items-center justify-between gap-3 rounded-xl bg-secondary/70 px-3 py-2 text-left hover:bg-secondary"
            >
              <span className="min-w-0 truncate text-xs font-medium">
                {idx + 1}. {segment.name}
              </span>
              <span className="shrink-0 rounded-full bg-background px-2 py-0.5 text-[11px] font-semibold text-destructive">
                Jam {segment.jamFactor.toFixed(1)}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function StatusBadge({ label, type }: { label: string; type: "congestion" | "weather" | "risk" }) {
  let className = "bg-secondary text-muted-foreground";
  if (type === "congestion") {
    if (label === "Free") className = "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]";
    if (label === "Slow") className = "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]";
    if (label === "Congested" || label === "Severe") className = "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]";
  }
  if (type === "weather" && label.includes("Rain")) className = "bg-blue-100 text-blue-700";
  if (type === "risk") {
    if (label.includes("High")) className = "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]";
    if (label.includes("Medium")) className = "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]";
    if (label.includes("Low")) className = "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]";
  }
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${className}`}>{label}</span>;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-semibold text-foreground">{value}</span>
    </div>
  );
}
