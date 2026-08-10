import { PackageSearch } from "lucide-react";

import { EmptyState } from "@/components/data/empty-state";

export default function PortfolioNotFound() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
      <EmptyState
        icon={PackageSearch}
        title="Portfolio not found"
        description="It may have been deleted, or you may not have access to it."
        actionLabel="Back to portfolios"
        actionHref="/portfolio"
      />
    </div>
  );
}
