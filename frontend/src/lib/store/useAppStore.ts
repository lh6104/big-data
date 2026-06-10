import { create } from "zustand";

export type CityKey = "hanoi" | "hcmc";

type AppState = {
  selectedCity: CityKey;
  selectedSegmentId: string | null;
  setSelectedCity: (city: CityKey) => void;
  setSelectedSegment: (id: string | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  selectedCity: "hanoi",
  selectedSegmentId: null,
  setSelectedCity: (selectedCity) => set({ selectedCity }),
  setSelectedSegment: (selectedSegmentId) => set({ selectedSegmentId }),
}));
