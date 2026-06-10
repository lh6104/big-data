import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { Flame, MapPin, TrendingUp, TrendingDown, Minus, Layers } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";
import useSWR from "swr";
import { apiGet } from "@/lib/api/client";

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc"]), "hanoi").default("hanoi"),
  severity: fallback(z.enum(["all", "critical", "high", "medium"]), "all").default("all"),
});

type SeverityFilter = "all" | "critical" | "high" | "medium";

export const Route = createFileRoute("/_app/hotspots")({
  validateSearch: zodValidator(searchSchema),
  component: HotspotsPage,
});

type Severity = "Critical" | "High" | "Medium";

type Hotspot = {
  id: string;
  name: string;
  area: string;
  severity: Severity;
  segments: number;
  avgSpeed: number;
  jam: number;
  started: string;
  trend: "up" | "down" | "flat";
  baseline: string;
  lat: number;
  lon: number;
};

type ApiHotspot = {
  hotspot_id: string;
  cluster_id: number;
  city: CityKey;
  center_lat: number;
  center_lon: number;
  radius_km: number;
  num_segments: number;
  avg_congestion: number;
  avg_jam_factor: number;
  severity: "critical" | "high" | "medium" | "low";
  detected_at: string;
};

const toHotspot = (h: ApiHotspot): Hotspot & { city: CityKey } => ({
  id: h.hotspot_id,
  name: `Cluster ${h.cluster_id}`,
  area: h.city === "hanoi" ? "Hanoi" : "Ho Chi Minh City",
  severity: (h.severity.charAt(0).toUpperCase() + h.severity.slice(1)) as Severity,
  segments: h.num_segments,
  avgSpeed: Math.max(0, Math.round(50 - h.avg_congestion)),
  jam: h.avg_jam_factor,
  started: new Date(h.detected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  trend: h.avg_jam_factor >= 6 ? "up" : "flat",
  baseline: `+ ${Math.round(h.avg_jam_factor * 10)}%`,
  lat: h.center_lat,
  lon: h.center_lon,
  city: h.city,
});

const CITY_CENTER: Record<CityKey, { lat: number; lon: number; zoom: number }> = {
  hanoi: { lat: 21.0285, lon: 105.8542, zoom: 12 },
  hcmc: { lat: 10.7769, lon: 106.7009, zoom: 12 },
};

const SEVERITY_COLOR: Record<Severity, string> = {
  Critical: "#ef4444",
  High: "#f97316",
  Medium: "#eab308",
};

const sevTone: Record<string, string> = {
  Critical: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  High: "bg-primary-soft text-accent-foreground",
  Medium: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
  Low: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
};

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "up") return <TrendingUp className="h-3.5 w-3.5 text-destructive" />;
  if (trend === "down") return <TrendingDown className="h-3.5 w-3.5 text-success" />;
  return <Minus className="h-3.5 w-3.5 text-muted-foreground" />;
}

function PanTo({ target }: { target: { lat: number; lon: number; id: string } | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 13), { duration: 0.7 });
  }, [target, map]);
  return null;
}

function HotspotsPage() {
  const { city, severity } = Route.useSearch() as { city: CityKey; severity: SeverityFilter };
  const navigate = useNavigate({ from: "/hotspots" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [panTarget, setPanTarget] = useState<{ lat: number; lon: number; id: string } | null>(null);
  const [mounted, setMounted] = useState(false);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const severityParam = severity === "all" ? "" : `&severity=${severity}`;
  const { data, error, isLoading } = useSWR<ApiHotspot[]>(`/hotspots?city=${city}${severityParam}`, apiGet, {
    refreshInterval: 60_000,
  });

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    setSelectedCity(city);
  }, [city, setSelectedCity]);

  useEffect(() => {
    setSelectedSegment(selectedId);
  }, [selectedId, setSelectedSegment]);

  const visibleHotspots = useMemo(() => (data ?? []).map(toHotspot), [data]);

  const handleMapClick = (h: Hotspot) => {
    setSelectedId(h.id);
    const el = cardRefs.current[h.id];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const handleCardClick = (h: Hotspot) => {
    setSelectedId(h.id);
    setPanTarget({ lat: h.lat, lon: h.lon, id: h.id + ":" + Date.now() });
  };

  const setCity = (next: CityKey) => navigate({ search: { city: next, severity } });
  const setSeverity = (next: SeverityFilter) => navigate({ search: { city, severity: next } });

  const center = CITY_CENTER[city];

  return (
    <PlaceholderPage title="Hotspots" subtitle="Detected congestion clusters and abnormal traffic regions">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { l: "Active hotspots", v: "12", d: "+ 3 in last hour" },
            { l: "Critical clusters", v: "2", d: "Both rising" },
            { l: "Affected segments", v: "44", d: "vs baseline 18" },
            { l: "Avg cluster speed", v: "19 km/h", d: "− 9 km/h" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl bg-card p-5">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Flame className="h-3.5 w-3.5" /> {s.l}
              </div>
              <div className="mt-3 text-2xl font-semibold">{s.v}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">{s.d}</div>
            </div>
          ))}
        </div>

        <div className="col-span-12 lg:col-span-7 rounded-3xl bg-card p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-base font-semibold">Hotspot Map</h3>
              <p className="text-xs text-muted-foreground">Spatial distribution of active congestion clusters</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(["hanoi", "hcmc"] as CityKey[]).map((c) => (
                <button
                  key={c}
                  onClick={() => setCity(c)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${city === c ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}
                >
                  {c === "hanoi" ? "Hanoi" : "HCMC"}
                </button>
              ))}
              <span className="mx-1 self-center text-muted-foreground">·</span>
              {(["all", "critical", "high", "medium"] as SeverityFilter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setSeverity(f)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-semibold capitalize ${severity === f ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="relative h-[420px] overflow-hidden rounded-2xl">
            {mounted ? (
              <MapContainer key={city} center={[center.lat, center.lon]} zoom={center.zoom} scrollWheelZoom className="h-full w-full">
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <PanTo target={panTarget} />
                {visibleHotspots.map((h) => {
                  const color = SEVERITY_COLOR[h.severity];
                  const isSelected = selectedId === h.id;
                  return (
                    <CircleMarker
                      key={h.id}
                      center={[h.lat, h.lon]}
                      radius={Math.sqrt(h.segments) * 8}
                      pathOptions={{
                        color,
                        fillColor: color,
                        fillOpacity: 0.25,
                        weight: isSelected ? 3 : 1.5,
                      }}
                      eventHandlers={{ click: () => handleMapClick(h) }}
                    >
                      <Tooltip permanent direction="center" className="hotspot-label">
                        {h.id}
                      </Tooltip>
                    </CircleMarker>
                  );
                })}
              </MapContainer>
            ) : (
              <div className="flex h-full items-center justify-center bg-secondary text-xs text-muted-foreground">
                Loading map…
              </div>
            )}
            {(isLoading || error || visibleHotspots.length === 0) && (
              <div className="absolute right-3 top-3 z-[1000] rounded-2xl bg-card/95 px-3 py-2 text-xs text-muted-foreground backdrop-blur">
                {error ? error.message : isLoading ? "Loading hotspots..." : "No hotspots for this filter"}
              </div>
            )}

            <div className="absolute bottom-3 left-3 z-[1000] rounded-2xl bg-card/95 p-3 backdrop-blur">
              <div className="text-[10px] font-semibold tracking-widest text-muted-foreground">CLUSTER SEVERITY</div>
              <div className="mt-2 flex gap-3 text-xs">
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: SEVERITY_COLOR.Critical }} /> Critical</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: SEVERITY_COLOR.High }} /> High</span>
                <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: SEVERITY_COLOR.Medium }} /> Medium</span>
              </div>
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-5 rounded-3xl bg-card p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-base font-semibold">Active Clusters</h3>
            <button className="flex h-7 items-center gap-1.5 rounded-full border border-border px-3 text-[11px] text-muted-foreground"><Layers className="h-3 w-3" /> Group view</button>
          </div>
          <div className="flex max-h-[420px] flex-col gap-3 overflow-y-auto pr-1">
            {visibleHotspots.map((h) => {
              const isSelected = selectedId === h.id;
              return (
                <div
                  key={h.id}
                  ref={(el) => { cardRefs.current[h.id] = el; }}
                  onClick={() => handleCardClick(h)}
                  className={`cursor-pointer rounded-2xl border p-4 transition-colors ${isSelected ? "border-primary bg-primary-soft/40" : "border-border hover:bg-secondary/40"}`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold">{h.id} · {h.name}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${sevTone[h.severity]}`}>{h.severity}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground"><MapPin className="h-3 w-3" /> {h.area}</div>
                    </div>
                    <div className="flex items-center gap-1 text-[11px]">
                      <TrendIcon trend={h.trend} />
                      <span className="font-semibold">{h.baseline}</span>
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-4 gap-2 text-[11px]">
                    <div><div className="text-muted-foreground">Segments</div><div className="font-semibold">{h.segments}</div></div>
                    <div><div className="text-muted-foreground">Avg speed</div><div className="font-semibold">{h.avgSpeed} km/h</div></div>
                    <div><div className="text-muted-foreground">Jam</div><div className="font-semibold">{h.jam}</div></div>
                    <div><div className="text-muted-foreground">Since</div><div className="font-semibold">{h.started}</div></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}
