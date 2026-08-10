import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowLeft, PieChart } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HoldingsTable } from "@/components/data/holdings-table";
import { AllocationDonutChart } from "@/components/charts/allocation-donut-chart";
import { SectorBars } from "@/components/charts/sector-bars";
import { Amount } from "@/components/data/amount";
import { EmptyState } from "@/components/data/empty-state";
import { AddHoldingDialog } from "@/components/portfolio/add-holding-dialog";
import { PerformancePanel } from "@/components/portfolio/performance-panel";
import { RefreshPricesButton } from "@/components/portfolio/refresh-prices-button";
import { getAccessToken } from "@/lib/supabase/server";
import {
  ApiError,
  getAllocation,
  getHoldings,
  getPerformance,
  getPortfolio,
  getPriceHistory,
} from "@/lib/api/client";
import { allocationBucketToSlices } from "@/lib/api/types";
import { formatCurrency, gainLossClass } from "@/lib/format";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  return { title: `Portfolio ${id}` };
}

export default async function PortfolioDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const accessToken = await getAccessToken();

  let portfolio;
  try {
    portfolio = await getPortfolio(accessToken, id);
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.code === "PORTFOLIO_NOT_FOUND")) {
      notFound();
    }
    throw err;
  }

  const [holdings, performance, allocation] = await Promise.all([
    getHoldings(accessToken, id),
    getPerformance(accessToken, id, "1M"),
    getAllocation(accessToken, id),
  ]);

  // Real 30-day closes per holding for the Holdings table sparkline column
  // — one Yahoo Finance call per holding, best-effort (a holding Yahoo
  // doesn't cover just renders without a sparkline, never a fake trend).
  const sparklineEntries = await Promise.all(
    holdings.map(async (holding) => {
      try {
        const history = await getPriceHistory(accessToken, id, holding.id, "1mo");
        return [holding.id, history.points.map((p) => p.close)] as const;
      } catch {
        return [holding.id, []] as const;
      }
    })
  );
  const sparklines = Object.fromEntries(sparklineEntries);

  const changePercent = performance.simple_return != null ? performance.simple_return * 100 : null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href="/portfolio"
          className="mb-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          Portfolio
        </Link>
        <p className="text-[11px] tracking-[0.14em] text-muted-foreground uppercase">
          {portfolio.base_currency} portfolio · {holdings.length} holding{holdings.length === 1 ? "" : "s"}
        </p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">{portfolio.name}</h1>
            <div className="mt-1 flex items-baseline gap-3">
              <span className="text-[34px] leading-none font-normal tracking-[-0.03em] text-foreground">
                <Amount>{formatCurrency(allocation.total_market_value, portfolio.base_currency)}</Amount>
              </span>
              {changePercent != null && (
                <span className={`text-sm tabular-nums ${gainLossClass(changePercent)}`}>
                  {changePercent > 0 ? "+" : ""}
                  {changePercent.toFixed(2)}%
                </span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <RefreshPricesButton portfolioId={id} />
            <AddHoldingDialog portfolioId={id} />
          </div>
        </div>
      </div>

      <Tabs defaultValue="holdings">
        <TabsList>
          <TabsTrigger value="holdings">Holdings</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="allocation">Allocation</TabsTrigger>
        </TabsList>

        <TabsContent value="holdings" className="mt-4">
          <HoldingsTable
            holdings={holdings}
            currency={portfolio.base_currency}
            portfolioId={id}
            sparklines={sparklines}
          />
        </TabsContent>

        <TabsContent value="performance" className="mt-4">
          <PerformancePanel
            portfolioId={id}
            currency={portfolio.base_currency}
            initialData={performance}
            holdings={holdings}
          />
        </TabsContent>

        <TabsContent value="allocation" className="mt-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By asset class</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(allocation.by_asset_class.market_value).length > 0 ? (
                  <AllocationDonutChart
                    data={allocationBucketToSlices(allocation.by_asset_class)}
                    currency={portfolio.base_currency}
                  />
                ) : (
                  <EmptyState
                    icon={PieChart}
                    title="No allocation data"
                    description="Sync holdings to see the asset-class breakdown."
                  />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By sector</CardTitle>
              </CardHeader>
              <CardContent>
                {Object.keys(allocation.by_sector.market_value).length > 0 ? (
                  <SectorBars data={allocationBucketToSlices(allocation.by_sector)} />
                ) : (
                  <EmptyState
                    icon={PieChart}
                    title="No sector data"
                    description="Sync holdings to see the sector breakdown."
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
