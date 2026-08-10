"use client";

import { ErrorState } from "@/components/data/error-state";

export default function BrokersError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Brokers</h1>
      <ErrorState error={error} reset={reset} title="Couldn't load broker connections" />
    </div>
  );
}
