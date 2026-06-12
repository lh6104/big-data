import { Fragment, useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Wind, Gauge, Clock, RefreshCw, AlertOctagon, CloudRain, X } from "lucide-react";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

type City = "Hanoi" | "HCMC";
type Congestion = "All" | "Free" | "Slow" | "Congested";
type RoadType = "All" | "Highway" | "Arterial" | "Local";

type Segment = {
  segment_id: string;
  name: string;
  road_type: Exclude<RoadType, "All">;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  currentSpeed: number;
  freeFlowSpeed: number;
  jamFactor: number;
  confidence: number;
  city: City;
  weather: { condition: string; temp: number; visibilityKm: number };
  updatedAt: string;
  incident?: string;
  source?: string;
  provider?: string;
  coverageSource?: string;
  isDemoCoverage?: boolean;
};

type Hotspot = {
  cluster_id: string;
  label: string;
  center_lat: number;
  center_lon: number;
  severity: "Critical" | "High" | "Medium" | "Low";
  segment_count: number;
  avg_speed: number;
  city: City;
};

type SegmentFeatureCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "LineString"; coordinates: [number, number][] };
    properties: {
      segment_id: string;
      segment_name?: string;
      jam_factor: number;
      current_speed: number;
      free_flow_speed: number;
      city: "hanoi" | "hcmc";
      coverage_source?: "local_gold" | "demo_coverage_interpolated";
      is_demo_coverage?: boolean;
      source?: string;
      provider?: string;
      latest_timestamp?: string;
      confidence?: number;
    };
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
  Hanoi: { lat: 21.0285, lng: 105.8542, zoom: 13 },
  HCMC: { lat: 10.7769, lng: 106.7009, zoom: 13 },
};

function congestionOf(s: Segment): Exclude<Congestion, "All"> {
  if (s.jamFactor >= 6) return "Congested";
  if (s.jamFactor >= 3) return "Slow";
  return "Free";
}

const CONG_COLOR: Record<Exclude<Congestion, "All">, string> = {
  Free: "#22c55e",
  Slow: "#f97316",
  Congested: "#ef4444",
};

const SEVERITY_COLOR: Record<Hotspot["severity"], string> = {
  Critical: "#ef4444",
  High: "#f97316",
  Medium: "#eab308",
  Low: "#22c55e",
};

function severityLabel(severity: ApiHotspot["severity"]): Hotspot["severity"] {
  if (severity === "critical") return "Critical";
  if (severity === "high") return "High";
  if (severity === "medium") return "Medium";
  return "Low";
}

function FlyTo({ city }: { city: City }) {
  const map = useMap();
  useEffect(() => {
    const c = CITY_CENTER[city];
    map.flyTo([c.lat, c.lng], c.zoom, { duration: 0.8 });
  }, [city, map]);
  return null;
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
    setInternalCity(next);
    onCityChange?.(next);
  };
  const [congestion, setCongestion] = useState<Congestion>("All");
  const [roadType, setRoadType] = useState<RoadType>("All");
  const [selected, setSelected] = useState<Segment | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [mounted, setMounted] = useState(false);
  const apiCity = city === "Hanoi" ? "hanoi" : "hcmc";
  const { data: segmentGeojson, error: segmentError, isLoading: segmentsLoading, mutate: reloadSegments } =
    useSWR<SegmentFeatureCollection>(`/segments/geojson?city=${apiCity}&include_demo_coverage=true&refresh=${refreshKey}`, apiGet, {
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
    if (segmentError) {
      console.error("Live Map segments API unavailable", segmentError);
    }
  }, [segmentError]);

  useEffect(() => {
    if (hotspotError) {
      console.error("Live Map hotspots API unavailable", hotspotError);
    }
  }, [hotspotError]);

  const apiSegments = useMemo<Segment[]>(() => {
    if (!segmentGeojson?.features?.length) return [];
    return segmentGeojson.features.map((feature) => ({
      segment_id: feature.properties.segment_id,
      name: feature.properties.segment_name ?? feature.properties.segment_id,
      road_type: "Arterial",
      geometry: feature.geometry,
      currentSpeed: feature.properties.current_speed,
      freeFlowSpeed: feature.properties.free_flow_speed,
      jamFactor: feature.properties.jam_factor,
      confidence: feature.properties.confidence ?? 1,
      city,
      weather: { condition: "Local data", temp: 0, visibilityKm: 0 },
      updatedAt: feature.properties.latest_timestamp ?? new Date().toISOString(),
      source: feature.properties.source,
      provider: feature.properties.provider,
      coverageSource: feature.properties.coverage_source,
      isDemoCoverage: feature.properties.is_demo_coverage,
    }));
  }, [segmentGeojson, city]);

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

  const segmentStatusMessage = segmentError
    ? "Segments API unavailable. No fallback data is shown."
    : !segmentsLoading && segmentGeojson && apiSegments.length === 0
      ? "No traffic segments returned for this city."
      : "";
  const hotspotStatusMessage = hotspotError
    ? "Hotspots API unavailable. No fallback hotspots are shown."
    : !hotspotsLoading && hotspotData && apiHotspots.length === 0
      ? "No hotspots returned for this city."
      : "";
  const localTomTomCount = apiSegments.filter((segment) => !segment.isDemoCoverage && segment.source === "tomtom").length;
  const dataSourceLabel = segmentError || hotspotError
    ? "Unavailable"
    : localTomTomCount > 0
      ? `TomTom realtime (${localTomTomCount})`
      : "API";
  const demoCoverageCount = apiSegments.filter((segment) => segment.segment_id.includes("_DEMO_")).length;

  const filteredSegments = useMemo(() => {
    return apiSegments.filter((s) => s.city === city)
      .filter((s) => (roadType === "All" ? true : s.road_type === roadType))
      .filter((s) => (congestion === "All" ? true : congestionOf(s) === congestion));
  }, [apiSegments, city, roadType, congestion]);

  const filteredHotspots = useMemo(() => {
    return apiHotspots.filter((h) => h.city === city);
  }, [apiHotspots, city]);

  const center = CITY_CENTER[city];

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-12 lg:col-span-8 rounded-3xl bg-card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold tracking-widest text-muted-foreground">CITY</span>
          {(["Hanoi", "HCMC"] as City[]).map((c) => (
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
          {(["All", "Free", "Slow", "Congested"] as Congestion[]).map((c) => (
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
          {(["All", "Highway", "Arterial", "Local"] as RoadType[]).map((r) => (
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
          <button
            onClick={() => {
              setRefreshKey((k) => k + 1);
              reloadSegments();
              reloadHotspots();
            }}
            className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-foreground px-3 py-1.5 text-[11px] font-semibold text-background"
          >
            <RefreshCw className="h-3 w-3" /> Refresh
          </button>
        </div>

        {(segmentStatusMessage || hotspotStatusMessage) && (
          <div className="mb-3 rounded-2xl border border-border bg-secondary px-3 py-2 text-xs font-medium text-muted-foreground">
            {[segmentStatusMessage, hotspotStatusMessage].filter(Boolean).join(" ")}
          </div>
        )}
        {!segmentError && demoCoverageCount > 0 && (
          <div className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-secondary px-3 py-2 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{filteredSegments.length} displayed segments</span>
            <span>{demoCoverageCount} interpolated demo coverage lines</span>
            <span>Solid lines are TomTom/local Gold data; faint lines are coverage overlay.</span>
          </div>
        )}

        <div className="relative h-[560px] overflow-hidden rounded-2xl">
          {mounted ? (
            <MapContainer
              center={[center.lat, center.lng]}
              zoom={center.zoom}
              scrollWheelZoom
              className="h-full w-full"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FlyTo city={city} />
              {filteredSegments.map((s) => {
                const color = CONG_COLOR[congestionOf(s)];
                const positions = s.geometry.coordinates.map(([lng, lat]) => [lat, lng]) as [number, number][];
                const isSelected = selected?.segment_id === s.segment_id;
                return (
                  <Fragment key={s.segment_id}>
                    <Polyline
                      positions={positions}
                      pathOptions={{ color, weight: 22, opacity: 0.001, interactive: true, bubblingMouseEvents: false }}
                      eventHandlers={{ click: () => setSelected(s) }}
                    />
                    <Polyline
                      positions={positions}
                      pathOptions={{
                        color,
                        weight: isSelected ? 7 : s.segment_id.includes("_DEMO_") ? 2 : 4,
                        opacity: s.segment_id.includes("_DEMO_") ? 0.45 : 0.9,
                        dashArray: s.segment_id.includes("_DEMO_") ? "6 6" : undefined,
                      }}
                      eventHandlers={{ click: () => setSelected(s) }}
                    />
                  </Fragment>
                );
              })}
              {filteredHotspots.map((h) => (
                <CircleMarker
                  key={h.cluster_id}
                  center={[h.center_lat, h.center_lon]}
                  radius={Math.min(8 + h.segment_count * 2, 40)}
                  pathOptions={{
                    color: SEVERITY_COLOR[h.severity],
                    fillColor: SEVERITY_COLOR[h.severity],
                    fillOpacity: 0.25,
                    weight: 1.5,
                  }}
                >
                  <Popup>
                    <div className="text-xs">
                      <div className="font-semibold">{h.label}</div>
                      <div>Severity: {h.severity}</div>
                      <div>{h.segment_count} segments · avg {h.avg_speed} km/h</div>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          ) : (
            <div className="flex h-full items-center justify-center bg-secondary text-xs text-muted-foreground">
              Loading map…
            </div>
          )}

          <div className="absolute bottom-4 left-4 z-[1000] rounded-2xl bg-card/95 p-3 shadow backdrop-blur">
            <div className="text-[10px] font-semibold tracking-widest text-muted-foreground">LEGEND</div>
            <div className="mt-2 flex gap-3 text-xs">
              <span className="flex items-center gap-1.5"><span className="h-2 w-6 rounded-full" style={{ background: CONG_COLOR.Free }} /> Free</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-6 rounded-full" style={{ background: CONG_COLOR.Slow }} /> Slow</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-6 rounded-full" style={{ background: CONG_COLOR.Congested }} /> Congested</span>
            </div>
            <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
              Data source: <span className="font-semibold text-foreground">{dataSourceLabel}</span>
            </div>
          </div>
          {(segmentsLoading || hotspotsLoading) && (
            <div className="absolute right-4 top-4 z-[1000] rounded-2xl bg-card/95 px-3 py-2 text-xs text-muted-foreground shadow backdrop-blur">
              Loading live map data...
            </div>
          )}
        </div>
      </div>

      <div className="col-span-12 lg:col-span-4 rounded-3xl bg-card p-6">
        {selected ? (
          <SegmentDetail segment={selected} onClose={() => setSelected(null)} onViewForecast={onViewForecast} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <MapPin className="h-8 w-8 text-primary" />
            <div className="mt-3 text-sm font-semibold">Select a segment</div>
            <p className="mt-1 text-xs text-muted-foreground">
              Click any colored road on the map to inspect real-time speed, jam factor, and weather context.
            </p>
            <div className="mt-6 w-full rounded-2xl bg-secondary p-4 text-left text-[11px] text-muted-foreground">
              <div className="font-semibold text-foreground">Showing</div>
              <div>{filteredSegments.length} segments · {filteredHotspots.length} hotspots</div>
              <div className="mt-1">City: {city} · Road: {roadType} · Congestion: {congestion}</div>
              <div className="mt-1">Data source: {dataSourceLabel}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SegmentDetail({
  segment,
  onClose,
  onViewForecast,
}: {
  segment: Segment;
  onClose: () => void;
  onViewForecast: (id: string) => void;
}) {
  const updated = new Date(segment.updatedAt);
  const status = congestionOf(segment);
  const statusStyles: Record<typeof status, string> = {
    Free: "bg-green-100 text-green-700",
    Slow: "bg-orange-100 text-orange-700",
    Congested: "bg-red-100 text-red-700",
  };

  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-base font-semibold">
            <MapPin className="h-4 w-4 text-primary" />
            {segment.name}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusStyles[status]}`}>
              {status}
            </span>
            <span className="text-[11px] text-muted-foreground">{segment.road_type}</span>
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">
            {segment.segment_id} · {segment.isDemoCoverage ? "Demo overlay" : segment.provider ?? segment.source ?? "local data"}
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded-full bg-secondary p-1.5 text-muted-foreground hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        {[
          { i: Gauge, l: "Current speed", v: `${segment.currentSpeed} km/h` },
          { i: Wind, l: "Free-flow speed", v: `${segment.freeFlowSpeed} km/h` },
          { i: Clock, l: "Jam factor", v: segment.jamFactor.toFixed(1) },
          { i: Gauge, l: "Confidence", v: segment.confidence.toFixed(2) },
        ].map((m, i) => (
          <div key={i} className="rounded-2xl bg-secondary p-3">
            <m.i className="h-4 w-4 text-primary" />
            <div className="mt-2 text-lg font-semibold">{m.v}</div>
            <div className="text-[11px] text-muted-foreground">{m.l}</div>
          </div>
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-border p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <CloudRain className="h-4 w-4 text-primary" /> Weather context
        </div>
        <dl className="mt-3 space-y-1.5 text-xs">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Conditions</dt>
            <dd className="font-medium">{segment.weather.condition}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Temperature</dt>
            <dd className="font-medium">{segment.weather.temp}°C</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Visibility</dt>
            <dd className="font-medium">{segment.weather.visibilityKm} km</dd>
          </div>
        </dl>
      </div>

      {segment.incident && (
        <div className="mt-3 flex items-start gap-2 rounded-2xl border border-red-100 bg-red-50 p-3 text-red-700">
          <AlertOctagon className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="text-[11px] font-semibold leading-snug">{segment.incident}</div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>Last update</span>
        <span className="font-semibold text-foreground">
          {Number.isNaN(updated.getTime()) ? "n/a" : updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </span>
      </div>

      <button
        onClick={() => onViewForecast(segment.segment_id)}
        className="mt-5 w-full rounded-xl bg-foreground py-3 text-sm font-semibold text-background hover:opacity-90"
      >
        View Forecast →
      </button>
    </div>
  );
}
