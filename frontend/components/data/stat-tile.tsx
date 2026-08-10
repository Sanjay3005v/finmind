import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatTileProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  valueClassName?: string;
  hint?: string;
}

/**
 * Fixed-shape stat card used across dashboard/performance/risk panels so
 * the loading skeleton and the loaded card never shift layout.
 */
export function StatTile({ label, value, icon: Icon, valueClassName, hint }: StatTileProps) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1.5 px-5 py-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] tracking-[0.06em] text-muted-foreground uppercase">{label}</span>
          {Icon ? <Icon className="size-4 text-muted-foreground" aria-hidden /> : null}
        </div>
        <span className={cn("text-[26px] font-normal tracking-[-0.02em]", valueClassName)}>
          {value}
        </span>
        {hint ? <span className="text-[11px] text-muted-foreground">{hint}</span> : null}
      </CardContent>
    </Card>
  );
}
