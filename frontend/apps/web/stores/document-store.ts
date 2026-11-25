import { create } from "zustand";

import { createResume, deleteResume, patchResume } from "@/lib/api";
import {
  hasResumeData,
  normalizeResumeData,
  toPayload,
  type ResumeData,
} from "@/lib/resume-data";

export interface ProjectFile {
  id: string;
  name: string;
  type: "tex" | "image";
  content?: string;
  dataUrl?: string;
  resumeId?: string;
  /** The tailor job this resume came from; null for an original resume. */
  tailorRequestId?: string | null;
  /** Last LaTeX known to be on the server. */
  savedTex?: string;
  /** Raw resume data from the server (`{}` when never parsed). */
  structuredData?: Partial<ResumeData>;
  /** The editor's working copy; undefined until the form is first opened. */
  draft?: ResumeData;
  dataStatus?: DataStatus;
  dataError?: string;
}

export type DataStatus = "idle" | "dirty" | "saving" | "saved" | "error";

interface DocumentState {
  files: ProjectFile[];
  activeFileId: string;
  cursorPosition: number;
  selectionRange: { start: number; end: number } | null;
  jumpToPosition: number | null;
  isThreadOpen: boolean;
  pdfData: Uint8Array | null;
  compileError: string | null;
  /** Compiler reported errors but still produced a PDF. */
  compileWarning: string | null;
  isCompiling: boolean;
  isSaving: boolean;
  initialized: boolean;
  compileRequestId: number;
  /** A rebuild was asked for while one was running; run it right after. */
  compileQueued: boolean;

  setActiveFile: (id: string) => void;
  addFile: (file: Omit<ProjectFile, "id">) => string;
  deleteFile: (id: string) => void;
  renameFile: (id: string, name: string) => void;
  updateFileContent: (id: string, content: string) => void;
  setCursorPosition: (position: number) => void;
  setSelectionRange: (range: { start: number; end: number } | null) => void;
  requestJumpToPosition: (position: number) => void;
  clearJumpRequest: () => void;
  setThreadOpen: (open: boolean) => void;
  setPdfData: (data: Uint8Array | null) => void;
  setCompileError: (error: string | null) => void;
  setCompileWarning: (warning: string | null) => void;
  setIsCompiling: (isCompiling: boolean) => void;
  setIsSaving: (isSaving: boolean) => void;
  insertAtCursor: (text: string) => void;
  replaceSelection: (start: number, end: number, text: string) => void;
  findAndReplace: (find: string, replace: string) => boolean;
  setInitialized: () => void;

  setFileName: (name: string) => void;
  setContent: (content: string) => void;
  requestCompile: () => void;

  /** Load the form's working copy for a resume (once). */
  openDraft: (id: string) => void;
  /** Change the working copy; saves after a short pause. */
  editDraft: (id: string, update: (draft: ResumeData) => ResumeData) => void;
  /** Save now instead of waiting (tab switch, leaving the page). */
  flushDraft: (id: string) => void;
  retryDraftSave: (id: string) => void;
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

function getActiveFile(state: { files: ProjectFile[]; activeFileId: string }) {
  return state.files.find((f) => f.id === state.activeFileId);
}

const AUTOSAVE_MS = 800;

const pendingSave: Record<string, number> = {};
const pendingDraftSave: Record<string, number> = {};
const draftSaveSeq: Record<string, number> = {};
const DRAFT_SAVE_MS = 600;

function patchFile(id: string, patch: Partial<ProjectFile>) {
  useDocumentStore.setState((s) => ({
    files: s.files.map((f) => (f.id === id ? { ...f, ...patch } : f)),
  }));
}

function scheduleDraftSave(id: string, delay = DRAFT_SAVE_MS) {
  clearTimeout(pendingDraftSave[id]);
  pendingDraftSave[id] = window.setTimeout(() => {
    delete pendingDraftSave[id];
    void saveDraft(id);
  }, delay);
}

async function saveDraft(id: string) {
  const file = useDocumentStore.getState().files.find((f) => f.id === id);
  if (!file?.resumeId || !file.draft) return;
  // The form is now the source of truth: drop any queued LaTeX autosave.
  clearTimeout(pendingSave[id]);
  delete pendingSave[id];

  const seq = (draftSaveSeq[id] ?? 0) + 1;
  draftSaveSeq[id] = seq;
  patchFile(id, { dataStatus: "saving", dataError: undefined });
  try {
    const resume = await patchResume(file.resumeId, {
      structured_data: toPayload(file.draft),
    });
    if (draftSaveSeq[id] !== seq) return; // a newer save is on its way
    const stillEditing = Boolean(pendingDraftSave[id]);
    patchFile(id, {
      content: resume.main_tex,
      savedTex: resume.main_tex,
      structuredData: resume.structured_data,
      dataStatus: stillEditing ? "dirty" : "saved",
    });
    useDocumentStore.getState().requestCompile();
  } catch (error) {
    console.error("Saving resume data failed", error);
    if (draftSaveSeq[id] !== seq) return;
    patchFile(id, {
      dataStatus: "error",
      dataError:
        error instanceof Error ? error.message : "Couldn't save your changes",
    });
  }
}

function scheduleSave(file: ProjectFile) {
  if (file.type !== "tex") return;
  clearTimeout(pendingSave[file.id]);
  const timer = window.setTimeout(() => {
    const state = useDocumentStore.getState();
    const current = state.files.find((f) => f.id === file.id);
    delete pendingSave[file.id];
    if (!current || current.type !== "tex") return;
    const content = current.content ?? "";
    if (current.resumeId) {
      void patchResume(current.resumeId, { main_tex: content }).then(() => {
        patchFile(current.id, { savedTex: content });
      });
    } else {
      void createResume(current.name, content).then((resume) => {
        useDocumentStore.setState((s) => ({
          files: s.files.map((f) =>
            f.id === current.id
              ? { ...f, resumeId: resume.id, savedTex: content }
              : f,
          ),
        }));
      });
    }
  }, AUTOSAVE_MS);
  pendingSave[file.id] = timer;
}

export const useDocumentStore = create<DocumentState>()((set, get) => ({
  files: [],
  activeFileId: "",
  cursorPosition: 0,
  selectionRange: null,
  jumpToPosition: null,
  isThreadOpen: false,
  pdfData: null,
  compileError: null,
  compileWarning: null,
  isCompiling: false,
  isSaving: false,
  initialized: false,
  compileRequestId: 0,
  compileQueued: false,

  setActiveFile: (id) =>
    set({ activeFileId: id, cursorPosition: 0, selectionRange: null }),

  setSelectionRange: (range) => set({ selectionRange: range }),

  requestJumpToPosition: (position) => set({ jumpToPosition: position }),

  clearJumpRequest: () => set({ jumpToPosition: null }),

  addFile: (file) => {
    const id = generateId();
    set((state) => ({
      files: [...state.files, { ...file, id }],
      activeFileId: id,
    }));
    return id;
  },

  deleteFile: (id) => {
    const state = get();
    if (state.files.length <= 1) return;
    const target = state.files.find((f) => f.id === id);
    clearTimeout(pendingSave[id]);
    delete pendingSave[id];
    clearTimeout(pendingDraftSave[id]);
    delete pendingDraftSave[id];
    const newFiles = state.files.filter((f) => f.id !== id);
    const newActiveId =
      state.activeFileId === id ? newFiles[0].id : state.activeFileId;
    set({ files: newFiles, activeFileId: newActiveId });
    if (target?.resumeId) {
      void deleteResume(target.resumeId);
    }
  },

  renameFile: (id, name) => {
    set((state) => ({
      files: state.files.map((f) => (f.id === id ? { ...f, name } : f)),
    }));
    const current = get().files.find((f) => f.id === id);
    if (current?.resumeId) {
      void patchResume(current.resumeId, { title: name });
    }
  },

  updateFileContent: (id, content) => {
    set((state) => ({
      files: state.files.map((f) => (f.id === id ? { ...f, content } : f)),
    }));
  },

  setThreadOpen: (open) => set({ isThreadOpen: open }),

  setPdfData: (data) => set({ pdfData: data, compileError: null }),

  setCompileError: (error) =>
    set({ compileError: error, pdfData: null, compileWarning: null }),

  setCompileWarning: (warning) => set({ compileWarning: warning }),

  setIsCompiling: (isCompiling) =>
    set((state) =>
      !isCompiling && state.compileQueued
        ? {
            isCompiling,
            compileQueued: false,
            compileRequestId: state.compileRequestId + 1,
          }
        : { isCompiling },
    ),

  setIsSaving: (isSaving) => set({ isSaving }),

  setCursorPosition: (position) => set({ cursorPosition: position }),

  insertAtCursor: (text) => {
    const state = get();
    const activeFile = getActiveFile(state);
    if (!activeFile || activeFile.type !== "tex") return;

    const content = activeFile.content ?? "";
    const { cursorPosition } = state;
    const newContent =
      content.slice(0, cursorPosition) + text + content.slice(cursorPosition);

    set({
      files: state.files.map((f) =>
        f.id === activeFile.id ? { ...f, content: newContent } : f,
      ),
      cursorPosition: cursorPosition + text.length,
    });
    scheduleSave({ ...activeFile, content: newContent });
  },

  replaceSelection: (start, end, text) => {
    const state = get();
    const activeFile = getActiveFile(state);
    if (!activeFile || activeFile.type !== "tex") return;

    const content = activeFile.content ?? "";
    const newContent = content.slice(0, start) + text + content.slice(end);

    set({
      files: state.files.map((f) =>
        f.id === activeFile.id ? { ...f, content: newContent } : f,
      ),
      cursorPosition: start + text.length,
    });
    scheduleSave({ ...activeFile, content: newContent });
  },

  findAndReplace: (find, replace) => {
    const state = get();
    const activeFile = getActiveFile(state);
    if (!activeFile || activeFile.type !== "tex") return false;

    const content = activeFile.content ?? "";
    if (!content.includes(find)) return false;

    const newContent = content.replace(find, replace);
    set({
      files: state.files.map((f) =>
        f.id === activeFile.id ? { ...f, content: newContent } : f,
      ),
    });
    scheduleSave({ ...activeFile, content: newContent });
    return true;
  },

  setInitialized: () => set({ initialized: true }),

  requestCompile: () =>
    set((state) =>
      state.isCompiling
        ? { compileQueued: true }
        : { compileRequestId: state.compileRequestId + 1 },
    ),

  openDraft: (id) => {
    const file = get().files.find((f) => f.id === id);
    if (!file || file.draft || !hasResumeData(file.structuredData)) return;
    patchFile(id, {
      draft: normalizeResumeData(file.structuredData ?? {}),
      dataStatus: "idle",
    });
  },

  editDraft: (id, update) => {
    const file = get().files.find((f) => f.id === id);
    if (!file?.draft) return;
    patchFile(id, { draft: update(file.draft), dataStatus: "dirty" });
    scheduleDraftSave(id);
  },

  flushDraft: (id) => {
    if (!pendingDraftSave[id]) return;
    clearTimeout(pendingDraftSave[id]);
    delete pendingDraftSave[id];
    void saveDraft(id);
  },

  retryDraftSave: (id) => {
    scheduleDraftSave(id, 0);
  },

  setFileName: (name) => {
    const state = get();
    set({
      files: state.files.map((f) =>
        f.id === state.activeFileId ? { ...f, name } : f,
      ),
    });
  },

  setContent: (content) => {
    const state = get();
    const activeFile = getActiveFile(state);
    set({
      files: state.files.map((f) =>
        f.id === state.activeFileId ? { ...f, content } : f,
      ),
    });
    if (activeFile) {
      scheduleSave({ ...activeFile, content });
    }
  },
}));
