import type { Metadata } from "next";
import { FileSearch, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/data/empty-state";
import { ResearchSearch } from "@/components/research/research-search";
import { UploadDocumentDialog } from "@/components/research/upload-document-dialog";
import { getAccessToken } from "@/lib/supabase/server";
import { listDocuments } from "@/lib/api/client";
import type { DocumentSourceType, DocumentStatus } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Research" };

const STATUS_STYLE: Record<DocumentStatus, string> = {
  ready: "border-gain/30 bg-gain/10 text-gain",
  processing: "border-primary/30 bg-primary/10 text-primary",
  pending: "border-border bg-white/5 text-muted-foreground",
  failed: "border-loss/30 bg-loss/10 text-loss",
};

const SOURCE_LABEL: Record<DocumentSourceType, string> = {
  filing: "Filing",
  report: "Report",
  news: "News",
  manual_upload: "Upload",
};

export default async function ResearchPage() {
  const accessToken = await getAccessToken();
  const documents = await listDocuments(accessToken);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-medium tracking-[-0.02em] text-foreground">Research</h1>
        <p className="text-sm text-muted-foreground">
          Ask a cited question, or browse the document library the agents retrieve from.
        </p>
      </div>

      <ResearchSearch />

      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Document library
        </h2>
        {documents.length > 0 && <UploadDocumentDialog />}
      </div>

      {documents.length === 0 ? (
        <EmptyState
          icon={FileSearch}
          title="Upload your first research document"
          description="Upload broker statements, filings, or research PDFs so the Research Agent can cite them in answers."
          action={<UploadDocumentDialog />}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc, index) => (
            <Card
              key={doc.id}
              className="animate-in fade-in slide-in-from-bottom-2"
              style={{ animationDelay: `${index * 40}ms` }}
            >
              <CardContent className="flex items-start gap-3 pt-4">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--neutral-900)]">
                  <FileText className="size-4 text-[var(--neutral-500)]" aria-hidden />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-foreground">{doc.title}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {SOURCE_LABEL[doc.source_type]} · {formatDate(doc.uploaded_at)}
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className={cn("shrink-0 capitalize", STATUS_STYLE[doc.status])}
                >
                  {doc.status}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
