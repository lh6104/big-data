import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { Bell, CheckCircle2, Clock, MapPin, TrendingUp, AlertTriangle, X } from "lucide-react";

export const Route = createFileRoute("/_app/alerts")({
  component: AlertsPage,
});

const INITIAL_ALERTS = [
  { id: "ALR-2481", loc: "Cau Giay, Hanoi", sev: "Critical", cause: "Accident + heavy rain", eta: "~ 38 min", source: "Anomaly detection", status: "active", t: "2m ago", rising: true },
  { id: "ALR-2479", loc: "District 1, HCMC", sev: "Critical", cause: "Public event spillover", eta: "~ 1h 20m", source: "Rule-based", status: "acknowledged", t: "8m ago", rising: false },
  { id: "ALR-2476", loc: "Nguyen Trai, Hanoi", sev: "High", cause: "Peak hour congestion", eta: "~ 25 min", source: "Model-based", status: "active", t: "14m ago", rising: true },
  { id: "ALR-2470", loc: "Pham Hung, Hanoi", sev: "High", cause: "Predicted slow-down 240m", source: "Model-based", eta: "~ 18 min", status: "active", t: "21m ago", rising: false },
  { id: "ALR-2468", loc: "Long Bien, Hanoi", sev: "Medium", cause: "Construction lane closure", eta: "~ 2h", source: "Rule-based", status: "acknowledged", t: "34m ago", rising: false },
  { id: "ALR-2455", loc: "Dong Da, Hanoi", sev: "Low", cause: "Light slow-down", eta: "~ 8 min", source: "Anomaly detection", status: "resolved", t: "1h ago", rising: false },
];

type Alert = (typeof INITIAL_ALERTS)[number];

const sevTone: Record<string, string> = {
  Critical: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]",
  High: "bg-primary-soft text-accent-foreground",
  Medium: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]",
  Low: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]",
};

const statusTone: Record<string, string> = {
  active: "bg-destructive/10 text-destructive",
  acknowledged: "bg-primary-soft text-accent-foreground",
  resolved: "bg-secondary text-muted-foreground",
};

const filters = ["All", "Critical", "High", "Active", "Acknowledged", "Hanoi", "HCMC"] as const;
type Filter = (typeof filters)[number];

function matches(a: Alert, f: Filter) {
  switch (f) {
    case "All": return true;
    case "Critical": return a.sev === "Critical";
    case "High": return a.sev === "High";
    case "Active": return a.status === "active";
    case "Acknowledged": return a.status === "acknowledged";
    case "Hanoi": return a.loc.includes("Hanoi");
    case "HCMC": return a.loc.includes("HCMC");
  }
}

function AlertsPage() {
  const [filter, setFilter] = useState<Filter>("All");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [alertList, setAlertList] = useState<Alert[]>(INITIAL_ALERTS);
  const [ackLoading, setAckLoading] = useState(false);

  const visible = useMemo(() => alertList.filter((a) => matches(a, filter)), [alertList, filter]);
  const visibleIds = visible.map((a) => a.id);
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));
  const someSelected = visibleIds.some((id) => selected.has(id));
  const selectedIds = visibleIds.filter((id) => selected.has(id));

  const toggleRow = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allSelected) visibleIds.forEach((id) => next.delete(id));
      else visibleIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const clearSelection = () => setSelected(new Set());

  const acknowledgeSelected = async () => {
    if (selectedIds.length === 0) return;
    setAckLoading(true);
    try {
      const res = await fetch("/api/alerts/bulk-ack", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: selectedIds }),
      });
      if (!res.ok) throw new Error("Failed to acknowledge");
      setAlertList((prev) =>
        prev.map((a) => (selectedIds.includes(a.id) ? { ...a, status: "acknowledged" as const } : a))
      );
      clearSelection();
    } catch (e) {
      console.error(e);
    } finally {
      setAckLoading(false);
    }
  };

  return (
    <PlaceholderPage title="Alerts" subtitle="Manage real-time traffic alerts by severity and status">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { l: "Critical", v: "2", i: AlertTriangle, tone: "bg-[oklch(0.94_0.06_25)] text-[oklch(0.5_0.2_25)]" },
            { l: "High", v: "5", i: Bell, tone: "bg-primary-soft text-accent-foreground" },
            { l: "Medium / Low", v: "10", i: Clock, tone: "bg-[oklch(0.95_0.08_70)] text-[oklch(0.45_0.15_70)]" },
            { l: "Resolved 24h", v: "73", i: CheckCircle2, tone: "bg-[oklch(0.93_0.07_155)] text-[oklch(0.4_0.15_155)]" },
          ].map((s) => (
            <div key={s.l} className="rounded-2xl bg-card p-5">
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${s.tone}`}><s.i className="h-5 w-5" /></div>
              <div className="mt-4 text-2xl font-semibold">{s.v}</div>
              <div className="text-xs text-muted-foreground">{s.l}</div>
            </div>
          ))}
        </div>

        <div className="col-span-12 rounded-3xl bg-card p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h3 className="text-base font-semibold">Alert Queue</h3>
              {selectedIds.length > 0 && (
                <>
                  <button
                    onClick={acknowledgeSelected}
                    disabled={ackLoading}
                    className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50"
                  >
                    {ackLoading ? "Acknowledging…" : `Acknowledge selected (${selectedIds.length})`}
                  </button>
                  <button
                    onClick={clearSelection}
                    className="rounded-full p-1.5 text-muted-foreground hover:bg-secondary"
                    aria-label="Clear selection"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {filters.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${filter === f ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="text-left">
                  <th className="pb-3 font-medium w-8">
                    <input
                      type="checkbox"
                      aria-label="Select all"
                      checked={allSelected}
                      ref={(el) => { if (el) el.indeterminate = !allSelected && someSelected; }}
                      onChange={toggleAll}
                      className="h-4 w-4 cursor-pointer accent-primary"
                    />
                  </th>
                  <th className="pb-3 font-medium">ID</th>
                  <th className="pb-3 font-medium">Location</th>
                  <th className="pb-3 font-medium">Severity</th>
                  <th className="pb-3 font-medium">Cause</th>
                  <th className="pb-3 font-medium">ETA</th>
                  <th className="pb-3 font-medium">Source</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Detected</th>
                  <th className="pb-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => (
                  <tr key={a.id} className="border-t border-border">
                    <td className="py-3">
                      <input
                        type="checkbox"
                        aria-label={`Select ${a.id}`}
                        checked={selected.has(a.id)}
                        onChange={() => toggleRow(a.id)}
                        className="h-4 w-4 cursor-pointer accent-primary"
                      />
                    </td>
                    <td className="py-3 font-mono text-[11px] text-muted-foreground">{a.id}</td>
                    <td className="font-medium"><span className="inline-flex items-center gap-1.5"><MapPin className="h-3 w-3 text-muted-foreground" />{a.loc}</span></td>
                    <td><span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${sevTone[a.sev]}`}>{a.sev}{a.rising && <TrendingUp className="h-3 w-3" />}</span></td>
                    <td className="text-muted-foreground">{a.cause}</td>
                    <td className="text-muted-foreground">{a.eta}</td>
                    <td className="text-[11px] text-muted-foreground">{a.source}</td>
                    <td><span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusTone[a.status]}`}>{a.status}</span></td>
                    <td className="text-muted-foreground">{a.t}</td>
                    <td className="space-x-1">
                      {a.status === "active" && <button className="rounded-full bg-foreground px-3 py-1 text-[11px] font-medium text-background">Ack</button>}
                      <button className="rounded-full border border-border px-3 py-1 text-[11px]">Detail</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </PlaceholderPage>
  );
}
