import type { Metadata } from "next";

import { SettingsForm } from "@/components/settings/settings-form";
import { AgentBehaviourCard, LlmRoutingCard } from "@/components/settings/agent-behaviour-card";
import { getAccessToken } from "@/lib/supabase/server";
import { getMe } from "@/lib/api/client";

export const metadata: Metadata = { title: "Settings" };

export default async function SettingsPage() {
  const accessToken = await getAccessToken();
  const profile = await getMe(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Settings</h1>
        <p className="text-[13px] text-muted-foreground">
          Your risk profile shapes how the Portfolio and Risk agents frame recommendations.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <SettingsForm profile={profile} />
        <div className="flex flex-col gap-4">
          <AgentBehaviourCard />
          <LlmRoutingCard />
        </div>
      </div>
    </div>
  );
}
