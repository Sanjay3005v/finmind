"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Eye, EyeOff, Menu, Search } from "lucide-react";

import { NAV_ITEMS } from "@/components/app-shell/nav-items";
import { Logo } from "@/components/app-shell/logo";
import { SidebarNav } from "@/components/app-shell/sidebar-nav";
import { UserMenu } from "@/components/app-shell/user-menu";
import { useMask } from "@/components/providers/mask-provider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

interface TopbarProps {
  email?: string | null;
  fullName?: string | null;
  pendingApprovals?: number;
}

function routeTitle(pathname: string) {
  const match = NAV_ITEMS.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
  return match?.label ?? "Dashboard";
}

export function Topbar({ email, fullName, pendingApprovals = 0 }: TopbarProps) {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const pathname = usePathname();
  const { masked, toggle } = useMask();

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 bg-background px-3 md:px-6">
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
            <Menu className="size-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 bg-sidebar p-0">
          <SheetHeader className="h-14 justify-center px-3">
            <SheetTitle asChild>
              <Logo />
            </SheetTitle>
          </SheetHeader>
          <div className="py-2">
            <SidebarNav pendingApprovals={pendingApprovals} onNavigate={() => setMobileOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="hidden items-center gap-1 text-xs text-muted-foreground md:flex">
        <span>FINMIND</span>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-foreground">{routeTitle(pathname)}</span>
      </div>

      <div className="flex-1" />

      <button
        type="button"
        className="hidden h-8 items-center gap-2 rounded-lg bg-[color-mix(in_srgb,var(--background)_60%,var(--card))] px-3 text-xs text-muted-foreground shadow-[inset_0_0_0_1px_var(--border)] transition-colors hover:text-foreground lg:flex"
        tabIndex={-1}
        aria-hidden="true"
      >
        <Search className="size-3.5" />
        <span>Search</span>
        <span className="ml-2 rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          ⌘K
        </span>
      </button>

      <Button
        variant="ghost"
        size="icon"
        aria-label={masked ? "Show amounts" : "Hide amounts"}
        aria-pressed={masked}
        onClick={toggle}
        className="text-muted-foreground hover:text-foreground"
      >
        {masked ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </Button>

      <UserMenu email={email} fullName={fullName} />
    </header>
  );
}
