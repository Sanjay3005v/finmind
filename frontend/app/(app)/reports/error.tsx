"use client";

import { ErrorState } from "@/components/data/error-state";

export default function ReportsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
      <ErrorState error={error} reset={reset} title="Couldn't load reports" />
    </div>
  );
}
