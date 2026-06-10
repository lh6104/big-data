import { createFileRoute } from "@tanstack/react-router";

type Status = "free" | "slow" | "congested";

type UpstreamSegment = {
  id: string;
  name: string;
  road_class: string;
  speed_kmh: number;
  status: Status;
};

// Deterministic mock chain per segment id.
function hashSeed(str: string) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function statusFromSpeed(speed: number): Status {
  if (speed < 18) return "congested";
  if (speed < 32) return "slow";
  return "free";
}

const STREET_POOL = [
  "Cau Giay",
  "Xuan Thuy",
  "Ho Tung Mau",
  "Pham Hung",
  "Pham Van Dong",
  "Tran Duy Hung",
  "Lang Ha",
  "Nguyen Chi Thanh",
  "Kim Ma",
  "Giang Vo",
];

export const Route = createFileRoute("/api/segments/$id/upstream")({
  server: {
    handlers: {
      GET: async ({ params }) => {
        const seed = hashSeed(params.id);
        const length = 4 + (seed % 3); // 4-6 segments
        const drift = Date.now() / 60000; // changes every minute for refresh feel

        const chain: UpstreamSegment[] = Array.from({ length }, (_, i) => {
          const nameIdx = (seed + i * 7) % STREET_POOL.length;
          const baseSpeed = 12 + ((seed >> (i + 1)) % 35);
          const wobble = Math.sin(drift + i) * 4;
          const speed = Math.max(5, Math.round(baseSpeed + wobble));
          return {
            id: i === 0 ? params.id : `${params.id}-up${i}`,
            name: `${STREET_POOL[nameIdx]} · seg ${i + 1}`,
            road_class: i % 2 === 0 ? "arterial" : "collector",
            speed_kmh: speed,
            status: statusFromSpeed(speed),
          };
        });

        return Response.json({
          segment_id: params.id,
          updated_at: new Date().toISOString(),
          chain,
        });
      },
    },
  },
});
