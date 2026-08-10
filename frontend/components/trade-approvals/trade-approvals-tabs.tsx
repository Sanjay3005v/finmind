"use client";

import * as React from "react";
import { Check, ClipboardCheck, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/data/empty-state";
import { ApiError, decideTradeApproval } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TradeApproval, TradeApprovalStatus, TradeDecision } from "@/lib/api/types";

// "executed" (not "approved") is the real terminal success state — the
// decision endpoint moves straight to it synchronously — so it gets the tab
// instead. "rejected" is the other reachable terminal state; "expired" and
// "failed" have no code path that sets them yet (see TradeApprovalStatus).
const TABS: { value: TradeApprovalStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "executed", label: "Executed" },
  { value: "rejected", label: "Rejected" },
];

// Tinted status chip for rows in a decided (executed/rejected) tab — the
// same real `approval.status` the tab is filtered by, just rendered inline
// per-row to match the rest of the table's decision column.
const DECIDED_CHIP: Partial<Record<TradeApprovalStatus, { label: string; className: string }>> = {
  executed: { label: "Executed", className: "bg-gain/15 text-gain" },
  rejected: { label: "Rejected", className: "bg-loss/15 text-loss" },
};

const HEAD_CLASS = "text-[10px] font-medium tracking-[0.09em] text-muted-foreground uppercase";

export function TradeApprovalsTabs({ approvals }: { approvals: TradeApproval[] }) {
  const [items, setItems] = React.useState(approvals);
  const [decidingId, setDecidingId] = React.useState<string | null>(null);

  async function handleDecision(id: string, decision: TradeDecision) {
    setDecidingId(id);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const updated = await decideTradeApproval(data.session?.access_token ?? null, id, {
        decision,
      });
      setItems((prev) => prev.map((item) => (item.id === id ? updated : item)));
      toast.success(decision === "approve" ? "Trade approved." : "Trade rejected.");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not record your decision. Please try again."
      );
    } finally {
      setDecidingId(null);
    }
  }

  return (
    <Tabs defaultValue="pending">
      <TabsList>
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value}>
            {tab.label}
            <span className="ml-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--neutral-900)] px-1 text-[10px] font-medium text-[var(--neutral-300)]">
              {items.filter((i) => i.status === tab.value).length}
            </span>
          </TabsTrigger>
        ))}
      </TabsList>

      {TABS.map((tab) => {
        const rows = items.filter((item) => item.status === tab.value);

        return (
          <TabsContent key={tab.value} value={tab.value} className="mt-4">
            {rows.length === 0 ? (
              <EmptyState
                icon={ClipboardCheck}
                title={`No ${tab.label.toLowerCase()} trades`}
                description={
                  tab.value === "pending"
                    ? "When an agent proposes a trade, it will show up here awaiting your approval."
                    : `Trades you've ${tab.value} will appear here.`
                }
              />
            ) : (
              <Card>
                <Table className="text-[13px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className={HEAD_CLASS}>Symbol</TableHead>
                      <TableHead className={HEAD_CLASS}>Side</TableHead>
                      <TableHead className={cn(HEAD_CLASS, "text-right")}>Qty</TableHead>
                      <TableHead className={HEAD_CLASS}>Proposed</TableHead>
                      <TableHead className={cn(HEAD_CLASS, "text-right")}>Decision</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((approval) => {
                      const decidedChip = DECIDED_CHIP[approval.status];

                      return (
                        <TableRow key={approval.id}>
                          <TableCell className="font-medium text-foreground">
                            {approval.symbol}
                          </TableCell>
                          <TableCell>
                            <span
                              className={cn(
                                "text-xs font-medium uppercase",
                                approval.side === "buy" ? "text-gain" : "text-loss"
                              )}
                            >
                              {approval.side}
                            </span>
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {approval.quantity}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatDateTime(approval.created_at)}
                          </TableCell>
                          <TableCell className="text-right">
                            {tab.value === "pending" ? (
                              <div className="flex justify-end gap-2">
                                <Button
                                  size="sm"
                                  variant="gain-outline"
                                  disabled={decidingId === approval.id}
                                  onClick={() => handleDecision(approval.id, "approve")}
                                >
                                  {decidingId === approval.id ? (
                                    <Loader2 className="size-3.5 animate-spin" />
                                  ) : (
                                    <Check className="size-3.5" />
                                  )}
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="loss-outline"
                                  disabled={decidingId === approval.id}
                                  onClick={() => handleDecision(approval.id, "reject")}
                                >
                                  <X className="size-3.5" />
                                  Reject
                                </Button>
                              </div>
                            ) : decidedChip ? (
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                                  decidedChip.className
                                )}
                              >
                                {decidedChip.label}
                              </span>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </Card>
            )}
          </TabsContent>
        );
      })}
    </Tabs>
  );
}
