"use client";

import * as React from "react";
import { Download, FileText, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/data/empty-state";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, generateReport, getReportJob } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Portfolio, ReportJob, ReportJobStatus } from "@/lib/api/types";

const STATUS_LABEL: Record<ReportJobStatus, string> = {
  queued: "Queued",
  running: "Running",
  ready: "Ready",
  error: "Error",
};

const STATUS_CHIP_CLASS: Record<ReportJobStatus, string> = {
  queued: "bg-[var(--neutral-900)] text-[var(--neutral-400)]",
  running: "bg-[var(--neutral-900)] text-[var(--neutral-400)]",
  ready: "bg-gain/15 text-gain",
  error: "bg-loss/15 text-loss",
};

// The report-job schema has no per-step progress field yet — job status is
// just queued/running/ready/error (see lib/api/types.ts's ReportJob). Rather
// than fabricate step labels, in-flight jobs get a generic indeterminate bar.
const IN_FLIGHT: ReportJobStatus[] = ["queued", "running"];

// Local-only display field: the portfolio name is known at generation time
// (it's whichever option was selected in the dropdown below), so it's
// attached to the job client-side for a friendlier row title. Never sent to
// or read from the API.
type DisplayReportJob = ReportJob & { portfolioName?: string };

export function ReportsPanel({ portfolios }: { portfolios: Portfolio[] }) {
  const [portfolioId, setPortfolioId] = React.useState(portfolios[0]?.id ?? "");
  const [generating, setGenerating] = React.useState(false);
  const [refreshingId, setRefreshingId] = React.useState<string | null>(null);
  const [jobs, setJobs] = React.useState<DisplayReportJob[]>([]);

  async function handleGenerate() {
    if (!portfolioId) return;
    setGenerating(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const job = await generateReport(data.session?.access_token ?? null, portfolioId);
      const portfolioName = portfolios.find((p) => p.id === portfolioId)?.name;
      setJobs((prev) => [{ ...job, portfolioName }, ...prev]);
      toast.success("Report generation queued.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not queue the report.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleRefresh(jobId: string) {
    setRefreshingId(jobId);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      const job = await getReportJob(data.session?.access_token ?? null, jobId);
      setJobs((prev) => prev.map((j) => (j.job_id === jobId ? { ...job, portfolioName: j.portfolioName } : j)));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not refresh that job's status.");
    } finally {
      setRefreshingId(null);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
      <Card className="self-start">
        <CardHeader>
          <CardTitle>Generate a report</CardTitle>
          <CardDescription>Pick a portfolio and run an on-demand report.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="report-portfolio">Portfolio</Label>
            <Select value={portfolioId} onValueChange={setPortfolioId}>
              <SelectTrigger id="report-portfolio" className="w-full">
                <SelectValue placeholder="Select a portfolio" />
              </SelectTrigger>
              <SelectContent>
                {portfolios.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={handleGenerate}
            disabled={generating || !portfolioId}
            variant="accent-outline"
            className="w-full"
          >
            {generating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {generating ? "Generating…" : "Generate"}
          </Button>
        </CardContent>
      </Card>

      {jobs.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No reports yet"
          description="Generate a performance + risk + allocation report for a portfolio. Report jobs run in the background and can take a moment to complete."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Generated reports</CardTitle>
            <CardDescription>
              Report jobs run in the background and can take a moment to complete.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 shadow-[inset_0_0_0_1px_var(--border)]"
              >
                <div className="flex items-center gap-2.5">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--neutral-900)]">
                    <FileText className="size-4.5 text-[var(--neutral-500)]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {job.portfolioName ?? "Report"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      Queued {formatDateTime(job.created_at)} ·{" "}
                      <span className="font-mono">{job.job_id}</span>
                    </p>
                    {IN_FLIGHT.includes(job.status) && (
                      <div className="mt-1.5 h-1 w-40 overflow-hidden rounded-full bg-[var(--neutral-900)]">
                        <div className="h-full w-2/5 animate-pulse rounded-full bg-gradient-to-r from-[var(--accent-600)] to-[var(--accent-300)]" />
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                      STATUS_CHIP_CLASS[job.status]
                    )}
                  >
                    {STATUS_LABEL[job.status]}
                  </span>
                  {job.status === "ready" && job.download_url ? (
                    <Button asChild size="sm" variant="outline">
                      <a href={job.download_url} target="_blank" rel="noreferrer">
                        <Download className="size-3.5" />
                        Download
                      </a>
                    </Button>
                  ) : job.status !== "error" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={refreshingId === job.job_id}
                      onClick={() => handleRefresh(job.job_id)}
                    >
                      {refreshingId === job.job_id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3.5" />
                      )}
                      Refresh
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
