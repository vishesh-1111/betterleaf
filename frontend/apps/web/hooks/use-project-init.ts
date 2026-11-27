"use client";

import { useEffect } from "react";
import { useDocumentStore } from "@/stores/document-store";
import { createResume, getWorkspace, resumeToFile } from "@/lib/api";
import { DEFAULT_TEX_CONTENT } from "@/lib/default-document";
import { hasResumeData } from "@/lib/resume-data";
import { resumeRunningRequest } from "@/stores/tailor-store";

export function useProjectInit() {
  const initialized = useDocumentStore((s) => s.initialized);
  const setInitialized = useDocumentStore((s) => s.setInitialized);
  const addFile = useDocumentStore((s) => s.addFile);

  useEffect(() => {
    if (initialized) return;

    (async () => {
      // Establish (or reuse) the workspace so the `bl_session` cookie is set
      // and fetch all of its resumes in one call.
      const workspace = await getWorkspace();

      useDocumentStore.getState().setMaster(workspace.master_resume ?? null);

      let resumes = workspace.resumes;

      if (resumes.length === 0) {
        const created = await createResume("document.tex", DEFAULT_TEX_CONTENT);
        resumes = [created];
      }

      const texFiles = resumes.map(resumeToFile);
      for (const file of texFiles) {
        if (
          !useDocumentStore
            .getState()
            .files.some((f) => f.resumeId === file.resumeId)
        ) {
          addFile(file);
        }
      }

      // Reconcile active file to a tex resume (default: first one).
      const state = useDocumentStore.getState();
      const active = state.files.find((f) => f.id === state.activeFileId);
      if (!active || active.type !== "tex") {
        const firstTex = state.files.find((f) => f.type === "tex");
        if (firstTex) {
          state.setActiveFile(firstTex.id);
        }
      }

      // A tailor job was still running when the page closed: show it again
      // on the original resume's Review tab and keep waiting for it.
      if (workspace.active_tailor_request_id) {
        const original = useDocumentStore
          .getState()
          .files.find(
            (f) =>
              f.type === "tex" &&
              f.resumeId &&
              !f.tailorRequestId &&
              hasResumeData(f.structuredData),
          );
        if (original) {
          resumeRunningRequest(original.id, workspace.active_tailor_request_id);
        }
      }

      setInitialized();
    })().catch((err) => {
      console.error("Project init failed:", err);
      setInitialized();
    });
  }, [initialized, addFile, setInitialized]);
}
