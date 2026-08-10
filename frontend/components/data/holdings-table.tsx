import { Layers } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/data/empty-state";
import { Sparkline } from "@/components/charts/sparkline";
import { DeleteHoldingButton } from "@/components/portfolio/delete-holding-button";
import type { Holding } from "@/lib/api/types";
import { formatCurrency, formatNumber, gainLossClass, signedCurrency } from "@/lib/format";

interface HoldingsTableProps {
  holdings: Holding[];
  currency: string;
  portfolioId: string;
  /** holdingId -> real recent closes (30d), fetched from Yahoo Finance.
   * Missing/short entries just render no sparkline — never a fake trend. */
  sparklines?: Record<string, number[]>;
}

export function HoldingsTable({ holdings, currency, portfolioId, sparklines }: HoldingsTableProps) {
  if (holdings.length === 0) {
    return (
      <EmptyState
        icon={Layers}
        title="No holdings yet"
        description="Sync a broker connection or record a manual transaction to see holdings here."
        actionLabel="Connect a broker"
        actionHref="/brokers"
      />
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg shadow-[inset_0_0_0_1px_var(--border)]">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Symbol</TableHead>
            <TableHead>Class</TableHead>
            <TableHead className="text-right">Qty</TableHead>
            <TableHead className="text-right">Avg</TableHead>
            <TableHead className="text-right">Last</TableHead>
            <TableHead>30d</TableHead>
            <TableHead className="text-right">Market value</TableHead>
            <TableHead className="text-right">Unrealised P/L</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {holdings.map((holding) => {
            const spark = sparklines?.[holding.id];
            return (
              <TableRow key={holding.id}>
                <TableCell className="font-medium">
                  <div>{holding.symbol}</div>
                  <div className="text-[10px] text-muted-foreground">{holding.exchange}</div>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {holding.asset_class ?? "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatNumber(holding.quantity)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(holding.avg_price, currency)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {holding.current_price != null ? formatCurrency(holding.current_price, currency) : "—"}
                </TableCell>
                <TableCell>
                  {spark && spark.length > 1 ? (
                    <Sparkline points={spark} width={60} height={20} className="h-5 w-15" />
                  ) : (
                    <span className="text-[11px] text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right font-medium tabular-nums">
                  {formatCurrency(holding.market_value, currency)}
                </TableCell>
                <TableCell
                  className={`text-right tabular-nums font-medium ${gainLossClass(holding.unrealized_pnl)}`}
                >
                  {signedCurrency(holding.unrealized_pnl, currency)}
                  <span className="ml-1 text-xs">
                    ({holding.unrealized_pnl_percent > 0 ? "+" : ""}
                    {holding.unrealized_pnl_percent.toFixed(2)}%)
                  </span>
                </TableCell>
                <TableCell>
                  <DeleteHoldingButton portfolioId={portfolioId} holdingId={holding.id} symbol={holding.symbol} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
