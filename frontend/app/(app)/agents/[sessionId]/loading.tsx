import { Skeleton } from "@/components/ui/skeleton";

export default function AgentSessionLoading() {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="space-y-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <Skeleton className="h-[calc(100dvh-11rem)] w-full rounded-xl" />
    </div>
  );
}
