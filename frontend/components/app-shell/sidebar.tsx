"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Logo } from "@/components/app-shell/logo";
import { SidebarNav } from "@/components/app-shell/sidebar-nav";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  pendingApprovals?: number;
}

/** Desktop sidebar. Collapses to an icon rail; hidden entirely on mobile in favor of the sheet drawer. */
export function Sidebar({ collapsed, onToggle, pendingApprovals = 0 }: SidebarProps) {
  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col bg-sidebar transition-[width] duration-200 md:flex",
        collapsed ? "w-16" : "w-[232px]"
      )}
    >
      <div className="flex h-14 items-center justify-between px-3">
        <Logo collapsed={collapsed} />
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        <SidebarNav collapsed={collapsed} pendingApprovals={pendingApprovals} />
      </div>
      <div className="flex flex-col gap-2 p-2">
        {!collapsed && (
          <div className="flex items-center gap-2.5 rounded-[10px] bg-gradient-to-br from-[var(--accent-900)] to-[color-mix(in_srgb,var(--background)_92%,#000)] px-3 py-2.5 shadow-[inset_0_0_0_1px_var(--accent-800)]">
            <span className="relative flex size-1.5 shrink-0">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-gain opacity-60" />
              <span className="relative inline-flex size-full rounded-full bg-gain" />
            </span>
            <span className="text-xs text-sidebar-foreground/80">Paper mode</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
        </Button>
      </div>
    </aside>
  );
}
