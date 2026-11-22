"use client";

import { useState, type KeyboardEvent } from "react";
import { CheckIcon, LoaderIcon } from "lucide-react";
import { LatexEditor } from "./editor/latex-editor";
import { ResumeEditor } from "./resume-editor/resume-editor";
import { useDocumentStore } from "@/stores/document-store";
import { hasResumeData } from "@/lib/resume-data";
import "@/styles/resume-editor.css";

type Tab = "edit" | "latex";

const TABS: { id: Tab; label: string }[] = [
  { id: "edit", label: "Edit" },
  { id: "latex", label: "LaTeX" },
];

function SaveStatus({ fileId }: { fileId: string }) {
  const status = useDocumentStore(
    (s) => s.files.find((f) => f.id === fileId)?.dataStatus ?? "idle",
  );
  const error = useDocumentStore(
    (s) => s.files.find((f) => f.id === fileId)?.dataError,
  );
  const isCompiling = useDocumentStore((s) => s.isCompiling);
  const retry = useDocumentStore((s) => s.retryDraftSave);

  let body = null;
  if (status === "error") {
    body = (
      <>
        <span className="re-status-dot is-error" aria-hidden="true" />
        <span title={error}>Couldn&apos;t save</span>
        <button
          type="button"
          className="re-status-retry"
          onClick={() => retry(fileId)}
        >
          Retry
        </button>
      </>
    );
  } else if (status === "dirty" || status === "saving") {
    body = (
      <>
        <LoaderIcon className="size-3.5 re-spin" aria-hidden="true" />
        Saving…
      </>
    );
  } else if (isCompiling) {
    body = (
      <>
        <LoaderIcon className="size-3.5 re-spin" aria-hidden="true" />
        Building PDF…
      </>
    );
  } else if (status === "saved") {
    body = (
      <>
        <CheckIcon className="size-3.5" aria-hidden="true" />
        Saved
      </>
    );
  }

  return (
    <div className="re-status" role="status" aria-live="polite">
      {body}
    </div>
  );
}

export function MiddlePane() {
  const activeFile = useDocumentStore((s) =>
    s.files.find((f) => f.id === s.activeFileId),
  );
  const [chosen, setChosen] = useState<Record<string, Tab>>({});

  // Images (and anything that is not a resume) go straight to the old editor.
  if (!activeFile || activeFile.type !== "tex" || !activeFile.resumeId) {
    return <LatexEditor />;
  }

  const tab: Tab =
    chosen[activeFile.id] ??
    (hasResumeData(activeFile.structuredData) ? "edit" : "latex");
  const select = (next: Tab) =>
    setChosen((prev) => ({ ...prev, [activeFile.id]: next }));

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const next = tab === "edit" ? "latex" : "edit";
    select(next);
    document.getElementById(`re-tab-${next}`)?.focus();
  };

  return (
    <div className="re-pane">
      <div className="re-tabbar">
        <div
          className="re-tabs"
          role="tablist"
          aria-label="Resume views"
          onKeyDown={onKeyDown}
        >
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              id={`re-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={tab === id}
              aria-controls="re-panel"
              tabIndex={tab === id ? 0 : -1}
              className="re-tab"
              onClick={() => select(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <SaveStatus fileId={activeFile.id} />
      </div>
      <div
        id="re-panel"
        role="tabpanel"
        aria-labelledby={`re-tab-${tab}`}
        className="re-panel"
      >
        {tab === "edit" ? (
          <ResumeEditor key={activeFile.id} fileId={activeFile.id} />
        ) : (
          <LatexEditor />
        )}
      </div>
    </div>
  );
}
