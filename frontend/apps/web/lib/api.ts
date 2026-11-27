import type { ResumeData } from "@/lib/resume-data";
import type { ProjectFile } from "@/stores/document-store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface ResumeDto {
  id: string;
  title: string;
  slug: string;
  template: string;
  main_tex: string;
  /** Parsed resume data; `{}` for resumes that were never parsed. */
  structured_data: Partial<ResumeData>;
  /** The job this resume was tailored for; null for an original resume. */
  tailor_request_id?: string | null;
  /** First tailor request on the same job; only in the workspace listing. */
  job_id?: string | null;
  /** Short job-text snippet used to name the job group. */
  job_label?: string | null;
  created_at?: string;
  updated_at: string;
}

export interface MasterResumeDto {
  id: string;
  title: string;
  updated_at: string;
}

export class ApiError extends Error {
  readonly status: number;
  /** The server's plain `detail` message, when it sent one. */
  readonly detail: string | null;

  constructor(path: string, status: number, body: string) {
    super(`API ${path} failed (${status}): ${body.slice(0, 200)}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = parseDetail(body);
  }
}

function parseDetail(body: string): string | null {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    return typeof detail === "string" ? detail : null;
  } catch {
    return null;
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
  master_resume: MasterResumeDto | null;
  resumes: ResumeDto[];
  /** A tailor job still running, so a reload can pick it back up. */
  active_tailor_request_id?: string | null;
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
  data: { main_tex?: string; title?: string; structured_data?: ResumeData },
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
  /** Compiler exit code (0 = clean); null if the compiler never ran. */
  exit_status: number | null;
  /** Whether a PDF was produced (can be true even when exit_status != 0). */
  has_pdf: boolean;
  /** Base64-encoded PDF; empty when no PDF was produced. */
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

export interface AutofitResult {
  /** False when even the tightest layout overflows the page limit. */
  fits: boolean;
  resume: ResumeDto;
}

/** Re-render the LaTeX with spacing tuned to fit one page. Pass the unsaved
 * form data so edits not yet autosaved are included. */
export async function autofitResume(
  resumeId: string,
  structuredData?: ResumeData,
): Promise<AutofitResult> {
  return request<AutofitResult>(`resumes/${resumeId}/autofit/`, {
    method: "POST",
    body: JSON.stringify(
      structuredData ? { structured_data: structuredData } : {},
    ),
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
    savedTex: resume.main_tex,
    structuredData: resume.structured_data,
    dataStatus: "idle",
    resumeId: resume.id,
    tailorRequestId: resume.tailor_request_id ?? null,
    jobId: resume.job_id ?? null,
    jobLabel: resume.job_label ?? null,
    createdAt: resume.created_at,
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

/* ------------------------------------------------------------ tailoring */

export type TailorStatus = "analysing" | "ready" | "drafting" | "failed";
export type Coverage = "met" | "partial" | "not_met";
export type Importance = "must_have" | "nice_to_have";
/** Sections a new bullet can be added to. */
export type SourceType = "experience" | "projects" | "achievements";

export interface TailorRequirement {
  id: string;
  text: string;
  importance: Importance;
  priority: number;
  status: Coverage;
  evidence: { source_id: string; quote: string }[];
  rationale: string;
}

export interface GapQuestion {
  requirement_id: string;
  question: string;
}

/** A job, project or achievement a gap answer can be attached to. */
export interface AnswerTarget {
  source_type: SourceType;
  item_id: string;
  label: string;
}

export interface GapProposal {
  id: string;
  requirement_id: string;
  requirement_text: string;
  source_type: SourceType;
  item_id: string;
  change: "add_bullet" | "no_change";
  bullet: string;
  skill: string;
  skill_group_id: string;
  reason: string;
}

export interface TailorExperience {
  required_label: string;
  required_years: number | null;
  candidate_years: number;
}

export interface TailorScores {
  must_have: { earned: number; total: number };
  nice_to_have: { earned: number; total: number };
}

/** What polling `tailor-requests/{id}/` returns. The report fields are only
 * present once the request has been analysed (`ready` or `drafting`). */
export interface TailorRequestDto {
  id: string;
  status: TailorStatus;
  kind: "initial" | "gap_followup";
  job_text: string;
  parent_id: string | null;
  error?: string;
  resume_id?: string | null;
  scores?: TailorScores;
  experience?: TailorExperience;
  requirements?: TailorRequirement[];
  gap_questions?: GapQuestion[];
  answer_targets?: AnswerTarget[];
  proposals?: GapProposal[];
}

export interface GapAnswerInput {
  requirement_id: string;
  source_type: SourceType;
  item_id: string;
  text: string;
}

export interface AcceptedProposalInput {
  id: string;
  bullet: string;
  skill: string;
  skill_group_id: string;
}

export interface TailorStarted {
  id: string;
  status: TailorStatus;
}

export async function startTailorRequest(
  jobText: string,
): Promise<TailorStarted> {
  return request<TailorStarted>("tailor-requests/", {
    method: "POST",
    body: JSON.stringify({ job_text: jobText }),
  });
}

export async function getJobTitle(jobText: string): Promise<string> {
  const res = await request<{ title: string }>("job-title/", {
    method: "POST",
    body: JSON.stringify({ job_text: jobText }),
  });
  return res.title;
}

export async function getTailorRequest(
  id: string,
  signal?: AbortSignal,
): Promise<TailorRequestDto> {
  return request<TailorRequestDto>(`tailor-requests/${id}/`, { signal });
}

export async function submitGapAnswers(
  id: string,
  answers: GapAnswerInput[],
): Promise<TailorStarted> {
  return request<TailorStarted>(`tailor-requests/${id}/answers/`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

/** Save the accepted bullets into the master and start the follow-up request. */
export async function confirmProposals(
  id: string,
  accepted: AcceptedProposalInput[],
): Promise<TailorStarted> {
  return request<TailorStarted>(`tailor-requests/${id}/confirm/`, {
    method: "POST",
    body: JSON.stringify({ accepted }),
  });
}
