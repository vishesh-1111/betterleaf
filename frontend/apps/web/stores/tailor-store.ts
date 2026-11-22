import { create } from "zustand";

import {
  ApiError,
  confirmProposals,
  getResume,
  getTailorRequest,
  resumeToFile,
  startTailorRequest,
  submitGapAnswers,
  type GapAnswerInput,
  type TailorRequestDto,
} from "@/lib/api";
import { useDocumentStore } from "@/stores/document-store";

/** What the user has typed for one gap question. `target` is
 * `"<source_type>:<item_id>"`; empty means "use the first one". */
export interface AnswerDraft {
  target: string;
  text: string;
}

/** The user's review of one proposed bullet. Unset means "accepted, as drafted". */
export interface ProposalEdit {
  accepted?: boolean;
  bullet?: string;
}

interface TailorState {
  /** Latest server copy of every request we are showing or waiting on. */
  requests: Record<string, TailorRequestDto>;
  /** Why polling stopped early (offline, took too long), by request id. */
  pollErrors: Record<string, string>;
  /** Which request a file's Review tab shows. A tailored file falls back to its
   * own `tailorRequestId`; this wins while a follow-up is running. */
  viewing: Record<string, string>;
  /** The job text being typed, kept when switching tabs. */
  jobDraft: string;
  answers: Record<string, Record<string, AnswerDraft>>;
  edits: Record<string, Record<string, ProposalEdit>>;

  setJobDraft: (text: string) => void;
  setAnswer: (
    requestId: string,
    reqId: string,
    patch: Partial<AnswerDraft>,
  ) => void;
  setEdit: (requestId: string, proposalId: string, patch: ProposalEdit) => void;
}

export const useTailorStore = create<TailorState>()((set) => ({
  requests: {},
  pollErrors: {},
  viewing: {},
  jobDraft: "",
  answers: {},
  edits: {},

  setJobDraft: (jobDraft) => set({ jobDraft }),
  setAnswer: (requestId, reqId, patch) =>
    set((s) => {
      const mine = s.answers[requestId] ?? {};
      const current = mine[reqId] ?? { target: "", text: "" };
      return {
        answers: {
          ...s.answers,
          [requestId]: { ...mine, [reqId]: { ...current, ...patch } },
        },
      };
    }),
  setEdit: (requestId, proposalId, patch) =>
    set((s) => {
      const mine = s.edits[requestId] ?? {};
      return {
        edits: {
          ...s.edits,
          [requestId]: {
            ...mine,
            [proposalId]: { ...mine[proposalId], ...patch },
          },
        },
      };
    }),
}));

/* --------------------------------------------------------------- polling */

const POLL_MS = 2000;
const POLL_SLOW_MS = 4000;
const SLOW_AFTER_MS = 30_000;
const TIMEOUT_MS = 180_000;
const MAX_NETWORK_ERRORS = 3;

const TIMEOUT_ERROR = "This is taking longer than expected.";
const NETWORK_ERROR = "Lost connection to the server.";

const loops = new Map<string, AbortController>();

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

function putRequest(dto: TailorRequestDto) {
  useTailorStore.setState((s) => {
    const { [dto.id]: _cleared, ...pollErrors } = s.pollErrors;
    return { requests: { ...s.requests, [dto.id]: dto }, pollErrors };
  });
}

function putPollError(id: string, message: string) {
  useTailorStore.setState((s) => ({
    pollErrors: { ...s.pollErrors, [id]: message },
  }));
}

/** When a job finishes, add its tailored resume to the left list, show it and
 * build its PDF. The file that was waiting on it stops pointing at this job. */
async function adoptResume(dto: TailorRequestDto) {
  const docs = useDocumentStore.getState();
  const resumeId = dto.resume_id;
  if (!resumeId) return;
  const file = docs.files.find((f) => f.resumeId === resumeId);
  if (!file) {
    const resume = await getResume(resumeId);
    docs.addFile(resumeToFile(resume));
  } else {
    docs.setActiveFile(file.id);
  }
  useTailorStore.setState((s) => ({
    viewing: Object.fromEntries(
      Object.entries(s.viewing).filter(([, id]) => id !== dto.id),
    ),
  }));
  useDocumentStore.getState().requestCompile();
}

/** Poll a request until it is `ready` or `failed`. `adopt` opens the tailored
 * resume when it finishes (for jobs the user is waiting on). Starting it again
 * for the same id restarts the loop. */
export function trackTailorRequest(id: string, { adopt = false } = {}) {
  loops.get(id)?.abort();
  const controller = new AbortController();
  loops.set(id, controller);
  const { signal } = controller;

  void (async () => {
    const startedAt = Date.now();
    let networkErrors = 0;
    while (!signal.aborted) {
      const elapsed = Date.now() - startedAt;
      if (elapsed > TIMEOUT_MS) {
        putPollError(id, TIMEOUT_ERROR);
        return;
      }
      try {
        const dto = await getTailorRequest(id, signal);
        networkErrors = 0;
        putRequest(dto);
        if (dto.status === "ready" || dto.status === "failed") {
          if (adopt && dto.status === "ready") await adoptResume(dto);
          return;
        }
      } catch (err) {
        if (isAbort(err)) return;
        const terminal =
          err instanceof ApiError && (err.status === 403 || err.status === 404);
        if (terminal || ++networkErrors > MAX_NETWORK_ERRORS) {
          putPollError(id, NETWORK_ERROR);
          return;
        }
      }
      await sleep(elapsed > SLOW_AFTER_MS ? POLL_SLOW_MS : POLL_MS, signal);
    }
  })().finally(() => {
    if (loops.get(id) === controller) loops.delete(id);
  });
}

/** Load a request we have no copy of yet (after a reload or tab switch). */
export function ensureTailorRequest(id: string) {
  const state = useTailorStore.getState();
  if (state.requests[id] || loops.has(id) || state.pollErrors[id]) return;
  trackTailorRequest(id);
}

/* --------------------------------------------------------------- actions */

/** Start a job from pasted text and show it on `fileId`'s Review tab. Throws
 * an `Error` with a readable message if the server refuses. */
export async function startTailor(fileId: string, jobText: string) {
  try {
    const started = await startTailorRequest(jobText.trim());
    useTailorStore.setState((s) => ({
      viewing: { ...s.viewing, [fileId]: started.id },
      requests: {
        ...s.requests,
        [started.id]: {
          id: started.id,
          status: started.status,
          kind: "initial",
          job_text: jobText.trim(),
          parent_id: null,
        },
      },
    }));
    trackTailorRequest(started.id, { adopt: true });
  } catch (err) {
    throw new Error(
      err instanceof ApiError && err.detail
        ? err.detail
        : "Couldn't start. Please try again.",
    );
  }
}

/** Send the typed answers; the request goes to `drafting` until bullets return. */
export async function submitAnswers(id: string, answers: GapAnswerInput[]) {
  try {
    await submitGapAnswers(id, answers);
  } catch (err) {
    throw new Error(
      err instanceof ApiError && err.detail
        ? err.detail
        : "Couldn't send your answers. Please try again.",
    );
  }
  useTailorStore.setState((s) => {
    const current = s.requests[id];
    return current
      ? {
          requests: {
            ...s.requests,
            [id]: { ...current, status: "drafting", error: undefined },
          },
        }
      : {};
  });
  trackTailorRequest(id);
}

/** Save the kept bullets and tailor again; `fileId`'s Review tab follows the new job. */
export async function confirmAccepted(
  id: string,
  fileId: string,
  accepted: Parameters<typeof confirmProposals>[1],
) {
  let followUp;
  try {
    followUp = await confirmProposals(id, accepted);
  } catch (err) {
    throw new Error(
      err instanceof ApiError && err.detail
        ? err.detail
        : "Couldn't save your bullets. Please try again.",
    );
  }
  useTailorStore.setState((s) => ({
    viewing: { ...s.viewing, [fileId]: followUp.id },
    requests: {
      ...s.requests,
      [followUp.id]: {
        id: followUp.id,
        status: followUp.status,
        kind: "gap_followup",
        job_text: s.requests[id]?.job_text ?? "",
        parent_id: id,
      },
    },
  }));
  trackTailorRequest(followUp.id, { adopt: true });
}

/** After a reload: pick up a job that was still running. */
export function resumeRunningRequest(fileId: string, requestId: string) {
  useTailorStore.setState((s) => ({
    viewing: { ...s.viewing, [fileId]: requestId },
  }));
  trackTailorRequest(requestId, { adopt: true });
}

/** The request a file's Review tab shows, if any. */
export function requestIdForFile(
  viewing: Record<string, string>,
  file: { id: string; tailorRequestId?: string | null } | undefined,
): string | null {
  if (!file) return null;
  return viewing[file.id] ?? file.tailorRequestId ?? null;
}

/** Stop showing a file's job (for example after it failed) so the paste box returns. */
export function clearViewing(fileId: string) {
  useTailorStore.setState((s) => {
    const { [fileId]: _gone, ...viewing } = s.viewing;
    return { viewing };
  });
}
