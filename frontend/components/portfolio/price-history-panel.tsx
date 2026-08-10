"use client";

import * as React from "react";
import { toast } from "sonner";

import { CandlestickChart } from "@/components/charts/candlestick-chart";
import { PriceHistoryChart } from "@/components/charts/price-history-chart";
import { EmptyState } from "@/components/data/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getPriceHistory } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import type { PriceHistoryRange, PriceHistoryResponse } from "@/lib/api/types";
import { TrendingUp } from "lucide-react";

const RANGES: PriceHistoryRange[] = ["5d", "1mo", "3mo", "6mo", "1y", "5y"];
const RANGE_LABELS: Record<PriceHistoryRange, string> = {
  "5d": "5D",
  "1mo": "1M",
  "3mo": "3M",
  "6mo": "6M",
  "1y": "1Y",
  "5y": "5Y",
};

interface PriceHistoryPanelProps {
  portfolioId: string;
  holdingId: string;
  initialData: PriceHistoryResponse;
}

export function PriceHistoryPanel({ portfolioId, holdingId, initialData }: PriceHistoryPanelProps) {
  const [range, setRange] = React.useState<PriceHistoryRange>("1mo");
  const [data, setData] = React.useState(initialData);
  const [loading, setLoading] = React.useState(false);

  async function handleRangeChange(next: PriceHistoryRange) {
    setRange(next);
    setLoading(true);
    try {
      const supabase = createClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session.session?.access_token ?? null;
      const response = await getPriceHistory(token, portfolioId, holdingId, next);
      setData(response);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not load price history.");
    } finally {
      setLoading(false);
    }
  }

  const hasCandles = data.points.some((p) => p.open != null && p.high != null && p.low != null);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end gap-1 rounded-lg bg-background p-[3px] shadow-[inset_0_0_0_1px_var(--border)]">
        {RANGES.map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => handleRangeChange(r)}
            className={
              "rounded-[6px] px-2.5 py-1 text-xs font-medium transition-colors " +
              (r === range
                ? "bg-[color-mix(in_srgb,var(--card)_60%,var(--primary)_16%)] text-[var(--accent-300)]"
                : "text-muted-foreground hover:text-foreground")
            }
          >
            {RANGE_LABELS[r]}
          </button>
        ))}
      </div>

      {loading ? (
        <Skeleton className="h-64 w-full" />
      ) : data.points.length === 0 ? (
        <EmptyState
          icon={TrendingUp}
          title="No market data available"
          description={`Yahoo Finance has no data for ${data.symbol} on ${data.exchange} for this range.`}
        />
      ) : (
        <div className="h-64 w-full">
          {hasCandles ? (
            <CandlestickChart data={data.points} currency={data.currency} />
          ) : (
            <PriceHistoryChart data={data.points} currency={data.currency} />
          )}
        </div>
      )}
    </div>
  );
}
