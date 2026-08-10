"use client";

import * as React from "react";
import { AlertTriangle, Check, Loader2, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ApiError, decideTradeApproval } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import type { TradeApproval, TradeDecision } from "@/lib/api/types";

interface TradeApprovalCardProps {
  approval: TradeApproval;
  onDecided?: (updated: TradeApproval) => void;
}

const STATUS_STYLE: Record<TradeApproval["status"], string> = {
  pending: "",
  approved: "text-gain",
  executed: "text-gain",
  rejected: "text-loss",
  expired: "text-muted-foreground",
  failed: "text-loss",
};

/**
 * Renders a proposed trade awaiting human sign-off. The decision button
 * calls the real `POST /trade-approvals/{id}/decision` endpoint, which
 * itself resumes the paused LangGraph `interrupt()` for this session.
 */
export function TradeApprovalCard({ approval, onDecided }: TradeApprovalCardProps) {
  const [current, setCurrent] = React.useState(approval);
  const [decidingAs, setDecidingAs] = React.useState<TradeDecision | null>(null);

  async function handleDecision(decision: TradeDecision) {
    setDecidingAs(decision);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const updated = await decideTradeApproval(data.session?.access_token ?? null, current.id, {
        decision,
      });
      setCurrent(updated);
      onDecided?.(updated);
      toast.success(decision === "approve" ? "Trade approved." : "Trade rejected.");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not record your decision. Please try again."
      );
    } finally {
      setDecidingAs(null);
    }
  }

  const sideClass = current.side === "buy" ? "text-gain" : "text-loss";

  return (
    <Card className="max-w-[420px] gap-3 bg-gradient-to-br from-[var(--accent-900)] to-background shadow-[inset_0_0_0_1px_var(--accent-800)]">
      <CardHeader className="gap-0">
        <div className="flex items-center gap-2">
          <AlertTriangle className="size-3.5 text-[var(--accent-300)]" aria-hidden />
          <span className="text-[11px] tracking-[0.06em] text-primary uppercase">Approval required</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[19px] text-foreground">{current.symbol}</span>
          <span className={`text-[13px] tracking-[0.08em] uppercase ${sideClass}`}>{current.side}</span>
        </div>
        <div className="rounded-[7px] bg-background px-2.5 py-2">
          <div className="text-[10px] tracking-[0.06em] text-muted-foreground uppercase">Quantity</div>
          <div className="mt-0.5 text-sm tabular-nums text-foreground">{current.quantity}</div>
        </div>
        {current.reasoning && (
          <p className="text-[12px] leading-[1.6] text-muted-foreground">{current.reasoning}</p>
        )}

        {current.status === "pending" ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="gain-outline"
              className="flex-1"
              disabled={decidingAs !== null}
              onClick={() => handleDecision("approve")}
            >
              {decidingAs === "approve" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Check className="size-4" />
              )}
              Approve
            </Button>
            <Button
              size="sm"
              variant="loss-outline"
              className="flex-1"
              disabled={decidingAs !== null}
              onClick={() => handleDecision("reject")}
            >
              {decidingAs === "reject" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <X className="size-4" />
              )}
              Reject
            </Button>
          </div>
        ) : (
          <div className={`rounded-[7px] bg-background px-2.5 py-2 text-[12px] capitalize ${STATUS_STYLE[current.status]}`}>
            {current.status}
          </div>
        )}

        <p className="text-[10px] text-muted-foreground">
          Paper mode — no live order will be placed.
        </p>
      </CardContent>
    </Card>
  );
}
