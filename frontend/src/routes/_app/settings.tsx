import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { MapPin, Bell, Clock, Save } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/dashboard/PageHeader";

const STORAGE_KEY = "ctap_settings";

interface CityConfig {
  enabled: boolean;
  lastUpdate: string;
  segmentCount: number;
  status: "online" | "offline";
}

interface AlertThresholds {
  critical: number;
  high: number;
  medium: number;
}

interface RefreshIntervals {
  traffic: string;
  weather: string;
  alerts: string;
}

interface SettingsData {
  cities: Record<string, CityConfig>;
  thresholds: AlertThresholds;
  intervals: RefreshIntervals;
}

const defaultSettings: SettingsData = {
  cities: {
    Hanoi: {
      enabled: true,
      lastUpdate: "2 min ago",
      segmentCount: 482,
      status: "online",
    },
    "Ho Chi Minh City": {
      enabled: true,
      lastUpdate: "1 min ago",
      segmentCount: 623,
      status: "online",
    },
  },
  thresholds: {
    critical: 0.6,
    high: 0.8,
    medium: 0.9,
  },
  intervals: {
    traffic: "1min",
    weather: "5min",
    alerts: "30s",
  },
};

function loadSettings(): SettingsData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SettingsData>;
      return {
        cities: { ...defaultSettings.cities, ...parsed.cities },
        thresholds: { ...defaultSettings.thresholds, ...parsed.thresholds },
        intervals: { ...defaultSettings.intervals, ...parsed.intervals },
      };
    }
  } catch {
    // ignore parse errors
  }
  return defaultSettings;
}

function saveSettings(data: SettingsData) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData>(loadSettings);

  useEffect(() => {
    setSettings(loadSettings());
  }, []);

  const toggleCity = (city: string) => {
    setSettings((prev) => ({
      ...prev,
      cities: {
        ...prev.cities,
        [city]: {
          ...prev.cities[city],
          enabled: !prev.cities[city].enabled,
        },
      },
    }));
  };

  const setThreshold = (key: keyof AlertThresholds, value: number) => {
    setSettings((prev) => ({
      ...prev,
      thresholds: { ...prev.thresholds, [key]: value },
    }));
  };

  const setInterval = (key: keyof RefreshIntervals, value: string) => {
    setSettings((prev) => ({
      ...prev,
      intervals: { ...prev.intervals, [key]: value },
    }));
  };

  const handleSave = () => {
    saveSettings(settings);
    toast.success("Settings saved successfully");
  };

  const intervalOptions: Record<keyof RefreshIntervals, string[]> = {
    traffic: ["30s", "1min", "5min"],
    weather: ["1min", "5min", "15min"],
    alerts: ["15s", "30s", "1min"],
  };

  const thresholdMeta: {
    key: keyof AlertThresholds;
    label: string;
    description: string;
    min: number;
    max: number;
    step: number;
  }[] = [
    {
      key: "critical",
      label: "Critical",
      description: "speed < threshold × p50 baseline",
      min: 0.5,
      max: 0.9,
      step: 0.01,
    },
    {
      key: "high",
      label: "High",
      description: "speed < threshold × p15 baseline",
      min: 0.6,
      max: 0.95,
      step: 0.01,
    },
    {
      key: "medium",
      label: "Medium",
      description: "speed < threshold × p50 baseline",
      min: 0.7,
      max: 1.0,
      step: 0.01,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Configure cities, alert thresholds, and data refresh intervals"
      />
      <div className="space-y-4">
        {/* Cities & Coverage */}
        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
              <MapPin className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold">Cities & Coverage</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Toggle city monitoring on or off
          </p>
          <div className="mt-4 space-y-3">
            {Object.entries(settings.cities).map(([name, city]) => (
              <div
                key={name}
                className="flex items-center justify-between rounded-2xl border border-border px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      city.status === "online" && city.enabled
                        ? "bg-success"
                        : "bg-destructive"
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium">{name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {city.segmentCount} segments · Last update{" "}
                      {city.lastUpdate}
                    </div>
                  </div>
                </div>
                <Switch
                  checked={city.enabled}
                  onCheckedChange={() => toggleCity(name)}
                  aria-label={`Toggle ${name}`}
                />
              </div>
            ))}
          </div>
        </section>

        {/* Alert Thresholds */}
        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
              <Bell className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold">Alert Thresholds</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Adjust severity trigger levels
          </p>
          <div className="mt-4 space-y-5">
            {thresholdMeta.map((t) => (
              <div key={t.key}>
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-sm font-medium">{t.label}</Label>
                    <p className="text-[11px] text-muted-foreground">
                      {t.description}
                    </p>
                  </div>
                  <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-semibold text-secondary-foreground">
                    {Math.round(settings.thresholds[t.key] * 100)}%
                  </span>
                </div>
                <div className="mt-3">
                  <Slider
                    value={[settings.thresholds[t.key]]}
                    onValueChange={(val) => setThreshold(t.key, val[0])}
                    min={t.min}
                    max={t.max}
                    step={t.step}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Data Refresh Intervals */}
        <section className="rounded-3xl bg-card p-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-accent-foreground">
              <Clock className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold">Data Refresh Intervals</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            How often each data stream is refreshed
          </p>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {(Object.keys(intervalOptions) as (keyof RefreshIntervals)[]).map(
              (key) => (
                <div key={key}>
                  <Label className="mb-2 block text-sm font-medium capitalize">
                    {key} data
                  </Label>
                  <Select
                    value={settings.intervals[key]}
                    onValueChange={(val) => setInterval(key, val)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {intervalOptions[key].map((opt) => (
                        <SelectItem key={opt} value={opt}>
                          {opt}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            )}
          </div>
        </section>

        {/* Save */}
        <div className="flex justify-end pt-2">
          <Button onClick={handleSave}>
            <Save className="mr-2 h-4 w-4" />
            Save settings
          </Button>
        </div>
      </div>
    </div>
  );
}
