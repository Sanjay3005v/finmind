"use client";

import * as React from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { TradeApprovalCard } from "@/components/agents/trade-approval-card";
import { ApiError, getTradeApproval } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import type { TradeApproval } from "@/lib/api/types";

interface TradeApprovalInlineProps {
  tradeApprovalId: string;
  onDecided?: () => void;
}

/** Fetches and renders a single trade approval referenced by a chat message. */
export function TradeApprovalInline({ tradeApprovalId, onDecided }: TradeApprovalInlineProps) {
  const [approval, setApproval] = React.useState<TradeApproval | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const supabase = createClient();
        const { data } = await supabase.auth.getSession();
        const result = await getTradeApproval(data.session?.access_token ?? null, tradeApprovalId);
        if (active) setApproval(result);
      } catch (err) {
        if (active) {
          setError(err instanceof ApiError ? err.message : "Could not load this trade proposal.");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [tradeApprovalId]);

  if (error) {
    return <p className="max-w-md text-sm text-loss">{error}</p>;
  }

  if (!approval) {
    return <Skeleton className="h-40 w-full max-w-md" />;
  }

  return <TradeApprovalCard approval={approval} onDecided={onDecided} />;
}
