import Link from "next/link";
import type { Metadata } from "next";
import { Activity, ArrowRight, Bot, Gauge, PlusCircle, TrendingDown, TrendingUp, Wallet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AllocationDonutChart } from "@/components/charts/allocation-donut-chart";
import { HoldingsPnlChart } from "@/components/charts/holdings-pnl-chart";
import { PriceHistoryPanel } from "@/components/portfolio/price-history-panel";
import { Amount } from "@/components/data/amount";
import { EmptyState } from "@/components/data/empty-state";
import { StatTile } from "@/components/data/stat-tile";
import { MoversList } from "@/components/portfolio/movers-list";
import { getAccessToken } from "@/lib/supabase/server";
import {
  getAllocation,
  getHoldings,
  getMovers,
  getPerformance,
  getPriceHistory,
  listPortfolios,
} from "@/lib/api/client";
import { allocationBucketToSlices, type PriceHistoryResponse } from "@/lib/api/types";
import { formatCurrency, formatPercent, gainLossClass } from "@/lib/format";

export const metadata: Metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const accessToken = await getAccessToken();
  const portfolios = await listPortfolios(accessToken);

  if (portfolios.length === 0) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Dashboard</h1>
          <p className="text-[13px] text-muted-foreground">
            Your net worth, allocation, and AI analyst — all in one place.
          </p>
        </div>
        <EmptyState
          icon={Wallet}
          title="Create your first portfolio"
          description="Add a portfolio to start tracking holdings, performance, and risk. FINMIND never shows placeholder numbers — connect real data to see it come alive."
          actionLabel="Create your first portfolio"
          actionHref="/portfolio"
        />
      </div>
    );
  }

  const primaryPortfolio = portfolios[0];
  // Net worth across all portfolios, and the primary portfolio's allocation
  // for the chart below — both derived from the same deterministic
  // allocation endpoint the portfolio pages use, never invented here.
  // "Today's change" needs an intraday/previous-close price series this
  // foundation-stage schema doesn't have yet (see ARCHITECTURE.md §9's
  // note on `_build_equity_curve`) — omitted rather than faked.
  const allocations = await Promise.all(portfolios.map((p) => getAllocation(accessToken, p.id)));
  const netWorth = allocations.reduce((sum, a) => sum + a.total_market_value, 0);
  const allocation = allocations[0];

  // Top movers, per-holding P&L, and portfolio-level risk stats — all real
  // numbers from app/financial (top_movers/position_pnl/performance),
  // scoped to the primary portfolio like the allocation chart above.
  const [movers, holdings, performance] = await Promise.all([
    getMovers(accessToken, primaryPortfolio.id, 5),
    getHoldings(accessToken, primaryPortfolio.id),
    getPerformance(accessToken, primaryPortfolio.id, "1M"),
  ]);

  // Real historical OHLC chart for the largest position, fetched live
  // from Yahoo Finance (app/market_data on the backend) — never derived
  // from transaction book-value like the Performance tab's equity curve.
  // A symbol Yahoo doesn't cover (rare, but possible for a manually-added
  // holding) degrades to an empty state rather than crashing the page.
  const topHolding = [...holdings].sort((a, b) => b.market_value - a.market_value)[0];
  let priceHistory: PriceHistoryResponse | null = null;
  if (topHolding) {
    try {
      priceHistory = await getPriceHistory(accessToken, primaryPortfolio.id, topHolding.id, "1mo");
    } catch {
      priceHistory = null;
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="mb-2 text-[11px] tracking-[0.14em] text-muted-foreground uppercase">Net worth</p>
        <span className="text-[42px] leading-none font-normal tracking-[-0.03em] text-foreground">
          <Amount>{formatCurrency(netWorth, primaryPortfolio.base_currency)}</Amount>
        </span>
        <p className="mt-2 text-xs text-muted-foreground">
          Across {portfolios.length} portfolio{portfolios.length === 1 ? "" : "s"}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              {topHolding ? `${topHolding.symbol} — price history (${topHolding.exchange})` : "Price history"}
            </CardTitle>
            <CardDescription>Real daily candles from the market, not derived from your transactions.</CardDescription>
          </CardHeader>
          <CardContent>
            {topHolding && priceHistory && priceHistory.points.length > 0 ? (
              <PriceHistoryPanel
                portfolioId={primaryPortfolio.id}
                holdingId={topHolding.id}
                initialData={priceHistory}
              />
            ) : (
              <EmptyState
                icon={TrendingUp}
                title="No market data available"
                description={
                  topHolding
                    ? `Yahoo Finance has no data for ${topHolding.symbol} on ${topHolding.exchange}.`
                    : "Add a holding to see its real price history."
                }
              />
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Allocation — {primaryPortfolio.name}</CardTitle>
              <CardDescription>By asset class</CardDescription>
            </CardHeader>
            <CardContent>
              {Object.keys(allocation.by_asset_class.market_value).length > 0 ? (
                <AllocationDonutChart data={allocationBucketToSlices(allocation.by_asset_class)} />
              ) : (
                <EmptyState
                  icon={TrendingUp}
                  title="No allocation data yet"
                  description="Sync a broker or add holdings to see your allocation breakdown."
                  actionLabel="Connect a broker"
                  actionHref="/brokers"
                />
              )}
            </CardContent>
          </Card>

          <Card className="flex flex-1 flex-col justify-between bg-gradient-to-br from-[var(--accent-900)] to-background shadow-[inset_0_0_0_1px_var(--accent-800)]">
            <CardHeader>
              <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Bot className="size-4.5" aria-hidden />
              </div>
              <CardTitle className="mt-2">Ask FINMIND</CardTitle>
              <CardDescription>
                Get a cited answer about your portfolio, risk, or a research question.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="accent-outline" className="w-full">
                <Link href="/agents">
                  Start a research session
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Total return"
          value={performance.simple_return != null ? formatPercent(performance.simple_return * 100) : "—"}
          valueClassName={performance.simple_return != null ? gainLossClass(performance.simple_return) : undefined}
          icon={performance.simple_return != null && performance.simple_return < 0 ? TrendingDown : TrendingUp}
        />
        <StatTile
          label="Sharpe ratio"
          value={performance.sharpe_ratio != null ? performance.sharpe_ratio.toFixed(2) : "—"}
          icon={Gauge}
        />
        <StatTile
          label="Max drawdown"
          value={performance.max_drawdown != null ? formatPercent(performance.max_drawdown * 100) : "—"}
          valueClassName={performance.max_drawdown != null ? "text-loss" : undefined}
          icon={TrendingDown}
        />
        <StatTile
          label="Volatility"
          value={
            performance.annualized_volatility != null
              ? formatPercent(performance.annualized_volatility * 100)
              : "—"
          }
          icon={Activity}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Holdings performance — {primaryPortfolio.name}</CardTitle>
            <CardDescription>Unrealized P&amp;L% per holding — stocks, gold, silver, anything you track.</CardDescription>
          </CardHeader>
          <CardContent>
            {holdings.length > 0 ? (
              <HoldingsPnlChart data={holdings} />
            ) : (
              <EmptyState
                icon={TrendingUp}
                title="No holdings yet"
                description="Sync a broker or add a holding manually to see performance here."
                actionLabel="Go to portfolio"
                actionHref="/portfolio"
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top movers</CardTitle>
            <CardDescription>Most and least profitable holdings right now.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <MoversList title="Most profitable" items={movers.gainers} />
            <MoversList title="Least profitable" items={movers.losers} />
          </CardContent>
        </Card>
      </div>

      <div>
        <Button asChild variant="outline" size="sm">
          <Link href="/portfolio">
            <PlusCircle className="size-4" />
            Manage portfolios
          </Link>
        </Button>
      </div>
    </div>
  );
}
