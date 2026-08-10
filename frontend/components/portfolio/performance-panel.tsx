"use client";

import * as React from "react";
import { Activity, Gauge, LineChart, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";

import { HoldingsPnlChart } from "@/components/charts/holdings-pnl-chart";
import { PerformanceLineChart } from "@/components/charts/performance-line-chart";
import { EmptyState } from "@/components/data/empty-state";
import { StatTile } from "@/components/data/stat-tile";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getPerformance } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { formatPercent, gainLossClass } from "@/lib/format";
import type { Holding, PerformanceRange, PerformanceResponse } from "@/lib/api/types";

const RANGES: PerformanceRange[] = ["1M", "3M", "1Y", "ALL"];

interface PerformancePanelProps {
  portfolioId: string;
  currency: string;
  initialData: PerformanceResponse;
  holdings: Holding[];
}

export function PerformancePanel({ portfolioId, currency, initialData, holdings }: PerformancePanelProps) {
  const [range, setRange] = React.useState<PerformanceRange>(initialData.range);
  const [data, setData] = React.useState(initialData);
  const [loading, setLoading] = React.useState(false);

  async function handleRangeChange(next: PerformanceRange) {
    setRange(next);
    setLoading(true);
    try {
      const supabase = createClient();
      const { data: session } = await supabase.auth.getSession();
      const token = session.session?.access_token ?? null;
      const response = await getPerformance(token, portfolioId, next);
      setData(response);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not load performance data.");
    } finally {
      setLoading(false);
    }
  }

  // Backend fields are `Optional[float] = None` — null (not absent) when a
  // portfolio has too little transaction history to compute them yet. `!=
  // null` catches both null and undefined; a bare truthiness/`!== undefined`
  // check would let a real `null` through into `.toFixed()` and crash.
  const totalReturnPercent = data.simple_return != null ? data.simple_return * 100 : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">Portfolio value</h3>
        <Select value={range} onValueChange={(value) => handleRangeChange(value as PerformanceRange)}>
          <SelectTrigger size="sm" className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RANGES.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <Skeleton className="h-72 w-full" />
      ) : data.equity_curve.length > 1 ? (
        <PerformanceLineChart data={data.equity_curve} currency={currency} />
      ) : (
        <EmptyState
          icon={LineChart}
          title="Not enough history yet"
          description="This portfolio needs at least two data points in the selected range to plot a value curve."
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total return"
          value={totalReturnPercent != null ? formatPercent(totalReturnPercent) : "—"}
          valueClassName={totalReturnPercent != null ? gainLossClass(totalReturnPercent) : undefined}
          icon={totalReturnPercent != null && totalReturnPercent < 0 ? TrendingDown : TrendingUp}
        />
        <StatTile
          label="CAGR"
          value={data.cagr != null ? formatPercent(data.cagr * 100) : "—"}
          icon={Activity}
        />
        <StatTile
          label="Sharpe ratio"
          value={data.sharpe_ratio != null ? data.sharpe_ratio.toFixed(2) : "—"}
          icon={Gauge}
        />
        <StatTile
          label="Max drawdown"
          value={data.max_drawdown != null ? formatPercent(data.max_drawdown * 100) : "—"}
          valueClassName={data.max_drawdown != null ? "text-loss" : undefined}
          icon={TrendingDown}
        />
      </div>

      {holdings.length > 0 && (
        <div>
          <h3 className="mb-3 text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
            Unrealised P&amp;L by holding
          </h3>
          <HoldingsPnlChart data={holdings} />
        </div>
      )}
    </div>
  );
}
