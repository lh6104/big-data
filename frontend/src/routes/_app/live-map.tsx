import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import type { ComponentType } from "react";
import { useEffect, useState } from "react";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc", "all"]), "hanoi").default("hanoi"),
});

export const Route = createFileRoute("/_app/live-map")({
  validateSearch: zodValidator(searchSchema),
  component: LiveMap,
});

type MapCityKey = CityKey | "all";
type MapCityLabel = "All" | "Hanoi" | "HCMC";

const KEY_TO_LABEL: Record<MapCityKey, MapCityLabel> = { all: "All", hanoi: "Hanoi", hcmc: "HCMC" };
const LABEL_TO_KEY: Record<MapCityLabel, MapCityKey> = { All: "all", Hanoi: "hanoi", HCMC: "hcmc" };

function LiveMap() {
  const { city } = Route.useSearch() as { city: MapCityKey };
  const navigate = useNavigate({ from: "/live-map" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);

  useEffect(() => {
    if (city !== "all") setSelectedCity(city);
  }, [city, setSelectedCity]);

  return (
    <PlaceholderPage title="Live Map" subtitle="Real-time congestion across monitored cities">
      <ClientLiveMapView
        city={KEY_TO_LABEL[city]}
        onCityChange={(label) => navigate({ search: { city: LABEL_TO_KEY[label] } })}
        onViewForecast={(id: string) =>
          navigate({ to: "/forecast", search: { city: city === "all" ? "hanoi" : city, segment: id } })
        }
      />
    </PlaceholderPage>
  );
}

function ClientLiveMapView(props: {
  city: MapCityLabel;
  onCityChange: (city: MapCityLabel) => void;
  onViewForecast: (segmentId: string) => void;
}) {
  const [LiveMapView, setLiveMapView] = useState<null | ComponentType<typeof props>>(null);

  useEffect(() => {
    let active = true;
    import("@/components/live-map/LiveMapView").then((module) => {
      if (active) setLiveMapView(() => module.LiveMapView);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!LiveMapView) {
    return <div className="h-[640px] rounded-3xl bg-card p-6 text-sm text-muted-foreground">Loading map...</div>;
  }
  return <LiveMapView {...props} />;
}
