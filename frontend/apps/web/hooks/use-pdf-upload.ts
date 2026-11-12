"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getUploadStatus, startPdfUpload } from "@/lib/api";

export type UploadPhase =
  | "idle"
  | "uploading"
  | "processing"
  | "succeeded"
  | "failed";

const POLL_MS = 1500;
const POLL_MAX_MS = 3000;
// Backend gives each attempt a 60s soft limit and retries; unknown task ids
// report "queued" forever, so we must stop on our own.
const TIMEOUT_MS = 120_000;
// Consecutive transient fetch failures tolerated while polling.
const MAX_NETWORK_ERRORS = 3;

const GENERIC_ERROR = "Upload failed. Please try again.";
const TIMEOUT_ERROR = "Taking longer than expected. Please try again.";

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

/** Upload a resume PDF, then poll the backend until the Celery job finishes.
 * `onSuccess` fires once the parsed resume exists. */
export function usePdfUpload({ onSuccess }: { onSuccess: () => void }) {
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;

  const abort = useCallback(() => {
    controller.current?.abort();
    controller.current = null;
  }, []);

  useEffect(() => abort, [abort]);

  const start = useCallback(
    async (file: File) => {
      abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      const { signal } = ctrl;

      const fail = (message: string) => {
        setError(message);
        setPhase("failed");
      };

      setError(null);
      setPhase("uploading");

      try {
        const task = await startPdfUpload(file, signal);
        setPhase("processing");

        const startedAt = Date.now();
        let delay = POLL_MS;
        let networkErrors = 0;

        while (!signal.aborted) {
          if (Date.now() - startedAt > TIMEOUT_MS) {
            fail(TIMEOUT_ERROR);
            return;
          }

          try {
            const status = await getUploadStatus(task.task_id, signal);
            networkErrors = 0;
            if (status.status === "succeeded") {
              setPhase("succeeded");
              onSuccessRef.current();
              return;
            }
            if (status.status === "failed") {
              fail(status.error ?? GENERIC_ERROR);
              return;
            }
          } catch (err) {
            if (isAbort(err)) return;
            // 403/404 won't fix themselves; anything else gets a few retries.
            const terminal =
              err instanceof ApiError &&
              (err.status === 403 || err.status === 404);
            if (terminal || ++networkErrors > MAX_NETWORK_ERRORS) {
              fail(GENERIC_ERROR);
              return;
            }
          }

          await sleep(delay, signal);
          delay = Math.min(delay * 1.25, POLL_MAX_MS);
        }
      } catch (err) {
        if (isAbort(err)) return;
        fail(
          err instanceof ApiError && err.status === 400
            ? "That file isn't a valid PDF."
            : GENERIC_ERROR,
        );
      }
    },
    [abort],
  );

  const reset = useCallback(() => {
    abort();
    setError(null);
    setPhase("idle");
  }, [abort]);

  return {
    phase,
    error,
    start,
    reset,
    isBusy: phase === "uploading" || phase === "processing",
  };
}
