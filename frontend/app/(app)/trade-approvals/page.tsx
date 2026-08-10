import type { Metadata } from "next";

import { TradeApprovalsTabs } from "@/components/trade-approvals/trade-approvals-tabs";
import { getAccessToken } from "@/lib/supabase/server";
import { listTradeApprovals } from "@/lib/api/client";

export const metadata: Metadata = { title: "Trade Approvals" };

export default async function TradeApprovalsPage() {
  const accessToken = await getAccessToken();
  const approvals = await listTradeApprovals(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Trade approvals</h1>
        <p className="text-sm text-muted-foreground">
          Every agent-proposed order pauses here until you decide.
        </p>
      </div>
      <TradeApprovalsTabs approvals={approvals} />
    </div>
  );
}
