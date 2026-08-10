import type { Metadata } from "next";
import { Building2, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConnectBrokerDialog } from "@/components/brokers/connect-broker-dialog";
import { SyncBrokerButton } from "@/components/brokers/sync-broker-button";
import { getAccessToken } from "@/lib/supabase/server";
import { listBrokerConnections } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BrokerConnectionStatus, BrokerName } from "@/lib/api/types";

export const metadata: Metadata = { title: "Brokers" };

const BROKERS: { id: BrokerName; label: string }[] = [
  { id: "dhan", label: "DhanHQ" },
  { id: "angelone", label: "Angel One" },
  { id: "upstox", label: "Upstox" },
  { id: "fyers", label: "FYERS" },
];

const STATUS_META: Record<
  BrokerConnectionStatus,
  { label: string; chipClassName: string; dotClassName: string }
> = {
  connected: {
    label: "Connected",
    chipClassName: "bg-gain/15 text-gain",
    dotClassName: "bg-gain",
  },
  error: {
    label: "Error",
    chipClassName: "bg-loss/15 text-loss",
    dotClassName: "bg-loss",
  },
  disconnected: {
    label: "Disconnected",
    chipClassName: "bg-[var(--neutral-900)] text-[var(--neutral-500)]",
    dotClassName: "bg-[var(--neutral-500)]",
  },
};

export default async function BrokersPage() {
  const accessToken = await getAccessToken();
  const connections = await listBrokerConnections(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Brokers</h1>
        <p className="text-sm text-muted-foreground">
          Connect a brokerage to sync holdings, positions, and orders.
        </p>
      </div>

      <div className="flex items-start gap-2.5 rounded-lg bg-[var(--accent-900)] px-3 py-2.5 shadow-[inset_0_0_0_1px_var(--accent-800)]">
        <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <div className="space-y-0.5">
          <p className="text-[13px] font-medium text-foreground">Paper/demo mode</p>
          <p className="text-[12px] text-muted-foreground">
            Every connection below defaults to simulated paper trading with fixture data. No live
            order will ever be placed until you explicitly attach real credentials and switch a
            connection to live mode.
          </p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {BROKERS.map((broker) => {
          const connection = connections.find((c) => c.broker === broker.id);
          const status: BrokerConnectionStatus = connection?.status ?? "disconnected";
          const meta = STATUS_META[status];

          return (
            <Card key={broker.id}>
              <CardHeader className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex size-9 items-center justify-center rounded-lg bg-[var(--neutral-900)]">
                    <Building2 className="size-4.5 text-[var(--neutral-500)]" />
                  </div>
                  <CardTitle>{broker.label}</CardTitle>
                </div>
                <span
                  className={cn(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
                    meta.chipClassName
                  )}
                >
                  <span className={cn("size-1.5 rounded-full", meta.dotClassName)} aria-hidden />
                  {meta.label}
                </span>
              </CardHeader>
              <CardContent className="flex items-center justify-between gap-2">
                <div className="text-[11px] text-muted-foreground">
                  {connection ? (
                    <>
                      <span className="capitalize">{connection.mode}</span> mode
                      {connection.last_synced_at && (
                        <> · synced {formatDateTime(connection.last_synced_at)}</>
                      )}
                    </>
                  ) : (
                    "Not connected yet"
                  )}
                </div>
                {connection ? (
                  <SyncBrokerButton connectionId={connection.id} brokerLabel={broker.label} />
                ) : (
                  <ConnectBrokerDialog
                    broker={broker.id}
                    brokerLabel={broker.label}
                    trigger={
                      <Button variant="accent-outline" size="sm">
                        Connect
                      </Button>
                    }
                  />
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
