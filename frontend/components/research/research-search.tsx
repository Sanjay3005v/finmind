"use client";

import * as React from "react";
import { FileSearch, Loader2, Search } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/data/empty-state";
import { Input } from "@/components/ui/input";
import { ApiError, queryResearch } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";
import type { ResearchQueryResponse } from "@/lib/api/types";

// Canned example prompts — just UI affordances that call the same real
// queryResearch() search function with fixed text, not fabricated data.
const SUGGESTED_QUERIES = [
  "What are the key risks mentioned in my documents?",
  "Summarize the most recent filing.",
  "What does the research say about valuation?",
];

export function ResearchSearch() {
  const [query, setQuery] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<ResearchQueryResponse | null>(null);

  async function runQuery(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const response = await queryResearch(data.session?.access_token ?? null, trimmed);
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run that query. Please try again.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void runQuery(query);
  }

  function handleSuggestion(suggestion: string) {
    setQuery(suggestion);
    void runQuery(suggestion);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-xl bg-gradient-to-br from-[var(--accent-900)] to-background p-5 shadow-[inset_0_0_0_1px_var(--accent-800)]">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your research library…"
            aria-label="Research query"
            className="h-[42px]"
          />
          <Button
            type="submit"
            variant="accent-outline"
            className="h-[42px]"
            disabled={loading || !query.trim()}
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            Search
          </Button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTED_QUERIES.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => handleSuggestion(suggestion)}
              disabled={loading}
              className="rounded-full border border-border bg-white/5 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary disabled:pointer-events-none disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="flex flex-col gap-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground tabular-nums">
            {result.citations.length} {result.citations.length === 1 ? "citation" : "citations"}
          </p>

          <Card className={cn("animate-in fade-in slide-in-from-bottom-2")}>
            <CardContent className="pt-4">
              <p className="text-[13px] leading-[1.65] text-foreground">{result.answer}</p>
            </CardContent>
          </Card>

          {result.citations.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {result.citations.map((citation, index) => (
                <Card
                  key={citation.chunk_id}
                  className="animate-in fade-in slide-in-from-bottom-2"
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <CardContent className="space-y-1.5 pt-4">
                    <p className="text-[13px] font-medium text-foreground">
                      <span className="text-primary">[{index + 1}]</span> {citation.document_title}
                    </p>
                    <p className="text-[13px] leading-[1.65] text-muted-foreground">{citation.snippet}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={FileSearch}
              title="No citations for this answer"
              description="The Research Agent answered without pointing to a specific passage in your library."
            />
          )}
        </div>
      )}
    </div>
  );
}
