import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator, fallback } from "@tanstack/zod-adapter";
import { z } from "zod";
import { useEffect } from "react";
import { PlaceholderPage } from "@/components/dashboard/PlaceholderPage";
import { LiveMapView } from "@/components/live-map/LiveMapView";
import { useAppStore, type CityKey } from "@/lib/store/useAppStore";

const searchSchema = z.object({
  city: fallback(z.enum(["hanoi", "hcmc"]), "hanoi").default("hanoi"),
});

export const Route = createFileRoute("/_app/live-map")({
  validateSearch: zodValidator(searchSchema),
  component: LiveMap,
});

const KEY_TO_LABEL: Record<CityKey, "Hanoi" | "HCMC"> = { hanoi: "Hanoi", hcmc: "HCMC" };
const LABEL_TO_KEY: Record<"Hanoi" | "HCMC", CityKey> = { Hanoi: "hanoi", HCMC: "hcmc" };

function LiveMap() {
  const { city } = Route.useSearch() as { city: CityKey };
  const navigate = useNavigate({ from: "/live-map" });
  const setSelectedCity = useAppStore((s) => s.setSelectedCity);

  useEffect(() => {
    setSelectedCity(city);
  }, [city, setSelectedCity]);

  return (
    <PlaceholderPage title="Live Map" subtitle="Real-time congestion across monitored cities">
      <LiveMapView
        city={KEY_TO_LABEL[city]}
        onCityChange={(label) => navigate({ search: { city: LABEL_TO_KEY[label] } })}
        onViewForecast={(id: string) =>
          navigate({ to: "/forecast", search: { city, segment: id } })
        }
      />
    </PlaceholderPage>
  );
}
