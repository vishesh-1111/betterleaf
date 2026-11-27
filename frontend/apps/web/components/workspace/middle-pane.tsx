"use client";

import { useState, type KeyboardEvent } from "react";
import { CheckIcon, LoaderIcon, SparklesIcon } from "lucide-react";
import { LatexEditor } from "./editor/latex-editor";
import { ResumeEditor } from "./resume-editor/resume-editor";
import { ReviewPanel } from "./review/review-panel";
import { useDocumentStore } from "@/stores/document-store";
import { requestIdForFile, useTailorStore } from "@/stores/tailor-store";
import { hasResumeData } from "@/lib/resume-data";
import "@/styles/resume-editor.css";

type Tab = "edit" | "latex" | "review";

/** Flip to true to bring the raw LaTeX tab back. */
const SHOW_LATEX_TAB = false;

const TABS: { id: Tab; label: string }[] = [
  { id: "edit", label: "Edit" },
  ...(SHOW_LATEX_TAB ? [{ id: "latex" as const, label: "LaTeX" }] : []),
  { id: "review", label: "Review" },
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
  const tailorStatus = useTailorStore((s) => {
    const file = useDocumentStore.getState().files.find((f) => f.id === fileId);
    const id = requestIdForFile(s.viewing, file);
    return id ? s.requests[id]?.status : undefined;
  });

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
  } else if (tailorStatus === "analysing" || tailorStatus === "drafting") {
    body = (
      <>
        <LoaderIcon className="size-3.5 re-spin" aria-hidden="true" />
        {tailorStatus === "analysing" ? "Analysing job…" : "Drafting bullets…"}
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
  // How many AI proposals / gap questions are waiting on the user.
  const pending = useTailorStore((s) => {
    const file = activeFile;
    const id = requestIdForFile(s.viewing, file);
    const dto = id ? s.requests[id] : undefined;
    if (!dto || dto.status !== "ready") return 0;
    return dto.proposals?.length || dto.gap_questions?.length || 0;
  });

  // Images (and anything that is not a resume) go straight to the old editor.
  if (!activeFile || activeFile.type !== "tex" || !activeFile.resumeId) {
    return <LatexEditor />;
  }

  // A tailored resume opens on its report; an original one on the form.
  const tab: Tab =
    chosen[activeFile.id] ??
    (activeFile.tailorRequestId
      ? "review"
      : hasResumeData(activeFile.structuredData)
        ? "edit"
        : SHOW_LATEX_TAB
          ? "latex"
          : "edit");
  const select = (next: Tab) =>
    setChosen((prev) => ({ ...prev, [activeFile.id]: next }));

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const at = TABS.findIndex((t) => t.id === tab);
    const step = e.key === "ArrowRight" ? 1 : -1;
    const next = TABS[(at + step + TABS.length) % TABS.length].id;
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
          {TABS.map(({ id, label }) => {
            const common = {
              id: `re-tab-${id}`,
              type: "button" as const,
              role: "tab",
              "aria-selected": tab === id,
              "aria-controls": "re-panel",
              tabIndex: tab === id ? 0 : -1,
              onClick: () => select(id),
            };
            if (id !== "review") {
              return (
                <button key={id} {...common} className="re-tab">
                  {label}
                </button>
              );
            }
            const text = pending > 0 ? "Review" : "Tailor";
            const state = pending > 0 ? "pending" : "idle";
            return (
              <button
                key={id}
                {...common}
                className="re-tab re-tab-action"
                data-state={state}
              >
                <SparklesIcon className="size-3.5" aria-hidden="true" />
                {text}
                {pending > 0 && (
                  <>
                    <span className="re-tab-count" aria-hidden="true">
                      {pending}
                    </span>
                    <span className="sr-only">{`${pending} pending`}</span>
                  </>
                )}
              </button>
            );
          })}
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
        ) : tab === "review" ? (
          <ReviewPanel key={activeFile.id} fileId={activeFile.id} />
        ) : (
          <LatexEditor />
        )}
      </div>
    </div>
  );
}
