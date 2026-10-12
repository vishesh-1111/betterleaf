import { create } from "zustand";

import { createResume, deleteResume, patchResume } from "@/lib/api";

export interface ProjectFile {
  id: string;
  name: string;
  type: "tex" | "image";
  content?: string;
  dataUrl?: string;
  resumeId?: string;
}

interface DocumentState {
  files: ProjectFile[];
  activeFileId: string;
  cursorPosition: number;
  selectionRange: { start: number; end: number } | null;
  jumpToPosition: number | null;
  isThreadOpen: boolean;
  pdfData: Uint8Array | null;
  compileError: string | null;
  isCompiling: boolean;
  isSaving: boolean;
  initialized: boolean;

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
  setIsCompiling: (isCompiling: boolean) => void;
  setIsSaving: (isSaving: boolean) => void;
  insertAtCursor: (text: string) => void;
  replaceSelection: (start: number, end: number, text: string) => void;
  findAndReplace: (find: string, replace: string) => boolean;
  setInitialized: () => void;

  setFileName: (name: string) => void;
  setContent: (content: string) => void;
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

function getActiveFile(state: { files: ProjectFile[]; activeFileId: string }) {
  return state.files.find((f) => f.id === state.activeFileId);
}

const AUTOSAVE_MS = 800;

const pendingSave: Record<string, number> = {};

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
      void patchResume(current.resumeId, { main_tex: content });
    } else {
      void createResume(current.name, content).then((resume) => {
        useDocumentStore.setState((s) => ({
          files: s.files.map((f) =>
            f.id === current.id ? { ...f, resumeId: resume.id } : f,
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
  isCompiling: false,
  isSaving: false,
  initialized: false,

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

  setCompileError: (error) => set({ compileError: error, pdfData: null }),

  setIsCompiling: (isCompiling) => set({ isCompiling }),

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
