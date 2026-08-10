"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, createAgentSession, listPortfolios } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

export function NewSessionButton({
  label = "New session",
  className,
}: {
  label?: string;
  className?: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = React.useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token ?? null;
      // The portfolio/risk agent nodes refuse to fabricate numbers without a
      // linked portfolio — auto-attach the user's first one (same "primary
      // portfolio" convention the dashboard uses) rather than starting every
      // session portfolio-less. A dedicated picker for multi-portfolio users
      // is a follow-up, not this phase's scope.
      const portfolios = await listPortfolios(accessToken);
      const session = await createAgentSession(accessToken, {
        portfolio_id: portfolios[0]?.id,
      });
      router.push(`/agents/${session.id}`);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not start a new session. Please try again."
      );
      setLoading(false);
    }
  }

  return (
    <Button onClick={handleClick} disabled={loading} variant="accent-outline" className={className}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
      {label}
    </Button>
  );
}
