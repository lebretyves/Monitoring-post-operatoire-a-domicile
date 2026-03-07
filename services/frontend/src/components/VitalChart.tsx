import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { TrendPoint } from "../types/vitals";

interface VitalChartProps {
  points: TrendPoint[];
}

const VITAL_COLORS = {
  fc: "#15803d",
  spo2: "#2563eb",
  fr: "#eab308",
  tam: "#dc2626",
  temp: "#7c3aed",
};

export function VitalChart({ points }: VitalChartProps) {
  const chartData = points.map((point) => ({
    label: new Date(point.ts).toLocaleTimeString(),
    hr: point.values.hr,
    spo2: point.values.spo2,
    rr: point.values.rr,
    map: roundTam(point.values.map),
    temp: point.values.temp
  }));

  return (
    <div style={{ height: 320, background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
      <h3 style={{ marginTop: 0 }}>Tendances vitales</h3>
      <ResponsiveContainer width="100%" height="88%">
        <LineChart data={chartData}>
          <CartesianGrid stroke="#dbe4ee" strokeDasharray="4 4" />
          <XAxis dataKey="label" minTickGap={24} />
          <YAxis yAxisId="left" domain={[0, 160]} />
          <YAxis yAxisId="right" orientation="right" domain={[34, 41]} />
          <Tooltip
            formatter={(value: number | string, name: string) => {
              const numericValue = Number(value);
              const formatters: Record<string, string> = {
                FC: `${numericValue} bpm`,
                SpO2: `${numericValue}%`,
                FR: `${numericValue}/min`,
                TAM: `${roundTam(numericValue)}`,
                "T\u00B0C": `${numericValue} \u00B0C`
              };
              return [formatters[name] ?? String(value), name];
            }}
          />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="hr" name="FC" stroke={VITAL_COLORS.fc} strokeWidth={2} dot={false} />
          <Line yAxisId="left" type="monotone" dataKey="spo2" name="SpO2" stroke={VITAL_COLORS.spo2} strokeWidth={2} dot={false} />
          <Line yAxisId="left" type="monotone" dataKey="rr" name="FR" stroke={VITAL_COLORS.fr} strokeWidth={2} dot={false} />
          <Line yAxisId="left" type="monotone" dataKey="map" name="TAM" stroke={VITAL_COLORS.tam} strokeWidth={2} dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="temp" name={"T\u00B0C"} stroke={VITAL_COLORS.temp} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function roundTam(value: number | undefined): number {
  return Math.round(Number(value ?? 0));
}
