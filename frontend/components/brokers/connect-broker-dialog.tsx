"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Info, Loader2, Plug } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ApiError, createBrokerConnection } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import type { BrokerName } from "@/lib/api/types";

interface ConnectBrokerDialogProps {
  broker: BrokerName;
  brokerLabel: string;
  trigger: React.ReactNode;
}

export function ConnectBrokerDialog({ broker, brokerLabel, trigger }: ConnectBrokerDialogProps) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [connecting, setConnecting] = React.useState(false);

  async function handleConnect() {
    setConnecting(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      await createBrokerConnection(data.session?.access_token ?? null, { broker, mode: "paper" });
      toast.success(`${brokerLabel} connected in paper/demo mode.`);
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : `Could not connect ${brokerLabel}. Please try again.`
      );
    } finally {
      setConnecting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect {brokerLabel}</DialogTitle>
          <DialogDescription>
            This starts a paper/demo connection backed by deterministic fixture data — no real
            brokerage credentials are collected yet.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-start gap-2.5 rounded-lg bg-[var(--accent-900)] px-3 py-2.5 shadow-[inset_0_0_0_1px_var(--accent-800)]">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <p className="text-[12px] text-muted-foreground">
            Live trading is disabled until you explicitly attach real {brokerLabel} sandbox or
            production credentials in a later step. Every order placed in paper mode is simulated.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={handleConnect} disabled={connecting} variant="accent-outline">
            {connecting ? <Loader2 className="size-4 animate-spin" /> : <Plug className="size-4" />}
            Connect in paper mode
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
