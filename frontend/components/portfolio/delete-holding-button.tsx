"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, deleteHolding } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

interface DeleteHoldingButtonProps {
  portfolioId: string;
  holdingId: string;
  symbol: string;
}

export function DeleteHoldingButton({ portfolioId, holdingId, symbol }: DeleteHoldingButtonProps) {
  const router = useRouter();
  const [deleting, setDeleting] = React.useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      await deleteHolding(data.session?.access_token ?? null, portfolioId, holdingId);
      toast.success(`${symbol} removed.`);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : `Could not remove ${symbol}.`);
      setDeleting(false);
    }
  }

  return (
    <Button variant="ghost" size="icon" aria-label={`Remove ${symbol}`} disabled={deleting} onClick={handleDelete}>
      {deleting ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
    </Button>
  );
}
