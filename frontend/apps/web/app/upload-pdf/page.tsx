"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon, FileUpIcon, LoaderIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { uploadPdf } from "@/lib/api";

export default function UploadPdfPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = (selected: File | null) => {
    setError(null);
    setFile(selected);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadPdf(file);
      // The backend set the workspace cookie + created the resume. Head to the
      // studio, which will load the newly created resume from the workspace.
      router.replace("/workspace");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Upload failed. Please try again.",
      );
      setUploading(false);
    }
  };

  return (
    <main className="flex h-full items-center justify-center p-6">
      <div className="flex w-full max-w-md flex-col gap-6">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit -ml-2"
          onClick={() => router.back()}
        >
          <ArrowLeftIcon />
          Back
        </Button>

        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Upload your resume
          </h1>
          <p className="text-sm text-muted-foreground">
            Drop a PDF — we&apos;ll extract the content and build a LaTeX resume
            from it.
          </p>
        </div>

        <label
          htmlFor="resume-upload"
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center transition-colors hover:bg-muted/60"
        >
          <FileUpIcon className="size-8 text-muted-foreground" />
          <span className="text-sm font-medium">
            {file ? file.name : "Click to choose a PDF"}
          </span>
          <span className="text-xs text-muted-foreground">
            Only PDF files are supported.
          </span>
          <input
            ref={inputRef}
            id="resume-upload"
            type="file"
            accept="application/pdf"
            className="sr-only"
            onChange={(e) => handleSelect(e.target.files?.[0] ?? null)}
          />
        </label>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button
          size="lg"
          className="w-full"
          disabled={!file || uploading}
          onClick={handleUpload}
        >
          {uploading ? (
            <>
              <LoaderIcon className="size-4 animate-spin" />
              Converting…
            </>
          ) : (
            "Upload & convert"
          )}
        </Button>
      </div>
    </main>
  );
}
