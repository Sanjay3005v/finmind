import { Skeleton } from "@/components/ui/skeleton";

export default function PortfolioDetailLoading() {
  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-8 w-40" />
      </div>
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
