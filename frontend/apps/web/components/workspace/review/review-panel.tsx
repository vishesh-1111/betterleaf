"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ClipboardPasteIcon, LoaderIcon } from "lucide-react";
import { toast } from "sonner";
import { useDocumentStore } from "@/stores/document-store";
import {
  clearViewing,
  ensureTailorRequest,
  requestIdForFile,
  startTailor,
  trackTailorRequest,
  useTailorStore,
} from "@/stores/tailor-store";
import { hasResumeData } from "@/lib/resume-data";
import { JobDescription, MatchedDetails, Scores } from "./report";
import { GapQuestions } from "./gap-questions";
import { Proposals } from "./proposals";
import "@/styles/review.css";

function firstLine(text: string): string {
  const line = text.split("\n").find((l) => l.trim()) ?? "";
  return line.trim().slice(0, 90);
}

function focusOnMount(el: HTMLTextAreaElement | null) {
  el?.focus();
}

function JobForm({
  fileId,
  onCancel,
}: {
  fileId: string;
  onCancel?: () => void;
}) {
  const text = useTailorStore((s) => s.jobDraft);
  const setText = useTailorStore((s) => s.setJobDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paste = async () => {
    try {
      setText(await navigator.clipboard.readText());
    } catch {
      toast("Couldn't read the clipboard. Paste into the box with Ctrl+V.");
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await startTailor(fileId, text);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  };

  return (
    <section className="rv-section" aria-label="Job description">
      <h2 className="rv-h">Paste a job description</h2>
      <p className="rv-hint">
        We check it against your resume, show what&apos;s covered, and build a
        tailored version from your own words.
      </p>
      <label htmlFor="rv-job" className="rv-sr">
        Job description
      </label>
      <textarea
        id="rv-job"
        className="re-input rv-job"
        ref={focusOnMount}
        value={text}
        placeholder="Paste the full job post here…"
        onChange={(e) => setText(e.target.value)}
      />
      {error && (
        <p className="rv-error" role="alert">
          {error}
        </p>
      )}
      <div className="rv-actions">
        <button
          type="button"
          className="rv-primary"
          disabled={busy || !text.trim()}
          onClick={submit}
        >
          {busy ? (
            <>
              <LoaderIcon className="re-spin size-4" aria-hidden="true" />
              Starting…
            </>
          ) : (
            "Tailor"
          )}
        </button>
        <button
          type="button"
          className="re-pill"
          onClick={paste}
          disabled={busy}
        >
          <ClipboardPasteIcon className="size-3.5" aria-hidden="true" />
          Paste from clipboard
        </button>
        {onCancel && (
          <button type="button" className="rv-link" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </section>
  );
}

function JobBar({
  requestId,
  jobText,
  onChange,
}: {
  requestId: string;
  jobText: string;
  onChange?: () => void;
}) {
  const title = useTailorStore((s) => s.jobTitles[requestId]);
  return (
    <div className="rv-jobbar">
      <span className="rv-jobbar-label">Job</span>
      <span className="rv-jobbar-text" title={jobText}>
        {title || firstLine(jobText) || "Pasted job description"}
      </span>
      {onChange && (
        <button type="button" className="rv-link" onClick={onChange}>
          Tailor to a different job
        </button>
      )}
    </div>
  );
}

function Notice({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="re-state" role="status">
      <h2 className="re-state-title">{title}</h2>
      {children}
    </div>
  );
}

export function ReviewPanel({ fileId }: { fileId: string }) {
  const file = useDocumentStore((s) => s.files.find((f) => f.id === fileId));
  const viewing = useTailorStore((s) => s.viewing);
  const requestId = requestIdForFile(viewing, file);
  const dto = useTailorStore((s) =>
    requestId ? s.requests[requestId] : undefined,
  );
  const pollError = useTailorStore((s) =>
    requestId ? s.pollErrors[requestId] : undefined,
  );
  const [composing, setComposing] = useState(false);
  // True while the user has gone back from the suggested bullets to the cards.
  const [editingAnswers, setEditingAnswers] = useState(false);
  const status = dto?.status;

  useEffect(() => {
    if (requestId) ensureTailorRequest(requestId);
    setComposing(false);
    setEditingAnswers(false);
  }, [requestId]);

  // A new draft run always lands on its suggestions.
  useEffect(() => {
    if (status === "drafting") setEditingAnswers(false);
  }, [status]);

  if (!file) return null;

  let body: React.ReactNode;
  if (!requestId) {
    body = hasResumeData(file.structuredData) ? (
      <JobForm fileId={fileId} />
    ) : (
      <Notice title="Upload a resume first">
        <p>
          Tailoring works from the resume you upload. This one wasn&apos;t made
          from an upload.
        </p>
        <p>
          <Link href="/" className="rv-link">
            Upload a resume
          </Link>
        </p>
      </Notice>
    );
  } else if (composing) {
    body = <JobForm fileId={fileId} onCancel={() => setComposing(false)} />;
  } else if (!dto) {
    body = pollError ? (
      <Notice title="Couldn't load this report">
        <p>{pollError}</p>
        <button
          type="button"
          className="re-pill"
          onClick={() => trackTailorRequest(requestId)}
        >
          Try again
        </button>
      </Notice>
    ) : (
      <div aria-busy="true">
        <div className="re-skeleton" />
        <div className="re-skeleton re-skeleton-tall" />
      </div>
    );
  } else if (dto.status === "failed") {
    body = (
      <Notice title="That didn't work">
        <p>{dto.error || "Something went wrong while tailoring."}</p>
        <button
          type="button"
          className="rv-primary"
          onClick={() => {
            useTailorStore.getState().setJobDraft(dto.job_text);
            clearViewing(fileId);
          }}
        >
          Try again
        </button>
      </Notice>
    );
  } else if (dto.status === "analysing") {
    body = (
      <>
        <JobBar requestId={requestId} jobText={dto.job_text} />
        <div className="rv-working" role="status">
          <LoaderIcon className="re-spin size-4" aria-hidden="true" />
          {pollError
            ? `${pollError} It may still finish.`
            : "Reading the job and checking your resume…"}
          {pollError && (
            <button
              type="button"
              className="re-pill"
              onClick={() => trackTailorRequest(requestId, { adopt: true })}
            >
              Check again
            </button>
          )}
        </div>
        <div className="re-skeleton" aria-hidden="true" />
      </>
    );
  } else {
    body = (
      <>
        <JobBar
          requestId={requestId}
          jobText={dto.job_text}
          onChange={() => setComposing(true)}
        />
        {dto.error && (
          <p className="rv-error" role="alert">
            {dto.error}
          </p>
        )}
        {pollError && (
          <p className="rv-error" role="alert">
            {pollError}{" "}
            <button
              type="button"
              className="rv-link"
              onClick={() => trackTailorRequest(requestId)}
            >
              Check again
            </button>
          </p>
        )}
        {dto.scores && (
          <Scores
            scores={dto.scores}
            experience={dto.experience}
          />
        )}
        {(dto.proposals?.length ?? 0) > 0 &&
        dto.status === "ready" &&
        !editingAnswers ? (
          <Proposals
            dto={dto}
            fileId={fileId}
            onEditAnswers={() => setEditingAnswers(true)}
          />
        ) : (
          <GapQuestions dto={dto} />
        )}
        <MatchedDetails requirements={dto.requirements ?? []} />
        <JobDescription text={dto.job_text} />
      </>
    );
  }

  return (
    <div className="re-root">
      <div className="rv-column">{body}</div>
    </div>
  );
}
