"use client";

import { ErrorState } from "@/components/data/error-state";

export default function ResearchError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Research</h1>
      <ErrorState error={error} reset={reset} title="Couldn't load your research library" />
    </div>
  );
}
