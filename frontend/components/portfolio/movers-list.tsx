import { TrendingDown, TrendingUp } from "lucide-react";

import type { MoverItem } from "@/lib/api/types";
import { gainLossClass } from "@/lib/format";

interface MoversListProps {
  title: string;
  items: MoverItem[];
}

/** Plain list of top gainers/losers, ranked by real unrealized P&L%
 * (app/financial/allocation.py::top_movers on the backend — never
 * re-sorted or re-derived here). Deliberately unstyled beyond the basics. */
export function MoversList({ title, items }: MoversListProps) {
  return (
    <div>
      <h3 className="mb-2 text-[11px] tracking-[0.06em] text-muted-foreground uppercase">{title}</h3>
      {items.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">Nothing to show yet.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {items.map((item) => {
            const positive = item.unrealized_pnl_percent >= 0;
            return (
              <li
                key={item.symbol}
                className="flex items-center justify-between gap-3 rounded-md px-1.5 py-1 text-[13px] transition-colors hover:bg-[color-mix(in_srgb,var(--foreground)_5%,transparent)]"
              >
                <span className="flex items-center gap-1.5 font-medium text-foreground">
                  {positive ? (
                    <TrendingUp className="size-3.5 text-gain" />
                  ) : (
                    <TrendingDown className="size-3.5 text-loss" />
                  )}
                  {item.symbol}
                  <span className="text-[11px] text-muted-foreground">({item.asset_class})</span>
                </span>
                <span className={`tabular-nums ${gainLossClass(item.unrealized_pnl_percent)}`}>
                  {positive ? "+" : ""}
                  {item.unrealized_pnl_percent.toFixed(2)}%
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
