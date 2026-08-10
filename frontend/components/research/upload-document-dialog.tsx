"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Loader2, Upload } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, uploadDocument } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

interface UploadDocumentDialogProps {
  trigger?: React.ReactNode;
}

export function UploadDocumentDialog({ trigger }: UploadDocumentDialogProps) {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [file, setFile] = React.useState<File | null>(null);
  const [title, setTitle] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  function handleFileChange(selected: File | null) {
    setFile(selected);
    if (selected && !title) {
      setTitle(selected.name.replace(/\.[^./]+$/, ""));
    }
  }

  async function handleUpload() {
    if (!file || !title.trim()) return;
    setSubmitting(true);
    try {
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      await uploadDocument(data.session?.access_token ?? null, file, title.trim());
      toast.success(`"${title.trim()}" queued for ingestion.`);
      setFile(null);
      setTitle("");
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not upload the document.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="accent-outline" size="sm">
            <Upload className="size-4" />
            Upload
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload a research document</DialogTitle>
          <DialogDescription>
            PDFs and text files are chunked and embedded so the Research Agent can cite them.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="document-file">File</Label>
          <Input
            id="document-file"
            type="file"
            accept=".pdf,.txt,.md"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="document-title">Title</Label>
          <Input
            id="document-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Q2 broker statement"
          />
        </div>
        <DialogFooter>
          <Button variant="accent-outline" onClick={handleUpload} disabled={!file || !title.trim() || submitting}>
            {submitting && <Loader2 className="size-4 animate-spin" />}
            Upload
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
