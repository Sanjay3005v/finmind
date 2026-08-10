import type { Metadata } from "next";

import { ChatShell } from "@/components/agents/chat-shell";
import { SessionRail } from "@/components/agents/session-rail";
import { getAccessToken } from "@/lib/supabase/server";
import { getAgentMessages, listAgentSessions } from "@/lib/api/client";

export const metadata: Metadata = { title: "Session" };

export default async function AgentSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  const accessToken = await getAccessToken();
  const [messages, sessions] = await Promise.all([
    getAgentMessages(accessToken, sessionId),
    listAgentSessions(accessToken),
  ]);

  return (
    <div className="flex h-[calc(100dvh-130px)] min-h-0 flex-col gap-4">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Research session</h1>
        <p className="text-[13px] text-muted-foreground">
          Every numeric claim is backed by a deterministic tool call, and any proposed trade waits
          for your approval before it goes anywhere.
        </p>
      </div>
      <div className="flex min-h-0 flex-1 gap-4">
        <SessionRail sessions={sessions} activeSessionId={sessionId} />
        <ChatShell sessionId={sessionId} initialMessages={messages} />
      </div>
    </div>
  );
}
