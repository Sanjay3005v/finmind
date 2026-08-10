import Link from "next/link";
import type { Metadata } from "next";
import { Bot, MessageSquare } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/data/empty-state";
import { NewSessionButton } from "@/components/agents/new-session-button";
import { getAccessToken } from "@/lib/supabase/server";
import { listAgentSessions } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = { title: "Agents" };

export default async function AgentsPage() {
  const accessToken = await getAccessToken();
  const sessions = await listAgentSessions(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Agents</h1>
          <p className="text-[13px] text-muted-foreground">
            Research sessions with your AI investment analyst.
          </p>
        </div>
        {sessions.length > 0 && <NewSessionButton />}
      </div>

      {sessions.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="Start a new research session"
          description="Ask FINMIND about your portfolio, a filing, or a risk question. Every claim is backed by a tool call and a citation."
          action={<NewSessionButton label="Start a new research session" />}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sessions.map((session) => (
            <Link key={session.id} href={`/agents/${session.id}`} className="group block">
              <Card className="h-full transition-shadow group-hover:shadow-[inset_0_0_0_1px_var(--accent-700)]">
                <CardContent className="flex items-start gap-3 pt-4">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--neutral-900)]">
                    <MessageSquare className="size-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-foreground">
                      {session.title || "Untitled session"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {formatDateTime(session.created_at)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
