"use client";

import { useEffect } from "react";
import { useDocumentStore } from "@/stores/document-store";
import { createResume, getWorkspace, resumeToFile } from "@/lib/api";
import { DEFAULT_TEX_CONTENT } from "@/lib/default-document";

const DEFAULT_IMAGE_FILE = {
  name: "hand-write.jpg",
  path: "/hand-write.jpg",
};

async function loadImageAsDataUrl(path: string): Promise<string> {
  const res = await fetch(path);
  const blob = await res.blob();
  const { promise, resolve, reject } = Promise.withResolvers<string>();
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result as string);
  reader.onerror = () => reject(reader.error ?? new Error("read failed"));
  reader.readAsDataURL(blob);
  return promise;
}

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

      // Seed the bundled image asset.
      const imageAlready = state.files.some(
        (f) => f.type === "image" && f.name === DEFAULT_IMAGE_FILE.name,
      );
      if (!imageAlready) {
        try {
          const dataUrl = await loadImageAsDataUrl(DEFAULT_IMAGE_FILE.path);
          const priorActive = useDocumentStore.getState().activeFileId;
          addFile({ name: DEFAULT_IMAGE_FILE.name, type: "image", dataUrl });
          useDocumentStore.getState().setActiveFile(priorActive);
        } catch (err) {
          console.error("Failed to load default image:", err);
        }
      }

      setInitialized();
    })().catch((err) => {
      console.error("Project init failed:", err);
      setInitialized();
    });
  }, [initialized, addFile, setInitialized]);
}
