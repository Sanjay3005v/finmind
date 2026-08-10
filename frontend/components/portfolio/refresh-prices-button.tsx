"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, refreshHoldingPrices } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

/** Pulls a real, live quote for every holding from Yahoo Finance
 * (app/market_data on the backend) and updates current_price — the only
 * way a manually-added holding (gold, silver, anything with no broker)
 * gets a real, current market price rather than staying at whatever was
 * typed in once. */
export function RefreshPricesButton({ portfolioId }: { portfolioId: string }) {
  const router = useRouter();
  const [loading, setLoading] = React.useState(false);

  async function handleRefresh() {
    setLoading(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const result = await refreshHoldingPrices(data.session?.access_token ?? null, portfolioId);
      if (result.updated.length > 0) {
        toast.success(`Refreshed ${result.updated.length} price(s) from the market.`);
      }
      if (result.failed.length > 0) {
        toast.error(
          `Could not price: ${result.failed.map((f) => f.symbol).join(", ")}. They may not be listed on NSE/BSE.`
        );
      }
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not refresh prices.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button size="sm" variant="outline" onClick={handleRefresh} disabled={loading}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
      Refresh prices
    </Button>
  );
}
