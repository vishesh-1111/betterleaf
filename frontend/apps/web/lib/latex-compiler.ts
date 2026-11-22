import {
  compileResume,
  createResume,
  patchResume,
} from "@/lib/api";
import { useDocumentStore } from "@/stores/document-store";

/**
 * Compile the active .tex file through the Django backend
 * (synchronous `POST /api/resumes/:id/compile/` -> latex service) and return the
 * PDF bytes. The current editor content is saved first so Django compiles
 * exactly what is on screen.
 */
export async function compileLatex(): Promise<Uint8Array> {
  const state = useDocumentStore.getState();
  const file =
    state.files.find((f) => f.id === state.activeFileId && f.type === "tex") ??
    state.files.find((f) => f.type === "tex");
  if (!file) throw new Error("No .tex file to compile");

  const content = file.content ?? "";
  let resumeId = file.resumeId;
  if (resumeId) {
    // Skip the save when the server already has this exact LaTeX (for example
    // right after the form regenerated it); an older copy must never be
    // written over a newer render.
    if (content !== file.savedTex) {
      await patchResume(resumeId, { main_tex: content });
      useDocumentStore.setState((s) => ({
        files: s.files.map((f) =>
          f.id === file.id ? { ...f, savedTex: content } : f,
        ),
      }));
    }
  } else {
    const resume = await createResume(file.name, content);
    resumeId = resume.id;
    useDocumentStore.setState((s) => ({
      files: s.files.map((f) => (f.id === file.id ? { ...f, resumeId } : f)),
    }));
  }

  const compilation = await compileResume(resumeId);
  if (compilation.status === "succeeded" && compilation.pdf_base64) {
    return Uint8Array.from(atob(compilation.pdf_base64), (c) =>
      c.charCodeAt(0),
    );
  }

  const log = compilation.log ?? "";
  const errorLines = log
    .split("\n")
    .filter((l) => l.includes("Error") || l.includes("!") || l.includes("Missing"))
    .slice(0, 10)
    .join("\n");
  throw new Error(
    `Compilation failed\n\n${errorLines || log.slice(-1000)}`.trim(),
  );
}
