"use client";

import Link from "next/link";
import { MessageSquare } from "lucide-react";

import { NewSessionButton } from "@/components/agents/new-session-button";
import { formatDateTime } from "@/lib/format";
import type { AgentSession } from "@/lib/api/types";

interface SessionRailProps {
  sessions: AgentSession[];
  activeSessionId: string;
}

export function SessionRail({ sessions, activeSessionId }: SessionRailProps) {
  return (
    <div className="flex w-[220px] shrink-0 flex-col gap-2.5">
      <NewSessionButton className="w-full" />
      <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {sessions.map((session) => {
          const active = session.id === activeSessionId;
          return (
            <Link
              key={session.id}
              href={`/agents/${session.id}`}
              className={
                "rounded-[7px] px-2.5 py-2 transition-colors " +
                (active
                  ? "bg-[var(--accent-900)] shadow-[inset_0_0_0_1px_var(--accent-800)]"
                  : "hover:bg-[color-mix(in_srgb,var(--foreground)_5%,transparent)]")
              }
            >
              <div className="flex items-center gap-1.5 truncate text-[12px] text-foreground">
                <MessageSquare className="size-3 shrink-0 text-muted-foreground" />
                <span className="truncate">{session.title || "Untitled session"}</span>
              </div>
              <div className="mt-0.5 text-[10px] text-muted-foreground">
                {formatDateTime(session.created_at)}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
