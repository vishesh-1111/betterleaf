"use client";

import { useMemo } from "react";
import { BriefcaseIcon, FileTextIcon, StarIcon } from "lucide-react";
import { useDocumentStore, type ProjectFile } from "@/stores/document-store";
import { useTailorStore } from "@/stores/tailor-store";
import { cn } from "@/lib/utils";
import packageJson from "@/package.json";

interface JobGroup {
  jobId: string;
  label: string;
  /** Oldest first, so version numbers stay stable. */
  versions: ProjectFile[];
}

function byCreated(a: ProjectFile, b: ProjectFile) {
  return (a.createdAt ?? "").localeCompare(b.createdAt ?? "");
}

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex h-9 items-center gap-2 border-sidebar-border border-b px-3">
      {icon}
      <span className="font-medium text-xs">{title}</span>
    </div>
  );
}

export function Sidebar() {
  const files = useDocumentStore((s) => s.files);
  const master = useDocumentStore((s) => s.master);
  const activeFileId = useDocumentStore((s) => s.activeFileId);
  const setActiveFile = useDocumentStore((s) => s.setActiveFile);
  const jobTitles = useTailorStore((s) => s.jobTitles);

  const { base, jobs } = useMemo(() => {
    const tex = files.filter((f) => f.type === "tex");
    const base = tex.filter((f) => !f.tailorRequestId).sort(byCreated);
    const groups = new Map<string, JobGroup>();
    for (const f of tex.filter((f) => f.tailorRequestId)) {
      const jobId = f.jobId ?? f.tailorRequestId!;
      const group = groups.get(jobId) ?? {
        jobId,
        label:
          jobTitles[jobId] ||
          (f.tailorRequestId && jobTitles[f.tailorRequestId]) ||
          f.jobLabel ||
          "Job application",
        versions: [],
      };
      group.versions.push(f);
      groups.set(jobId, group);
    }
    const jobs = [...groups.values()];
    for (const g of jobs) g.versions.sort(byCreated);
    // Most recently created job first.
    jobs.sort((a, b) =>
      (b.versions[0].createdAt ?? "").localeCompare(a.versions[0].createdAt ?? ""),
    );
    return { base, jobs };
  }, [files, jobTitles]);

  const row = (file: ProjectFile, label: string) => (
    <button
      key={file.id}
      className={cn(
        "file-row",
        file.id === activeFileId ? "active" : "hover:bg-muted/60",
      )}
      onClick={() => setActiveFile(file.id)}
    >
      <FileTextIcon className="size-4 shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );

  return (
    <div className="sidebar flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <SectionHeader
          icon={<StarIcon className="size-4 text-muted-foreground" />}
          title="Master Resume"
        />
        <div className="space-y-1 p-2">
          {master ? (
            <div
              className="file-row cursor-default"
              title="Editing the master resume is coming soon"
            >
              <StarIcon className="size-4 shrink-0" />
              <span className="truncate">{master.title}</span>
              <span className="ml-auto shrink-0 text-muted-foreground text-[10px]">
                Soon
              </span>
            </div>
          ) : (
            <div className="px-2 py-1 text-muted-foreground text-xs">
              No master resume yet
            </div>
          )}
          <div className="px-2 text-muted-foreground text-[11px]">
            Editing the master resume is coming soon.
          </div>
        </div>

        <SectionHeader
          icon={<FileTextIcon className="size-4 text-muted-foreground" />}
          title="Base Resume"
        />
        <div className="space-y-1 p-2">
          {base.length > 0 ? (
            base.map((f) => row(f, f.name.replace(/\.tex$/, "")))
          ) : (
            <div className="px-2 py-1 text-muted-foreground text-xs">
              Upload a resume to get started
            </div>
          )}
        </div>

        <SectionHeader
          icon={<BriefcaseIcon className="size-4 text-muted-foreground" />}
          title="Job Applications"
        />
        <div className="space-y-3 p-2">
          {jobs.length > 0 ? (
            jobs.map((g) => (
              <div key={g.jobId} className="space-y-1">
                <div
                  className="truncate px-2 font-medium text-xs"
                  title={g.label}
                >
                  {g.label}
                </div>
                {g.versions.map((f, i) =>
                  row(f, g.versions.length > 1 ? `Version ${i + 1}` : "Tailored resume"),
                )}
              </div>
            ))
          ) : (
            <div className="px-2 py-1 text-muted-foreground text-xs">
              Tailored resumes appear here, one group per job
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between border-sidebar-border border-t px-3 py-2 text-muted-foreground text-xs">
        <span>Betterleaf v{packageJson.version}</span>
      </div>
    </div>
  );
}
