"use client";
import { useMemo } from "react";

interface Sample {
  t: number; x: number; z: number;
  spd: number; thr: number; brk: number;
  gear: number; drs: number; dist: number;
  ers?: number; str?: number; fuel?: number; tw?: number;
}

type ColorMetric = "speed" | "throttle" | "brake" | "gear" | "ers" | "steer" | "tyre_wear";

interface TrackMapProps {
  samples: Sample[];
  metric?: ColorMetric;
  width?: number;
  height?: number;
  teamColor?: string;
}

const METRIC_MAX: Record<ColorMetric, number> = {
  speed: 350,
  throttle: 1.0,
  brake: 1.0,
  gear: 8,
  ers: 4.0,
  steer: 1.0,
  tyre_wear: 100,
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function valueToColor(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  const r = t < 0.5 ? 255 : Math.round(lerp(255, 0, (t - 0.5) * 2));
  const g = t < 0.5 ? Math.round(lerp(0, 255, t * 2)) : 255;
  return `rgb(${r},${g},0)`;
}

function brakeColor(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  const r = Math.round(lerp(50, 255, t));
  return `rgb(${r},0,0)`;
}

function throttleColor(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  const g = Math.round(lerp(50, 255, t));
  return `rgb(0,${g},0)`;
}

function gearColor(gear: number): string {
  const palette = [
    "#555", "#ff4444", "#ff8c00", "#ffd700",
    "#aadd00", "#44dd44", "#00ddaa", "#00aaff", "#aa00ff",
  ];
  return palette[Math.min(gear, 8)] ?? "#888";
}

function ersColor(v: number): string {
  const t = Math.max(0, Math.min(1, v / METRIC_MAX.ers));
  const b = Math.round(lerp(50, 255, t));
  const g = Math.round(lerp(0, 180, t));
  return `rgb(0,${g},${b})`;
}

function steerColor(v: number): string {
  const t = Math.max(-1, Math.min(1, v));
  if (Math.abs(t) < 0.05) return "#444";
  if (t < 0) {
    const s = Math.abs(t);
    return `rgb(${Math.round(30 * (1 - s))},${Math.round(100 + 155 * s)},${Math.round(200 + 55 * s)})`;
  }
  return `rgb(${Math.round(200 + 55 * t)},${Math.round(140 * (1 - t))},0)`;
}

function tyreWearColor(v: number): string {
  const t = Math.max(0, Math.min(1, v / 100));
  if (t < 0.3) return `rgb(0,${Math.round(200 + 55 * (t / 0.3))},0)`;
  if (t < 0.6) return `rgb(${Math.round(255 * ((t - 0.3) / 0.3))},255,0)`;
  return `rgb(255,${Math.round(255 * (1 - (t - 0.6) / 0.4))},0)`;
}

function getColor(sample: Sample, metric: ColorMetric): string {
  switch (metric) {
    case "speed": return valueToColor(sample.spd / METRIC_MAX.speed);
    case "throttle": return throttleColor(sample.thr);
    case "brake": return brakeColor(sample.brk);
    case "gear": return gearColor(sample.gear);
    case "ers": return ersColor(sample.ers ?? 0);
    case "steer": return steerColor(sample.str ?? 0);
    case "tyre_wear": return tyreWearColor(sample.tw ?? 0);
  }
}

export default function TrackMap({
  samples,
  metric = "speed",
  width = 600,
  height = 500,
}: TrackMapProps) {
  const { segments, minX, minZ, scaleX, scaleZ, pad } = useMemo(() => {
    if (!samples.length) return { segments: [], minX: 0, minZ: 0, scaleX: 1, scaleZ: 1, pad: 20 };

    const xs = samples.map((s) => s.x);
    const zs = samples.map((s) => s.z);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minZ = Math.min(...zs), maxZ = Math.max(...zs);

    const pad = 20;
    const rangeX = maxX - minX || 1;
    const rangeZ = maxZ - minZ || 1;
    const scaleX = (width - pad * 2) / rangeX;
    const scaleZ = (height - pad * 2) / rangeZ;

    const segments = [];
    for (let i = 0; i < samples.length - 1; i++) {
      const s = samples[i];
      const n = samples[i + 1];
      segments.push({
        x1: pad + (s.x - minX) * scaleX,
        z1: pad + (s.z - minZ) * scaleZ,
        x2: pad + (n.x - minX) * scaleX,
        z2: pad + (n.z - minZ) * scaleZ,
        color: getColor(s, metric),
      });
    }
    return { segments, minX, minZ, scaleX, scaleZ, pad };
  }, [samples, metric, width, height]);

  if (!samples.length) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-500" style={{ width, height }}>
        Нет телеметрии
      </div>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="bg-[#0f0f13] rounded-lg"
    >
      <polyline
        points={samples
          .map((s) => `${pad + (s.x - minX) * scaleX},${pad + (s.z - minZ) * scaleZ}`)
          .join(" ")}
        fill="none"
        stroke="#2a2a35"
        strokeWidth={8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {segments.map((seg, i) => (
        <line
          key={i}
          x1={seg.x1} y1={seg.z1}
          x2={seg.x2} y2={seg.z2}
          stroke={seg.color}
          strokeWidth={4}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}

export function SpeedLegend({ maxSpeed = 350 }: { maxSpeed?: number }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      <span>0</span>
      <div
        className="h-2 w-32 rounded"
        style={{
          background: "linear-gradient(to right, #ff0000, #ffff00, #00ff00)",
        }}
      />
      <span>{maxSpeed} km/h</span>
    </div>
  );
}
