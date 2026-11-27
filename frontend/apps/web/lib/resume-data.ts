/** TypeScript mirror of the backend `ResumeData` (betterleaf/resumes/services/schemas.py). */

export interface Bullet {
  id: string;
  text: string;
}

export interface ContactInfo {
  phone?: string | null;
  email?: string | null;
  linkedin?: string | null;
  github?: string | null;
  portfolio?: string | null;
}

export interface Experience {
  id: string;
  company: string;
  role: string;
  duration: string;
  bullets: Bullet[];
}

export interface Education {
  id: string;
  institution: string;
  degree: string;
  duration: string;
}

export interface Project {
  id: string;
  title: string;
  github?: string | null;
  deployed?: string | null;
  tech_stack: string;
  bullets: Bullet[];
}

export interface SkillGroup {
  id: string;
  key: string;
  /** Comma-separated skill words. */
  value: string;
}

export interface Achievement {
  id: string;
  title: string;
  bullets: Bullet[];
}

export type SectionKey =
  | "summary"
  | "education"
  | "experience"
  | "projects"
  | "technical_skills"
  | "achievements";

export const SECTION_KEYS: SectionKey[] = [
  "summary",
  "education",
  "experience",
  "projects",
  "technical_skills",
  "achievements",
];

export const SECTION_TITLES: Record<SectionKey, string> = {
  summary: "Summary",
  education: "Education",
  experience: "Experience",
  projects: "Projects",
  technical_skills: "Technical skills",
  achievements: "Achievements",
};

export interface ResumeData {
  name: string;
  contact: ContactInfo;
  summary: { text: string } | null;
  education: Education[];
  experience: Experience[];
  projects: Project[];
  technical_skills: SkillGroup[];
  achievements: Achievement[];
  section_order: SectionKey[];
}

export function newId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function newBullet(text = ""): Bullet {
  return { id: newId(), text };
}

export function newExperience(): Experience {
  return {
    id: newId(),
    company: "",
    role: "",
    duration: "",
    bullets: [newBullet()],
  };
}

export function newEducation(): Education {
  return { id: newId(), institution: "", degree: "", duration: "" };
}

export function newProject(): Project {
  return {
    id: newId(),
    title: "",
    github: "",
    deployed: "",
    tech_stack: "",
    bullets: [newBullet()],
  };
}

export function newSkillGroup(): SkillGroup {
  return { id: newId(), key: "", value: "" };
}

export function newAchievement(): Achievement {
  return { id: newId(), title: "", bullets: [newBullet()] };
}

function isSectionKey(key: unknown): key is SectionKey {
  return SECTION_KEYS.includes(key as SectionKey);
}

function hasContent(data: Partial<ResumeData>, key: SectionKey): boolean {
  const value = data[key];
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

/** True when the stored JSON looks like a parsed resume (the starter and
 * hand-written resumes carry `{}`). */
export function hasResumeData(raw: unknown): boolean {
  return (
    typeof raw === "object" &&
    raw !== null &&
    typeof (raw as { name?: unknown }).name === "string"
  );
}

/** Older resumes were stored without ids, and bullets as plain strings. */
function looseBullets(list: unknown[] | undefined): Bullet[] {
  return (list ?? []).map((b) => {
    if (typeof b === "string") return newBullet(b);
    const bullet = b as Partial<Bullet>;
    return { id: bullet.id || newId(), text: bullet.text ?? "" };
  });
}

function withId<T extends { id?: string }>(item: T): T & { id: string } {
  return { ...item, id: item.id || newId() };
}

/** Fill gaps in server data so every field the editor touches exists, and
 * make `section_order` list every section that has content. */
export function normalizeResumeData(raw: Partial<ResumeData>): ResumeData {
  const data: ResumeData = {
    name: raw.name ?? "",
    contact: { ...(raw.contact ?? {}) },
    summary: raw.summary ?? null,
    education: (raw.education ?? []).map(withId),
    experience: (raw.experience ?? []).map((e) => ({
      ...withId(e),
      bullets: looseBullets(e.bullets),
    })),
    projects: (raw.projects ?? []).map((p) => ({
      ...withId(p),
      tech_stack: p.tech_stack ?? "",
      bullets: looseBullets(p.bullets),
    })),
    technical_skills: (raw.technical_skills ?? []).map(withId),
    achievements: (raw.achievements ?? []).map((a) => ({
      ...withId(a),
      bullets: looseBullets(a.bullets),
    })),
    section_order: [],
  };
  const order = (raw.section_order ?? []).filter(isSectionKey);
  const seen = new Set<SectionKey>(order);
  for (const key of SECTION_KEYS) {
    if (!seen.has(key) && hasContent(data, key)) order.push(key);
  }
  data.section_order = order;
  return data;
}

function blankToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

/** What gets sent to the server: empty bullets and an empty summary are left
 * out so they never reach the LaTeX. The on-screen draft keeps them. */
export function toPayload(data: ResumeData): ResumeData {
  const bullets = (list: Bullet[]) => list.filter((b) => (b.text ?? "").trim());
  return {
    ...data,
    contact: {
      phone: blankToNull(data.contact.phone),
      email: blankToNull(data.contact.email),
      linkedin: blankToNull(data.contact.linkedin),
      github: blankToNull(data.contact.github),
      portfolio: blankToNull(data.contact.portfolio),
    },
    summary: data.summary?.text.trim() ? data.summary : null,
    experience: data.experience.map((e) => ({
      ...e,
      bullets: bullets(e.bullets),
    })),
    projects: data.projects.map((p) => ({
      ...p,
      github: blankToNull(p.github),
      deployed: blankToNull(p.deployed),
      bullets: bullets(p.bullets),
    })),
    achievements: data.achievements.map((a) => ({
      ...a,
      bullets: bullets(a.bullets),
    })),
  };
}

export function moveItem<T>(list: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= list.length) return list;
  const next = list.slice();
  const [item] = next.splice(from, 1);
  next.splice(Math.min(to, next.length), 0, item);
  return next;
}
