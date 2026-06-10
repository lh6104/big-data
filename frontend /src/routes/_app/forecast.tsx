import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect } from "react";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";

const CITIES: { key: CityKey; label: string }[] = [
  { key: "hanoi", label: "Hanoi" },
  { key: "hcmc", label: "HCMC" },
];

const SEGMENTS: Record<CityKey, { slug: string; label: string }[]> = {
  hanoi: [
    { slug: "SEG-HN-RR3-08493", label: "Ring Road 3 — Thanh Xuan" },
    { slug: "SEG-HN-NTR-00112", label: "Nguyen Trai" },
    { slug: "SEG-HN-CG-00871", label: "Cau Giay" },
    { slug: "SEG-HN-HK-00220", label: "Hoan Kiem Loop" },
    { slug: "SEG-HN-TL-09931", label: "Truong Chinh" },
  ],
  hcmc: [
    { slug: "SEG-HCM-DBP-00045", label: "Dien Bien Phu" },
    { slug: "SEG-HCM-NVL-01122", label: "Nguyen Van Linh" },
  ],
};

const ALL_SEGMENT_LABELS: Record<string, string> = {
  ...Object.fromEntries(
    Object.values(SEGMENTS).flat().map((s) => [s.slug, s.label])
  ),
};

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc"]), "hanoi").default("hanoi"),
  segment: fallback(z.string(), "").default(""),
});

export const Route = createFileRoute("/_app/forecast")({
  validateSearch: zodValidator(searchSchema),
  component: ForecastPage,
});


function ForecastPage() {
  const search = Route.useSearch() as { city: CityKey; segment: string };
  const { city, segment } = search;
  const navigate = useNavigate({ from: "/forecast" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);
  const setSelectedSegment = useAppStore((s) => s.setSelectedSegment);

  useEffect(() => {
    setSelectedCity(city);
    setSelectedSegment(segment || null);
  }, [city, segment, setSelectedCity, setSelectedSegment]);

  const segments = SEGMENTS[city];
  const segmentLabel = segment ? ALL_SEGMENT_LABELS[segment] ?? segment : null;

  // Segment-specific deterministic forecast: now + 3 prediction horizons
  const seed = (segment || city).split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const nowSpeed = 32 + (seed % 9);
  const data = [
    { t: "Now", current: nowSpeed, predicted: nowSpeed },
    { t: "+15 min", current: null, predicted: nowSpeed - 4 + (seed % 3) },
    { t: "+60 min", current: null, predicted: nowSpeed - 11 + (seed % 4) },
    { t: "+240 min", current: null, predicted: nowSpeed + 8 - (seed % 5) },
  ];

  const selectCity = (next: CityKey) => {
    navigate({ search: { city: next, segment: "" } });
  };
  const selectSegment = (slug: string) => {
    navigate({ search: { city, segment: slug } });
  };

  const title = segmentLabel ? `Forecast · ${segmentLabel}` : "Forecast";
  const subtitle = segmentLabel
    ? `${segment} · AI-predicted speed for the next 4 hours`
    : "AI-predicted traffic conditions for the next horizon";

  return (
    <PlaceholderPage title={title} subtitle={subtitle}>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-wrap gap-2">
          {CITIES.map((c) => (
            <button
              key={c.key}
              onClick={() => selectCity(c.key)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${c.key === city ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {c.label}
            </button>
          ))}
          <span className="mx-1 self-center text-xs text-muted-foreground">/</span>
          {segments.map((s) => (
            <button
              key={s.slug}
              onClick={() => selectSegment(s.slug)}
              className={`rounded-full px-4 py-2 text-xs font-semibold ${s.slug === segment ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"}`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="col-span-12 grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            { h: "+15 min", v: "29 km/h", d: "− 4 km/h", c: "0.94" },
            { h: "+60 min", v: "22 km/h", d: "− 11 km/h", c: "0.89" },
            { h: "+240 min", v: "41 km/h", d: "+ 8 km/h", c: "0.78" },
          ].map((c) => (
            <div key={c.h} className="rounded-3xl bg-card p-6">
              <div className="text-xs font-semibold tracking-widest text-muted-foreground">{c.h.toUpperCase()}</div>
              <div className="mt-3 flex items-baseline gap-2">
                <div className="text-3xl font-semibold">{c.v}</div>
                <div className="text-sm text-muted-foreground">{c.d}</div>
              </div>
              <div className="mt-4 flex items-center justify-between rounded-xl bg-secondary px-3 py-2 text-xs">
                <span className="text-muted-foreground">Confidence</span>
                <span className="font-semibold">{c.c}</span>
              </div>
              <div className="mt-2 text-[11px] text-muted-foreground">Model v2024.11 · GBM-traffic</div>
            </div>
          ))}
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6">
          <h3 className="text-base font-semibold">
            Current vs Predicted Speed
            {segmentLabel && <span className="ml-2 text-xs font-normal text-muted-foreground">· {segmentLabel}</span>}
          </h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid stroke="oklch(0.92 0.01 280)" vertical={false} />
                <XAxis dataKey="t" stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="oklch(0.5 0.02 270)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "white", border: "1px solid oklch(0.92 0.01 280)", borderRadius: 12, fontSize: 12 }} />
                <Line type="linear" dataKey="current" stroke="oklch(0.5 0.02 270)" strokeWidth={2} dot={{ r: 5, fill: "oklch(0.5 0.02 270)" }} />
                <Line type="linear" dataKey="predicted" stroke="oklch(0.58 0.21 285)" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 6, fill: "oklch(0.58 0.21 285)", stroke: "white", strokeWidth: 2 }} activeDot={{ r: 8 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}
