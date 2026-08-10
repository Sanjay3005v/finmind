"use client";

import { useMask } from "@/components/providers/mask-provider";
import { cn } from "@/lib/utils";

interface AmountProps {
  children: string;
  className?: string;
}

/** Wraps an already-formatted currency string so the topbar privacy toggle can mask it. */
export function Amount({ children, className }: AmountProps) {
  const { masked } = useMask();
  return (
    <span className={cn("tabular-nums", className)} aria-label={masked ? "hidden amount" : undefined}>
      {masked ? "••••••" : children}
    </span>
  );
}
