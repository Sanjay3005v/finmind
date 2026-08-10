import Link from "next/link";
import { LineChart } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({ collapsed, className }: { collapsed?: boolean; className?: string }) {
  return (
    <Link
      href="/dashboard"
      className={cn("flex items-center gap-2.5 px-1 font-medium", className)}
    >
      <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-[inset_0_0_0_1px_var(--accent-700)]">
        <LineChart className="size-3.5" aria-hidden />
      </span>
      {!collapsed && (
        <span className="text-[13px] font-medium tracking-[0.18em] text-sidebar-foreground uppercase">
          FINMIND
        </span>
      )}
    </Link>
  );
}
