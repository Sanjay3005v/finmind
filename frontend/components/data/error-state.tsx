"use client";

import { AlertTriangle, RotateCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";

interface ErrorStateProps {
  error: Error;
  reset?: () => void;
  title?: string;
}

/**
 * Standard "something went wrong" affordance used by every route-level
 * error.tsx boundary: an Alert with a human-readable message plus a retry
 * button. Never a bare spinner or blank div.
 */
export function ErrorState({ error, reset, title = "Something went wrong" }: ErrorStateProps) {
  const message =
    error instanceof ApiError
      ? error.message
      : error.message || "An unexpected error occurred. Please try again.";
  const requestId = error instanceof ApiError ? error.requestId : undefined;

  return (
    <Alert variant="destructive" className="max-w-xl">
      <AlertTriangle className="size-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {requestId ? (
          <p className="mt-1 font-mono text-xs opacity-70">Request ID: {requestId}</p>
        ) : null}
        {reset ? (
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={reset}
          >
            <RotateCw className="size-3.5" />
            Try again
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
