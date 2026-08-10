"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS } from "@/components/app-shell/nav-items";
import { cn } from "@/lib/utils";

interface SidebarNavProps {
  collapsed?: boolean;
  pendingApprovals?: number;
  onNavigate?: () => void;
}

export function SidebarNav({ collapsed, pendingApprovals = 0, onNavigate }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 px-2">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;
        const badge = item.href === "/trade-approvals" && pendingApprovals > 0 ? pendingApprovals : null;

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            title={collapsed ? item.label : undefined}
            className={cn(
              "flex h-[34px] items-center gap-3 rounded-[7px] px-3 text-[13px] font-medium text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              active && "bg-sidebar-accent text-sidebar-accent-foreground shadow-[inset_0_0_0_1px_var(--accent-800)]",
              collapsed && "justify-center px-0"
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            {!collapsed && (
              <>
                <span className="truncate">{item.label}</span>
                {badge != null && (
                  <span className="ml-auto rounded-md bg-[var(--accent-800)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent-100)]">
                    {badge}
                  </span>
                )}
              </>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
