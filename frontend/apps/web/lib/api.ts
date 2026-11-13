import type { ProjectFile } from "@/stores/document-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ResumeDto {
  id: string;
  title: string;
  slug: string;
  template: string;
  main_tex: string;
  updated_at: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(path: string, status: number, body: string) {
    super(`API ${path} failed (${status}): ${body.slice(0, 200)}`);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiUrl(path: string): string {
  return `${API_BASE}/api/${path}`;
}

const UNSAFE_METHODS: Record<string, true> = {
  POST: true,
  PUT: true,
  PATCH: true,
  DELETE: true,
};

function getCsrfToken(): string | undefined {
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrftoken="));
  return match?.slice("csrftoken=".length);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method?.toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (method && UNSAFE_METHODS[method]) {
    const csrf = getCsrfToken();
    if (csrf) headers["X-CSRFToken"] = csrf;
  }
  const res = await fetch(apiUrl(path), {
    credentials: "include",
    headers,
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(path, res.status, text);
  }
  return (await res.json()) as T;
}

export interface WorkspaceDto {
  workspace_id: string;
  anonymous: boolean;
  resumes: ResumeDto[];
}

/** Fetch the workspace (creating + setting the cookie if none exists) and all
 * of its resumes in a single request. */
export async function getWorkspace(): Promise<WorkspaceDto> {
  return request<WorkspaceDto>("workspace/");
}

export async function createResume(
  title: string,
  mainTex: string,
): Promise<ResumeDto> {
  return request<ResumeDto>("resumes/", {
    method: "POST",
    body: JSON.stringify({
      title,
      template: "jakes",
      main_tex: mainTex,
    }),
  });
}

export async function patchResume(
  id: string,
  data: { main_tex?: string; title?: string },
): Promise<ResumeDto> {
  return request<ResumeDto>(`resumes/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getResume(id: string): Promise<ResumeDto> {
  return request<ResumeDto>(`resumes/${id}/`);
}

export async function deleteResume(id: string): Promise<void> {
  await request<void>(`resumes/${id}/`, { method: "DELETE" });
}

export type CompilationStatus = "queued" | "running" | "succeeded" | "failed";

export interface CompilationDto {
  id: string;
  status: CompilationStatus;
  /** Base64-encoded PDF; empty unless the compile succeeded. */
  pdf_base64: string;
  log: string;
}

/** Compile the resume's saved `main_tex` via Django. The request is
 * synchronous: it resolves once pdflatex has finished (or failed). */
export async function compileResume(resumeId: string): Promise<CompilationDto> {
  return request<CompilationDto>(`resumes/${resumeId}/compile/`, {
    method: "POST",
  });
}

export interface AuthStatus {
  authenticated: boolean;
}

/** Check whether the current session is authenticated with Django.

 * Always resolves to a boolean; the endpoint returns 200 for both states. */
export async function checkAuthentication(): Promise<boolean> {
  const res = await fetch(apiUrl("users/auth-status/"), {
    credentials: "include",
  });
  if (!res.ok) {
    // Network or server error: treat as unauthenticated so the user is
    // safely sent through the login flow rather than blocked.
    return false;
  }
  const data = (await res.json()) as AuthStatus;
  return data.authenticated === true;
}

/** Absolute URL that starts the Django Google OAuth flow. The backend redirects
 * back to the frontend origin with `?download=true` so the download resumes. */
export function googleLoginUrl(): string {
  return `${API_BASE}/accounts/google/login/`;
}

/** Map a Django resume into an editor file, assigning resumeId. */
export function resumeToFile(resume: ResumeDto): ProjectFile {
  const title = resume.title?.trim() || "document.tex";
  const name = title.endsWith(".tex") ? title : `${title}.tex`;
  return {
    id: `resume-${resume.id}`,
    name,
    type: "tex",
    content: resume.main_tex,
    resumeId: resume.id,
  };
}

export type UploadStatus = "queued" | "processing" | "succeeded" | "failed";

export interface UploadTaskDto {
  task_id: string;
  status: "queued";
  created: boolean;
}

export interface UploadStatusDto {
  task_id: string;
  status: UploadStatus;
  master_resume_id?: string;
  resume_ids?: string[];
  error?: string;
}

/** Queue a resume PDF for parsing. The backend attaches/creates the workspace
 * (setting the `bl_session` cookie) and returns a task to poll with
 * `getUploadStatus`; the resume doesn't exist yet when this resolves. */
export async function startPdfUpload(
  file: File,
  signal?: AbortSignal,
): Promise<UploadTaskDto> {
  const headers: Record<string, string> = {};
  const csrf = getCsrfToken();
  if (csrf) headers["X-CSRFToken"] = csrf;

  const form = new FormData();
  form.append("file", file);

  const path = "upload-pdf/";
  const res = await fetch(apiUrl(path), {
    credentials: "include",
    method: "POST",
    headers,
    body: form,
    signal,
  });
  if (!res.ok) {
    throw new ApiError(path, res.status, await res.text().catch(() => ""));
  }
  return (await res.json()) as UploadTaskDto;
}

/** Poll the status of a task returned by `startPdfUpload`. */
export async function getUploadStatus(
  taskId: string,
  signal?: AbortSignal,
): Promise<UploadStatusDto> {
  return request<UploadStatusDto>(
    `upload-pdf/${encodeURIComponent(taskId)}/status/`,
    { signal },
  );
}
