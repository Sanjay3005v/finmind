import Link from "next/link";
import type { Metadata } from "next";
import { ArrowRight, PlusCircle, Wallet } from "lucide-react";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Sparkline } from "@/components/charts/sparkline";
import { Amount } from "@/components/data/amount";
import { EmptyState } from "@/components/data/empty-state";
import { NewPortfolioDialog } from "@/components/portfolio/new-portfolio-dialog";
import { getAccessToken } from "@/lib/supabase/server";
import { getAllocation, getPerformance, listPortfolios } from "@/lib/api/client";
import { formatCurrency, gainLossClass } from "@/lib/format";

export const metadata: Metadata = { title: "Portfolio" };

export default async function PortfolioListPage() {
  const accessToken = await getAccessToken();
  const portfolios = await listPortfolios(accessToken);
  // Portfolios carry no computed value themselves (see DATABASE_SCHEMA.sql) —
  // total market value and the sparkline/change line are derived from the
  // same deterministic allocation/performance endpoints the detail page
  // uses, never invented client-side.
  const [totals, performances] = await Promise.all([
    Promise.all(portfolios.map((p) => getAllocation(accessToken, p.id).then((a) => a.total_market_value))),
    Promise.all(
      portfolios.map((p) =>
        getPerformance(accessToken, p.id, "1M").catch(() => null)
      )
    ),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Portfolio</h1>
          <p className="text-[13px] text-muted-foreground">
            Manage every portfolio you track with FINMIND.
          </p>
        </div>
        {portfolios.length > 0 && <NewPortfolioDialog />}
      </div>

      {portfolios.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title="Create your first portfolio"
          description="A portfolio groups holdings, transactions, and performance under one base currency."
          action={<NewPortfolioDialog />}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {portfolios.map((portfolio, i) => {
            const performance = performances[i];
            const changePercent = performance?.simple_return != null ? performance.simple_return * 100 : null;

            return (
              <Link key={portfolio.id} href={`/portfolio/${portfolio.id}`} className="group block">
                <Card className="h-full transition-shadow group-hover:shadow-[inset_0_0_0_1px_var(--accent-700)]">
                  <CardHeader className="flex-row items-center justify-between space-y-0">
                    <div>
                      <p className="text-[15px] font-medium text-foreground">{portfolio.name}</p>
                      <span className="mt-1 inline-flex rounded-md bg-[var(--neutral-900)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--neutral-400)]">
                        {portfolio.base_currency}
                      </span>
                    </div>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-2xl font-normal tracking-[-0.02em] tabular-nums text-foreground">
                      <Amount>{formatCurrency(totals[i], portfolio.base_currency)}</Amount>
                    </p>
                    {changePercent != null && (
                      <p className={`text-xs tabular-nums ${gainLossClass(changePercent)}`}>
                        {changePercent > 0 ? "+" : ""}
                        {changePercent.toFixed(2)}% · 1M
                      </p>
                    )}
                    {performance && performance.equity_curve.length > 1 && (
                      <Sparkline points={performance.equity_curve} className="h-11 w-full" />
                    )}
                  </CardContent>
                </Card>
              </Link>
            );
          })}

          <NewPortfolioDialog
            trigger={
              <button
                type="button"
                className="flex h-full min-h-[168px] w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                <PlusCircle className="size-5" />
                <span className="text-sm">Add a portfolio</span>
              </button>
            }
          />
        </div>
      )}
    </div>
  );
}
