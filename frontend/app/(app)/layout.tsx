import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell/app-shell";
import { listTradeApprovals } from "@/lib/api/client";
import { getAccessToken, getCurrentUser } from "@/lib/supabase/server";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();

  // The proxy already guards these routes; this is defense-in-depth in
  // case a Server Function bypasses the proxy matcher (see Next.js 16
  // proxy.js docs).
  if (!user) {
    redirect("/login");
  }

  const fullName =
    typeof user.user_metadata?.full_name === "string" ? user.user_metadata.full_name : null;

  const accessToken = await getAccessToken();
  let pendingApprovals = 0;
  try {
    const pending = await listTradeApprovals(accessToken, "pending");
    pendingApprovals = pending.length;
  } catch {
    pendingApprovals = 0;
  }

  return (
    <AppShell email={user.email} fullName={fullName} pendingApprovals={pendingApprovals}>
      {children}
    </AppShell>
  );
}
