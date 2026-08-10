"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, syncBrokerConnection } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

interface SyncBrokerButtonProps {
  connectionId: string;
  brokerLabel: string;
}

export function SyncBrokerButton({ connectionId, brokerLabel }: SyncBrokerButtonProps) {
  const router = useRouter();
  const [syncing, setSyncing] = React.useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const result = await syncBrokerConnection(data.session?.access_token ?? null, connectionId);
      toast.success(`${brokerLabel} synced — ${result.holdings_synced} holding(s) updated.`);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : `Could not sync ${brokerLabel}. Please try again.`);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={handleSync} disabled={syncing}>
      {syncing ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
      Sync now
    </Button>
  );
}
