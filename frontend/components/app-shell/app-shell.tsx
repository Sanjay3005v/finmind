"use client";

import * as React from "react";

import { Sidebar } from "@/components/app-shell/sidebar";
import { Topbar } from "@/components/app-shell/topbar";
import { MaskProvider } from "@/components/providers/mask-provider";

interface AppShellProps {
  email?: string | null;
  fullName?: string | null;
  pendingApprovals?: number;
  children: React.ReactNode;
}

export function AppShell({ email, fullName, pendingApprovals = 0, children }: AppShellProps) {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <MaskProvider>
      <div className="flex h-dvh overflow-hidden bg-background">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          pendingApprovals={pendingApprovals}
        />
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <Topbar email={email} fullName={fullName} pendingApprovals={pendingApprovals} />
          <main className="flex-1 overflow-y-auto px-4 py-6 md:px-6 md:pb-14">
            <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-6">{children}</div>
          </main>
        </div>
      </div>
    </MaskProvider>
  );
}
