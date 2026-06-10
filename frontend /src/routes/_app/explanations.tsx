import { createFileRoute } from "@tanstack/react-router";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { Brain, CloudRain, Clock, Activity, MapPin, History, Route as RouteIcon } from "lucide-react";

export const Route = createFileRoute("/_app/explanations")({
  component: ExplanationsPage,
});

const factors = [
  { icon: Activity, label: "Current speed very low (12 km/h)", impact: 0.32, dir: "up" },
  { icon: Clock, label: "Peak hour (17:00 - 19:00)", impact: 0.24, dir: "up" },
  { icon: CloudRain, label: "Heavy rain · visibility 1.8km", impact: 0.18, dir: "up" },
  { icon: History, label: "Historical baseline same hour", impact: 0.11, dir: "up" },
  { icon: RouteIcon, label: "Adjacent hotspot HS-02 (1.2km)", impact: 0.09, dir: "up" },
  { icon: MapPin, label: "Road class: arterial junction", impact: 0.06, dir: "down" },
];

function ExplanationsPage() {
  return (
    <PlaceholderPage title="Explanations" subtitle="Why the model predicted this congestion — feature attribution & SHAP">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="rounded-3xl bg-card p-6">
            <div className="text-[11px] font-semibold tracking-widest text-muted-foreground">SELECTED PREDICTION</div>
            <div className="mt-3 flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Brain className="h-5 w-5" /></div>
              <div>
                <div className="text-sm font-semibold">ALR-2481 · Cau Giay</div>
                <div className="text-[11px] text-muted-foreground">Predicted speed 14 km/h · +60m horizon · conf 0.91</div>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-xl bg-secondary p-3"><div className="text-muted-foreground">Predicted</div><div className="mt-1 text-base font-semibold">14 km/h</div></div>
              <div className="rounded-xl bg-secondary p-3"><div className="text-muted-foreground">Actual now</div><div className="mt-1 text-base font-semibold">12 km/h</div></div>
              <div className="rounded-xl bg-secondary p-3"><div className="text-muted-foreground">Jam factor</div><div className="mt-1 text-base font-semibold">9.1</div></div>
              <div className="rounded-xl bg-secondary p-3"><div className="text-muted-foreground">Confidence</div><div className="mt-1 text-base font-semibold">0.91</div></div>
            </div>
          </div>

          <div className="rounded-3xl bg-card p-6">
            <div className="text-sm font-semibold">Recent predictions</div>
            <div className="mt-3 flex flex-col gap-2">
              {[
                { id: "ALR-2481", loc: "Cau Giay", sel: true },
                { id: "ALR-2479", loc: "District 1, HCMC", sel: false },
                { id: "ALR-2476", loc: "Nguyen Trai", sel: false },
                { id: "FCS-1180", loc: "Pham Hung +240m", sel: false },
              ].map((p) => (
                <button key={p.id} className={`flex items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs ${p.sel ? "bg-primary-soft text-accent-foreground" : "bg-secondary"}`}>
                  <span><span className="font-mono">{p.id}</span> · {p.loc}</span>
                  <span>›</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-8 space-y-4">
          <div className="rounded-3xl bg-card p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold">Top contributing factors</h3>
                <p className="text-xs text-muted-foreground">SHAP values · contribution to predicted slow-down</p>
              </div>
              <span className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground">Model v2024.11 · GBM-traffic</span>
            </div>
            <div className="mt-5 space-y-3">
              {factors.map((f) => (
                <div key={f.label} className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-accent-foreground"><f.icon className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between">
                      <span className="truncate text-sm font-medium">{f.label}</span>
                      <span className={`ml-3 text-xs font-semibold ${f.dir === "up" ? "text-destructive" : "text-success"}`}>{f.dir === "up" ? "+" : "−"}{(f.impact * 100).toFixed(0)}%</span>
                    </div>
                    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-secondary">
                      <div className={`h-full rounded-full ${f.dir === "up" ? "bg-gradient-to-r from-primary to-[oklch(0.7_0.22_25)]" : "bg-success"}`} style={{ width: `${f.impact * 100 * 2.5}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-3xl bg-card p-6">
              <div className="flex items-center gap-2 text-sm font-semibold"><CloudRain className="h-4 w-4 text-primary" /> Weather context</div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-muted-foreground">Conditions</span><span className="font-semibold">Heavy rain</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Temperature</span><span className="font-semibold">24 °C</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Visibility</span><span className="font-semibold">1.8 km</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Wind</span><span className="font-semibold">14 km/h</span></div>
              </div>
            </div>
            <div className="rounded-3xl bg-card p-6">
              <div className="flex items-center gap-2 text-sm font-semibold"><History className="h-4 w-4 text-primary" /> Historical baseline · 17:00 Mon</div>
              <div className="mt-3 space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-muted-foreground">Avg speed (4w)</span><span className="font-semibold">31 km/h</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Avg jam factor</span><span className="font-semibold">5.1</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Today vs avg</span><span className="font-semibold text-destructive">− 19 km/h</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Anomaly score</span><span className="font-semibold">2.8 σ</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}