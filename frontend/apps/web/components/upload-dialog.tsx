"use client";

import { useEffect, useId, useRef, useState } from "react";
import { LaTeXLine } from "@/components/latex-line";
import type { UploadPhase } from "@/hooks/use-pdf-upload";

/** After this long in a busy phase, reassure the user instead of looking frozen. */
const SLOW_AFTER_MS = 12_000;

/* Decorative only: LaTeX streaming past while the real parse runs. It is all
 * structure and `…` placeholders, so nothing pretends to be the user's content. */
const STREAM = [
  String.raw`\section{Experience}`,
  String.raw`\resumeSubheading`,
  "  {…}{…}",
  "  {…}{…}",
  String.raw`\resumeItemListStart`,
  String.raw`  \resumeItem{…}`,
  String.raw`  \resumeItem{…}`,
  String.raw`  \resumeItem{…}`,
  String.raw`\resumeItemListEnd`,
  String.raw`\section{Education}`,
  String.raw`\resumeSubheading`,
  "  {…}{…}",
  String.raw`\section{Projects}`,
  String.raw`\resumeProjectHeading`,
  String.raw`\section{Technical Skills}`,
];

type RowKind = "name" | "contact" | "head" | "row" | "line";
interface PaperRow {
  kind: RowKind;
  /** Bar width, % of the sheet. */
  w: number;
  /** Gets the sun highlight when the resume is ready. */
  hl?: boolean;
}

/* The sheet that "writes itself": ink bars standing in for a resume. */
const PAPER: PaperRow[] = [
  { kind: "name", w: 46, hl: true },
  { kind: "contact", w: 68 },
  { kind: "head", w: 26 },
  { kind: "row", w: 50 },
  { kind: "line", w: 94, hl: true },
  { kind: "line", w: 88 },
  { kind: "line", w: 62, hl: true },
  { kind: "head", w: 30 },
  { kind: "row", w: 44 },
  { kind: "line", w: 90 },
  { kind: "line", w: 74 },
  { kind: "head", w: 34 },
  { kind: "line", w: 92 },
];

function bar(w: number, i: number, extra = "") {
  return (
    <span
      className={`up-bar${extra}`}
      style={{ "--w": `${w}%`, "--i": i } as React.CSSProperties}
    />
  );
}

const PdfIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M6 2.5h7.5L19 8v12.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-17a1 1 0 0 1 1-1z" />
    <path d="M13.5 2.5V8H19" />
  </svg>
);

interface UploadDialogProps {
  phase: UploadPhase;
  fileName: string;
  /** Message from the failed upload. */
  error: string | null;
  /** Abort the upload and close. */
  onCancel: () => void;
  /** After a failure: close and open the file picker again. */
  onChooseAnother: () => void;
}

/** Modal shown while a resume PDF uploads and is parsed. Native <dialog>, so
 * the page behind is inert, focus is trapped, and Esc cancels. */
export function UploadDialog({
  phase,
  fileName,
  error,
  onCancel,
  onChooseAnother,
}: UploadDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const open = phase !== "idle";
  const busy = phase === "uploading" || phase === "processing";
  const done = phase === "succeeded";
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    setSlow(false);
    if (!busy) return;
    const timer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [busy]);

  let title = "Uploading your resume";
  let caption = "Sending your PDF to Betterleaf.";
  if (phase === "processing") {
    title = "Reading your resume";
    caption = slow
      ? "Still working. Longer resumes take a bit more time."
      : "Turning your PDF into editable LaTeX. This usually takes a few seconds.";
  } else if (done) {
    title = "Your resume is ready";
    caption = "Opening your workspace…";
  } else if (phase === "failed") {
    title = "That didn’t work";
    caption = error ?? "Upload failed. Please try again.";
  }

  return (
    <dialog
      ref={ref}
      className="upload"
      aria-labelledby={titleId}
      aria-busy={busy}
      onCancel={(e) => {
        // Esc: take over from the native close so React state stays the source
        // of truth. Once the resume is ready there is nothing left to cancel.
        e.preventDefault();
        if (!done) onCancel();
      }}
    >
      {open && (
        <div className={`up${done ? "done" : ""}`}>
          <div className="up-head">
            <h2 id={titleId}>{title}</h2>
            <p role="status" aria-live="polite">
              {caption}
            </p>
          </div>

          {phase !== "failed" && (
            <div className="up-stage" aria-hidden="true">
              <div className="up-code">
                <div className="up-window">
                  <div className="up-track">
                    {[0, 1].map((copy) =>
                      STREAM.map((text, i) => (
                        <div className="up-ln" key={`${copy}-${i}`}>
                          <LaTeXLine text={text} />
                        </div>
                      )),
                    )}
                  </div>
                </div>
              </div>
              <div className="up-right">
                <div className="up-paper">
                  {PAPER.map((row, i) => (
                    <div key={i} className={`up-row ${row.kind}`}>
                      {bar(row.w, i, row.hl ? " hl" : "")}
                      {row.kind === "row" && bar(18, i)}
                      {row.kind === "head" && (
                        <span
                          className="up-bar up-rule"
                          style={
                            { "--w": "100%", "--i": i } as React.CSSProperties
                          }
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="up-foot">
            <span className="up-file" title={fileName}>
              <PdfIcon />
              <span>{fileName}</span>
            </span>
            {busy && (
              <button className="btn ghost sm" type="button" onClick={onCancel}>
                Cancel
              </button>
            )}
            {done && <span className="pill ok">Ready</span>}
            {phase === "failed" && (
              <span className="up-actions">
                <button
                  className="btn ghost sm"
                  type="button"
                  onClick={onCancel}
                >
                  Close
                </button>
                <button
                  className="btn sm"
                  type="button"
                  onClick={onChooseAnother}
                >
                  Choose another file
                </button>
              </span>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}
