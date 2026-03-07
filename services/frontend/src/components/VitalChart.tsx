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
import { useEffect, useMemo, useRef, useState } from "react";

import type { TrendPoint } from "../types/vitals";

interface VitalChartProps {
  points: TrendPoint[];
  rangeHours: number;
}

const VITAL_COLORS = {
  fc: "#15803d",
  spo2: "#2563eb",
  fr: "#eab308",
  tam: "#dc2626",
  temp: "#7c3aed",
};

export function VitalChart({ points, rangeHours }: VitalChartProps) {
  const [windowEndIndex, setWindowEndIndex] = useState(0);
  const previousLength = useRef(0);
  const previousRangeHours = useRef(rangeHours);

  const firstTimestamp = points[0]?.ts ?? "";
  const allChartData = useMemo(
    () =>
      points.map((point, index) => ({
        index,
        ts: point.ts,
        hr: point.values.hr,
        spo2: point.values.spo2,
        rr: point.values.rr,
        map: roundTam(point.values.map),
        temp: point.values.temp,
      })),
    [points]
  );

  useEffect(() => {
    if (allChartData.length === 0) {
      setWindowEndIndex(0);
      previousLength.current = 0;
      previousRangeHours.current = rangeHours;
      return;
    }
    const maxIndex = allChartData.length - 1;
    const previousMaxIndex = Math.max(0, previousLength.current - 1);
    const rangeChanged = previousRangeHours.current !== rangeHours;
    const wasNearLatest = windowEndIndex >= Math.max(0, previousMaxIndex - 1);

    setWindowEndIndex((current) => {
      if (rangeChanged || previousLength.current === 0 || wasNearLatest) {
        return maxIndex;
      }
      return Math.max(0, Math.min(current, maxIndex));
    });

    previousLength.current = allChartData.length;
    previousRangeHours.current = rangeHours;
  }, [allChartData.length, rangeHours, windowEndIndex]);

  const maxIndex = Math.max(0, allChartData.length - 1);
  const safeEndIndex = Math.max(0, Math.min(windowEndIndex, maxIndex));
  const startIndex = resolveStartIndexForWindow(allChartData, safeEndIndex, rangeHours);
  const chartData = rangeHours <= 0 ? allChartData : allChartData.slice(startIndex, safeEndIndex + 1);
  const visibleStart = chartData[0]?.ts ?? firstTimestamp;
  const visibleEnd = chartData[chartData.length - 1]?.ts ?? visibleStart;
  const sliderMinEndIndex = resolveMinimumEndIndex(allChartData, rangeHours);
  const showSlider = rangeHours > 0 && allChartData.length > 1 && sliderMinEndIndex < maxIndex;

  return (
    <div style={{ height: 320, background: "#ffffff", borderRadius: 18, padding: 16, boxShadow: "0 12px 24px rgba(15, 23, 42, 0.08)" }}>
      <h3 style={{ marginTop: 0 }}>Tendances vitales</h3>
      <ResponsiveContainer width="100%" height={showSlider ? "76%" : "88%"}>
        <LineChart data={chartData}>
          <CartesianGrid stroke="#dbe4ee" strokeDasharray="4 4" />
          <XAxis
            dataKey="ts"
            minTickGap={24}
            tickFormatter={(value) => formatTimelineTick(String(value), firstTimestamp, visibleStart, visibleEnd)}
          />
          <YAxis yAxisId="left" domain={[0, 160]} />
          <YAxis yAxisId="right" orientation="right" domain={[34, 41]} />
          <Tooltip
            labelFormatter={(value) => formatTooltipLabel(String(value), firstTimestamp)}
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
      {showSlider ? (
        <div style={{ marginTop: 12, display: "grid", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", fontSize: 12 }}>
            <span>{formatWindowEdgeLabel(allChartData[sliderMinEndIndex]?.ts ?? firstTimestamp, firstTimestamp)}</span>
            <span>{formatWindowEdgeLabel(allChartData[maxIndex]?.ts ?? firstTimestamp, firstTimestamp)}</span>
          </div>
          <input
            type="range"
            min={sliderMinEndIndex}
            max={maxIndex}
            step={1}
            value={safeEndIndex}
            onChange={(event) => setWindowEndIndex(Number(event.target.value))}
            style={{ width: "100%", accentColor: "#0f766e" }}
          />
          <div style={{ color: "#475569", fontSize: 13 }}>
            Fenetre affichee: {formatWindowEdgeLabel(visibleStart, firstTimestamp)}{" -> "}{formatWindowEdgeLabel(visibleEnd, firstTimestamp)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function roundTam(value: number | undefined): number {
  return Math.round(Number(value ?? 0));
}

function formatTimelineTick(
  value: string,
  firstTimestamp: string,
  visibleStartTimestamp: string,
  visibleEndTimestamp: string
): string {
  const current = new Date(value).getTime();
  const first = new Date(firstTimestamp).getTime();
  const visibleStart = new Date(visibleStartTimestamp).getTime();
  const visibleEnd = new Date(visibleEndTimestamp).getTime();
  if (!Number.isFinite(current) || !Number.isFinite(first) || !Number.isFinite(visibleStart) || !Number.isFinite(visibleEnd)) {
    return value;
  }
  const spanHours = Math.max(0, (visibleEnd - visibleStart) / 3_600_000);
  const dayIndex = Math.floor((current - first) / 86_400_000);
  const hourMinute = new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (spanHours >= 24) {
    return `J${dayIndex} ${hourMinute}`;
  }
  if (spanHours >= 6) {
    return hourMinute;
  }
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatTooltipLabel(value: string, firstTimestamp: string): string {
  const current = new Date(value).getTime();
  const first = new Date(firstTimestamp).getTime();
  if (!Number.isFinite(current) || !Number.isFinite(first)) {
    return value;
  }
  const dayIndex = Math.floor((current - first) / 86_400_000);
  return `J${dayIndex} - ${new Date(value).toLocaleString([], {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function formatWindowEdgeLabel(value: string, firstTimestamp: string): string {
  const current = new Date(value).getTime();
  const first = new Date(firstTimestamp).getTime();
  if (!Number.isFinite(current) || !Number.isFinite(first)) {
    return value;
  }
  const dayIndex = Math.floor((current - first) / 86_400_000);
  return `J${dayIndex} ${new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function resolveStartIndexForWindow(
  chartData: Array<{ ts: string }>,
  endIndex: number,
  rangeHours: number
): number {
  if (chartData.length === 0) {
    return 0;
  }
  if (rangeHours <= 0) {
    return 0;
  }
  const endTime = new Date(chartData[endIndex].ts).getTime();
  const threshold = endTime - rangeHours * 3_600_000;
  const startIndex = Math.max(
    0,
    chartData.findIndex((point) => new Date(point.ts).getTime() >= threshold)
  );
  return startIndex === -1 ? 0 : startIndex;
}

function resolveMinimumEndIndex(
  chartData: Array<{ ts: string }>,
  rangeHours: number
): number {
  if (chartData.length === 0 || rangeHours <= 0) {
    return 0;
  }
  const firstTime = new Date(chartData[0].ts).getTime();
  const threshold = firstTime + rangeHours * 3_600_000;
  const firstMatchingIndex = chartData.findIndex((point) => new Date(point.ts).getTime() >= threshold);
  return firstMatchingIndex === -1 ? chartData.length - 1 : firstMatchingIndex;
}
