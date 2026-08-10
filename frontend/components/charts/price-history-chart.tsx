"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { PriceHistoryPoint } from "@/lib/api/types";
import { formatCurrency, formatDate } from "@/lib/format";

interface PriceHistoryChartProps {
  data: PriceHistoryPoint[];
  currency?: string;
}

/** Real historical daily closes fetched live from Yahoo Finance
 * (app/market_data on the backend) — actual calendar dates, not the index-
 * based placeholder the portfolio performance chart uses (that one has no
 * real per-point dates yet, see PerformanceLineChart). */
export function PriceHistoryChart({ data, currency = "INR" }: PriceHistoryChartProps) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(value: string) => formatDate(value)}
            stroke="var(--muted-foreground)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
          />
          <YAxis
            stroke="var(--muted-foreground)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={64}
            domain={["auto", "auto"]}
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
            labelFormatter={(value) => formatDate(String(value))}
            formatter={(value) => [formatCurrency(Number(value), currency), "Close"]}
          />
          <Line type="monotone" dataKey="close" stroke="var(--chart-1)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
