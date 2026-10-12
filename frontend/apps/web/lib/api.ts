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

function apiUrl(path: string): string {
  return `${API_BASE}/api/${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `API ${path} failed (${res.status}): ${text.slice(0, 200)}`,
    );
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

/** Map a Django resume into an editor file, assigning resumeId. */
export function resumeToFile(resume: ResumeDto): ProjectFile {
  return {
    id: `resume-${resume.id}`,
    name: resume.title,
    type: "tex",
    content: resume.main_tex,
    resumeId: resume.id,
  };
}
