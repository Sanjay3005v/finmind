import type { Metadata } from "next";
import { FileText } from "lucide-react";

import { EmptyState } from "@/components/data/empty-state";
import { ReportsPanel } from "@/components/reports/reports-panel";
import { getAccessToken } from "@/lib/supabase/server";
import { listPortfolios } from "@/lib/api/client";

export const metadata: Metadata = { title: "Reports" };

export default async function ReportsPage() {
  const accessToken = await getAccessToken();
  const portfolios = await listPortfolios(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Generate an on-demand performance, risk, and allocation report.
        </p>
      </div>

      {portfolios.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Create a portfolio first"
          description="Reports are generated per portfolio. Add a portfolio to unlock report generation."
          actionLabel="Create your first portfolio"
          actionHref="/portfolio"
        />
      ) : (
        <ReportsPanel portfolios={portfolios} />
      )}
    </div>
  );
}
