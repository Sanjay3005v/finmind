"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCurrency } from "@/lib/format";

interface PerformanceLineChartProps {
  /** Raw point values, no dates — this foundation-stage schema has no
   * historical price table yet (see ARCHITECTURE.md §9), so the x-axis is an
   * honest sequence index rather than a fabricated calendar date. */
  data: number[];
  currency?: string;
}

/** Single-series line — no legend needed (the axis + tooltip name it). */
export function PerformanceLineChart({ data, currency = "INR" }: PerformanceLineChartProps) {
  const points = data.map((value, index) => ({ index, value }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="index"
            stroke="var(--muted-foreground)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            minTickGap={32}
          />
          <YAxis
            stroke="var(--muted-foreground)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={64}
            tickFormatter={(value: number) => formatCurrency(value, currency)}
          />
          <Tooltip
            contentStyle={{
              background: "var(--popover)",
              color: "var(--popover-foreground)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: 12,
            }}
            labelFormatter={(value) => `Point ${value}`}
            formatter={(value) => [formatCurrency(Number(value), currency), "Portfolio value"]}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
