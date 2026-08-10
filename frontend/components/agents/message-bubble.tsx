import { CheckCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";
import type { AgentMessage } from "@/lib/api/types";

const TOOL_LABELS: Record<string, string> = {
  get_holdings_summary: "Checked your holdings",
  compute_performance: "Computed performance",
  compute_risk_metrics: "Computed risk metrics",
  compute_allocation_breakdown: "Checked your allocation",
  research_lookup: "Searched your research library",
  // Synthetic names the graph substitutes on a tool failure (see
  // app/agents/graph.py's `except AgentToolError` branches) rather than the
  // real per-tool name, since no individual tool actually returned data.
  portfolio_tools: "Tried to check your portfolio",
  risk_tools: "Tried to compute risk metrics",
};

interface MessageBubbleProps {
  message: AgentMessage;
  onCitationClick?: () => void;
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-medium",
          isUser ? "bg-[var(--neutral-900)] text-[var(--neutral-400)]" : "bg-[var(--accent-800)] text-[var(--accent-100)]"
        )}
      >
        {isUser ? "Me" : "AI"}
      </div>
      <div className={cn("flex max-w-[78%] flex-col gap-1.5", isUser && "items-end")}>
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.tool_calls.map((call, index) => (
              <span
                key={`${call.name}-${index}`}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--neutral-900)] px-2.5 py-1 text-[11px] text-[var(--neutral-400)] shadow-[inset_0_0_0_1px_var(--accent-800)]"
              >
                <span className="size-1.5 rounded-full bg-gain" />
                <CheckCircle2 className="size-3" />
                {TOOL_LABELS[call.name] ?? call.name}
              </span>
            ))}
          </div>
        )}
        <div
          className={cn(
            "px-4 py-2.5 text-[13px] leading-[1.75] whitespace-pre-wrap",
            isUser
              ? "rounded-[12px_12px_3px_12px] bg-[var(--accent-900)] text-foreground"
              : "rounded-[12px_12px_12px_3px] bg-background text-foreground shadow-[inset_0_0_0_1px_var(--border)]"
          )}
        >
          {message.content}
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.citations.map((citation, index) => (
              <button
                key={citation.chunk_id}
                type="button"
                title={citation.snippet}
                onClick={onCitationClick}
                className="rounded-md border border-primary/40 px-2 py-0.5 text-[11px] text-primary transition-colors hover:bg-primary/10"
              >
                [{index + 1}] {citation.document_title}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
