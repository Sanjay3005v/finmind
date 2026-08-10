"use client";

import { ErrorState } from "@/components/data/error-state";

export default function AgentSessionError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-lg font-semibold tracking-tight">Research session</h1>
      <ErrorState error={error} reset={reset} title="Couldn't load this session" />
    </div>
  );
}
