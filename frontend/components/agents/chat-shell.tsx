"use client";

import * as React from "react";
import { Bot, Loader2, SendHorizonal, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/data/empty-state";
import { MessageBubble } from "@/components/agents/message-bubble";
import { TradeApprovalInline } from "@/components/agents/trade-approval-inline";
import { ApiError, getAgentMessages, streamAgentMessage } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import type { AgentMessage, AgentToolCall, ResearchCitation } from "@/lib/api/types";

interface ChatShellProps {
  sessionId: string;
  initialMessages: AgentMessage[];
}

const SUGGESTED_PROMPTS = [
  "How is my portfolio allocated right now?",
  "What's my current risk exposure?",
  "Summarize my recent performance",
];

export function ChatShell({ sessionId, initialMessages }: ChatShellProps) {
  const [messages, setMessages] = React.useState<AgentMessage[]>(initialMessages);
  const [input, setInput] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [sourcesOpen, setSourcesOpen] = React.useState(false);
  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // The backend never persists `trade_approval_id` on the message row itself
  // (only on `trade_approvals`) — this ref remembers the most recent one for
  // the life of this session so `refreshMessages` can reattach it to the
  // newest assistant message on every refetch, including the one that runs
  // right after a decision. It does not survive a page reload — a still-
  // pending approval remains independently visible on /trade-approvals.
  const lastTradeApprovalIdRef = React.useRef<string | null>(null);
  const localIdCounterRef = React.useRef(0);

  const refreshMessages = React.useCallback(async () => {
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const latest = await getAgentMessages(data.session?.access_token ?? null, sessionId);
      if (lastTradeApprovalIdRef.current) {
        for (let i = latest.length - 1; i >= 0; i--) {
          if (latest[i].role === "assistant") {
            latest[i] = { ...latest[i], trade_approval_id: lastTradeApprovalIdRef.current };
            break;
          }
        }
      }
      setMessages(latest);
    } catch {
      // A background refresh failing (e.g. after a trade decision) isn't
      // worth surfacing as an error toast — the chat just won't show the
      // agent's follow-up acknowledgment until the next successful fetch.
    }
  }, [sessionId]);

  async function sendContent(content: string) {
    if (!content || sending) return;

    const userMessageId = `local-user-${localIdCounterRef.current++}`;
    const assistantMessageId = `local-assistant-${localIdCounterRef.current++}`;
    setMessages((prev) => [
      ...prev,
      { id: userMessageId, role: "user", content, created_at: new Date().toISOString() },
      { id: assistantMessageId, role: "assistant", content: "", created_at: new Date().toISOString() },
    ]);
    setInput("");
    setSending(true);

    const toolCalls: AgentToolCall[] = [];

    function updateAssistant(patch: Partial<AgentMessage> | ((m: AgentMessage) => AgentMessage)) {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantMessageId) return m;
          return typeof patch === "function" ? patch(m) : { ...m, ...patch };
        })
      );
    }

    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const accessToken = data.session?.access_token ?? null;

      await streamAgentMessage(accessToken, sessionId, content, (evt) => {
        switch (evt.event) {
          case "token": {
            const text = typeof evt.data.text === "string" ? evt.data.text : "";
            updateAssistant((m) => ({ ...m, content: m.content + text }));
            break;
          }
          case "tool_call": {
            toolCalls.push({
              name: String(evt.data.name ?? ""),
              args: (evt.data.args as Record<string, unknown>) ?? {},
              result: evt.data.result,
            });
            updateAssistant({ tool_calls: [...toolCalls] });
            break;
          }
          case "citation": {
            updateAssistant((m) => ({
              ...m,
              citations: [
                ...(m.citations ?? []),
                {
                  chunk_id: String(evt.data.chunk_id ?? ""),
                  document_title: String(evt.data.document_title ?? ""),
                  snippet: String(evt.data.snippet ?? ""),
                },
              ],
            }));
            break;
          }
          case "interrupt": {
            const id = evt.data.trade_approval_id ? String(evt.data.trade_approval_id) : null;
            lastTradeApprovalIdRef.current = id;
            updateAssistant((m) => ({ ...m, trade_approval_id: id }));
            break;
          }
          case "done":
            // The interrupt path never streams `token` events for its
            // acknowledgment text (only `interrupt` + `done`) — refetch so
            // the message shows the backend's actual persisted content
            // rather than staying blank, and so every turn ends reconciled
            // with the authoritative record rather than the local accumulation.
            void refreshMessages();
            break;
        }
      });
    } catch (err) {
      updateAssistant((m) => ({
        ...m,
        content: m.content || "I couldn't complete that — please try again.",
      }));
      toast.error(
        err instanceof ApiError
          ? err.message
          : "Could not reach FINMIND right now. Your message wasn't sent."
      );
    } finally {
      setSending(false);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    await sendContent(input.trim());
  }

  const sources = React.useMemo(() => {
    const seen = new Map<string, ResearchCitation>();
    for (const message of messages) {
      for (const citation of message.citations ?? []) {
        if (!seen.has(citation.chunk_id)) seen.set(citation.chunk_id, citation);
      }
    }
    return Array.from(seen.values());
  }, [messages]);

  return (
    <div className="flex min-h-0 flex-1 gap-4">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-card shadow-[inset_0_0_0_1px_var(--border)]">
        <div className="flex h-12 shrink-0 items-center gap-2.5 px-4 shadow-[inset_0_-1px_0_0_var(--border)]">
          <span className="size-1.5 rounded-full bg-gain" />
          <span className="text-[13px] text-foreground">Live session</span>
          <div className="flex-1" />
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
            onClick={() => setSourcesOpen((v) => !v)}
          >
            {sourcesOpen ? "Hide sources" : "Show sources"}
          </Button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="Start the conversation"
              description="Ask about your portfolio's performance, a filing, or risk. Every numeric claim is backed by a deterministic tool call and every fact carries a citation."
              className="h-full justify-center border-none"
            />
          ) : (
            messages.map((message) => (
              <div key={message.id} className="space-y-2">
                <MessageBubble message={message} onCitationClick={() => setSourcesOpen(true)} />
                {message.trade_approval_id && (
                  <div className="ml-10">
                    <TradeApprovalInline
                      tradeApprovalId={message.trade_approval_id}
                      onDecided={refreshMessages}
                    />
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <div className="shrink-0 p-3 shadow-[inset_0_1px_0_0_var(--border)]">
          <div className="mb-2.5 flex flex-wrap gap-1.5">
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => sendContent(prompt)}
                disabled={sending}
                className="rounded-full border border-border bg-[color-mix(in_srgb,var(--foreground)_3%,transparent)] px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
              >
                {prompt}
              </button>
            ))}
          </div>
          <form onSubmit={handleSend} className="flex items-end gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend(e);
                }
              }}
              placeholder="Ask FINMIND about your portfolio…"
              rows={1}
              className="min-h-10 flex-1 resize-none"
            />
            <Button
              type="submit"
              size="icon"
              disabled={sending || !input.trim()}
              aria-label="Send message"
              className="bg-[var(--accent-400)] text-background hover:bg-[var(--accent-300)]"
            >
              {sending ? <Loader2 className="size-4 animate-spin" /> : <SendHorizonal className="size-4" />}
            </Button>
          </form>
        </div>
      </div>

      {sourcesOpen && (
        <div className="flex w-[300px] shrink-0 flex-col overflow-hidden rounded-xl bg-card shadow-[inset_0_0_0_1px_var(--border)]">
          <div className="flex h-12 shrink-0 items-center justify-between px-3.5 shadow-[inset_0_-1px_0_0_var(--border)]">
            <span className="text-[12px] tracking-[0.08em] text-primary uppercase">Sources</span>
            <button
              type="button"
              onClick={() => setSourcesOpen(false)}
              className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
              aria-label="Close sources"
            >
              <X className="size-3.5" />
            </button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-3.5">
            {sources.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">
                Citations from the conversation will appear here.
              </p>
            ) : (
              sources.map((source, index) => (
                <div
                  key={source.chunk_id}
                  className="rounded-lg bg-background p-3 shadow-[inset_0_0_0_1px_var(--border)]"
                >
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className="rounded-md bg-[var(--accent-800)] px-1.5 py-0.5 text-[10px] text-[var(--accent-200)]">
                      {index + 1}
                    </span>
                    <span className="truncate text-[11px] text-foreground">{source.document_title}</span>
                  </div>
                  <p className="text-[11px] leading-[1.6] text-muted-foreground">{source.snippet}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
