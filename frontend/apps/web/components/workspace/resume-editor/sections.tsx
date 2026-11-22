"use client";

import { useRef, useState, type ReactNode } from "react";
import { PlusIcon, Trash2Icon, XIcon } from "lucide-react";
import {
  newAchievement,
  newBullet,
  newEducation,
  newExperience,
  newProject,
  newSkillGroup,
  type Bullet,
  type ResumeData,
} from "@/lib/resume-data";
import {
  AutoTextarea,
  Field,
  IconButton,
  SortableList,
  useEditor,
} from "./primitives";

/* ---------------------------------------------------------------- bullets */

function focusBullet(id: string) {
  requestAnimationFrame(() => {
    document
      .querySelector<HTMLTextAreaElement>(`[data-bullet="${id}"]`)
      ?.focus();
  });
}

function BulletList({
  bullets,
  onChange,
  onRemoveBullet,
}: {
  bullets: Bullet[];
  onChange: (next: Bullet[]) => void;
  onRemoveBullet: (bullet: Bullet, next: Bullet[]) => void;
}) {
  const addAfter = (index: number) => {
    const bullet = newBullet();
    const next = bullets.slice();
    next.splice(index + 1, 0, bullet);
    onChange(next);
    focusBullet(bullet.id);
  };

  return (
    <div className="re-bullets">
      <SortableList
        items={bullets}
        onReorder={onChange}
        rowClassName="re-bullet"
        renderRow={(bullet, index, handle) => (
          <>
            {handle}
            <AutoTextarea
              data-bullet={bullet.id}
              aria-label={`Bullet ${index + 1}`}
              value={bullet.text}
              placeholder="Describe what you did and the result"
              onChange={(e) =>
                onChange(
                  bullets.map((b) =>
                    b.id === bullet.id ? { ...b, text: e.target.value } : b,
                  ),
                )
              }
              onKeyDown={(e) => {
                const el = e.currentTarget;
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  el.selectionStart === el.value.length
                ) {
                  e.preventDefault();
                  addAfter(index);
                } else if (e.key === "Backspace" && bullet.text === "") {
                  e.preventDefault();
                  const next = bullets.filter((b) => b.id !== bullet.id);
                  onRemoveBullet(bullet, next);
                  const prev = bullets[index - 1] ?? bullets[index + 1];
                  if (prev) focusBullet(prev.id);
                }
              }}
            />
            <IconButton
              label="Delete bullet"
              className="re-bullet-delete"
              onClick={() =>
                onRemoveBullet(
                  bullet,
                  bullets.filter((b) => b.id !== bullet.id),
                )
              }
            >
              <Trash2Icon className="size-4" aria-hidden="true" />
            </IconButton>
          </>
        )}
      />
      <button
        type="button"
        className="re-add-inline"
        onClick={() => addAfter(bullets.length - 1)}
      >
        <PlusIcon className="size-3.5" aria-hidden="true" />
        Add bullet
      </button>
    </div>
  );
}

/* -------------------------------------------------------------- item rows */

function ItemShell({
  handle,
  title,
  onRemove,
  children,
}: {
  handle: ReactNode;
  title: string;
  onRemove: () => void;
  children: ReactNode;
}) {
  return (
    <div className="re-item">
      {handle}
      <div className="re-item-body">{children}</div>
      <IconButton label={`Remove ${title}`} onClick={onRemove}>
        <Trash2Icon className="size-4" aria-hidden="true" />
      </IconButton>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="re-empty">{children}</p>;
}

/* --------------------------------------------------------------- sections */

export function SummarySection({ data }: { data: ResumeData }) {
  const { edit } = useEditor();
  return (
    <AutoTextarea
      aria-label="Summary"
      className="re-summary"
      value={data.summary?.text ?? ""}
      placeholder="Two or three sentences on who you are and what you do best"
      onChange={(e) =>
        edit((d) => ({ ...d, summary: { text: e.target.value } }))
      }
    />
  );
}

export function EducationSection({ data }: { data: ResumeData }) {
  const { edit, removeWithUndo } = useEditor();
  const set = (id: string, patch: Partial<ResumeData["education"][number]>) =>
    edit((d) => ({
      ...d,
      education: d.education.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    }));
  if (data.education.length === 0) return <Empty>No education added yet.</Empty>;
  return (
    <SortableList
      items={data.education}
      onReorder={(education) => edit((d) => ({ ...d, education }))}
      rowClassName="re-item-wrap"
      renderRow={(item, _i, handle) => (
        <ItemShell
          handle={handle}
          title={item.institution || "Education"}
          onRemove={() =>
            removeWithUndo(item.institution || "Education", (d) => ({
              ...d,
              education: d.education.filter((e) => e.id !== item.id),
            }))
          }
        >
          <div className="re-grid re-grid-2">
            <Field
              label="School"
              value={item.institution}
              onChange={(v) => set(item.id, { institution: v })}
            />
            <Field
              label="Dates"
              value={item.duration}
              placeholder="2017 - 2021"
              onChange={(v) => set(item.id, { duration: v })}
            />
          </div>
          <Field
            label="Degree"
            value={item.degree}
            onChange={(v) => set(item.id, { degree: v })}
          />
        </ItemShell>
      )}
    />
  );
}

export function ExperienceSection({ data }: { data: ResumeData }) {
  const { edit, removeWithUndo } = useEditor();
  const set = (id: string, patch: Partial<ResumeData["experience"][number]>) =>
    edit((d) => ({
      ...d,
      experience: d.experience.map((e) =>
        e.id === id ? { ...e, ...patch } : e,
      ),
    }));
  if (data.experience.length === 0)
    return <Empty>No experience added yet.</Empty>;
  return (
    <SortableList
      items={data.experience}
      onReorder={(experience) => edit((d) => ({ ...d, experience }))}
      rowClassName="re-item-wrap"
      renderRow={(item, _i, handle) => (
        <ItemShell
          handle={handle}
          title={[item.role, item.company].filter(Boolean).join(", ") || "Job"}
          onRemove={() =>
            removeWithUndo(item.company || "Job", (d) => ({
              ...d,
              experience: d.experience.filter((e) => e.id !== item.id),
            }))
          }
        >
          <div className="re-grid re-grid-2">
            <Field
              label="Role"
              value={item.role}
              onChange={(v) => set(item.id, { role: v })}
            />
            <Field
              label="Company"
              value={item.company}
              onChange={(v) => set(item.id, { company: v })}
            />
          </div>
          <Field
            label="Dates"
            value={item.duration}
            placeholder="Jan 2021 - Mar 2023"
            className="re-field-narrow"
            onChange={(v) => set(item.id, { duration: v })}
          />
          <BulletList
            bullets={item.bullets}
            onChange={(bullets) => set(item.id, { bullets })}
            onRemoveBullet={(bullet, next) =>
              bullet.text.trim()
                ? removeWithUndo("Bullet", (d) => ({
                    ...d,
                    experience: d.experience.map((e) =>
                      e.id === item.id ? { ...e, bullets: next } : e,
                    ),
                  }))
                : set(item.id, { bullets: next })
            }
          />
        </ItemShell>
      )}
    />
  );
}

export function ProjectsSection({ data }: { data: ResumeData }) {
  const { edit, removeWithUndo } = useEditor();
  const set = (id: string, patch: Partial<ResumeData["projects"][number]>) =>
    edit((d) => ({
      ...d,
      projects: d.projects.map((p) => (p.id === id ? { ...p, ...patch } : p)),
    }));
  if (data.projects.length === 0) return <Empty>No projects added yet.</Empty>;
  return (
    <SortableList
      items={data.projects}
      onReorder={(projects) => edit((d) => ({ ...d, projects }))}
      rowClassName="re-item-wrap"
      renderRow={(item, _i, handle) => (
        <ItemShell
          handle={handle}
          title={item.title || "Project"}
          onRemove={() =>
            removeWithUndo(item.title || "Project", (d) => ({
              ...d,
              projects: d.projects.filter((p) => p.id !== item.id),
            }))
          }
        >
          <Field
            label="Project name"
            value={item.title}
            onChange={(v) => set(item.id, { title: v })}
          />
          <Field
            label="Tech used"
            value={item.tech_stack}
            placeholder="Python, Django, PostgreSQL"
            onChange={(v) => set(item.id, { tech_stack: v })}
          />
          <div className="re-grid re-grid-2">
            <Field
              label="GitHub link"
              type="url"
              inputMode="url"
              value={item.github}
              onChange={(v) => set(item.id, { github: v })}
            />
            <Field
              label="Live link"
              type="url"
              inputMode="url"
              value={item.deployed}
              onChange={(v) => set(item.id, { deployed: v })}
            />
          </div>
          <BulletList
            bullets={item.bullets}
            onChange={(bullets) => set(item.id, { bullets })}
            onRemoveBullet={(bullet, next) =>
              bullet.text.trim()
                ? removeWithUndo("Bullet", (d) => ({
                    ...d,
                    projects: d.projects.map((p) =>
                      p.id === item.id ? { ...p, bullets: next } : p,
                    ),
                  }))
                : set(item.id, { bullets: next })
            }
          />
        </ItemShell>
      )}
    />
  );
}

export function AchievementsSection({ data }: { data: ResumeData }) {
  const { edit, removeWithUndo } = useEditor();
  const set = (
    id: string,
    patch: Partial<ResumeData["achievements"][number]>,
  ) =>
    edit((d) => ({
      ...d,
      achievements: d.achievements.map((a) =>
        a.id === id ? { ...a, ...patch } : a,
      ),
    }));
  if (data.achievements.length === 0)
    return <Empty>No achievements added yet.</Empty>;
  return (
    <SortableList
      items={data.achievements}
      onReorder={(achievements) => edit((d) => ({ ...d, achievements }))}
      rowClassName="re-item-wrap"
      renderRow={(item, _i, handle) => (
        <ItemShell
          handle={handle}
          title={item.title || "Achievement"}
          onRemove={() =>
            removeWithUndo(item.title || "Achievement", (d) => ({
              ...d,
              achievements: d.achievements.filter((a) => a.id !== item.id),
            }))
          }
        >
          <Field
            label="Title"
            value={item.title}
            onChange={(v) => set(item.id, { title: v })}
          />
          <BulletList
            bullets={item.bullets}
            onChange={(bullets) => set(item.id, { bullets })}
            onRemoveBullet={(bullet, next) =>
              bullet.text.trim()
                ? removeWithUndo("Bullet", (d) => ({
                    ...d,
                    achievements: d.achievements.map((a) =>
                      a.id === item.id ? { ...a, bullets: next } : a,
                    ),
                  }))
                : set(item.id, { bullets: next })
            }
          />
        </ItemShell>
      )}
    />
  );
}

/* ----------------------------------------------------------------- skills */

function splitSkills(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function SkillChips({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const skills = splitSkills(value);

  const commit = (text: string) => {
    const incoming = splitSkills(text).filter(
      (s) => !skills.some((k) => k.toLowerCase() === s.toLowerCase()),
    );
    if (incoming.length) onChange([...skills, ...incoming].join(", "));
    setDraft("");
  };

  return (
    <div
      className="re-chips"
      onClick={() => inputRef.current?.focus()}
      role="group"
      aria-label={label}
    >
      {skills.map((skill) => (
        <span key={skill} className="re-chip">
          {skill}
          <button
            type="button"
            className="re-chip-x"
            aria-label={`Remove ${skill}`}
            onClick={(e) => {
              e.stopPropagation();
              onChange(skills.filter((s) => s !== skill).join(", "));
            }}
          >
            <XIcon className="size-3" aria-hidden="true" />
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="re-chip-input"
        value={draft}
        placeholder={skills.length ? "Add skill" : "Type a skill, press Enter"}
        aria-label={`Add skill to ${label}`}
        onChange={(e) => {
          const v = e.target.value;
          if (v.includes(",")) commit(v);
          else setDraft(v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit(draft);
          } else if (e.key === "Backspace" && draft === "" && skills.length) {
            onChange(skills.slice(0, -1).join(", "));
          }
        }}
        onBlur={() => draft.trim() && commit(draft)}
      />
    </div>
  );
}

export function SkillsSection({ data }: { data: ResumeData }) {
  const { edit, removeWithUndo } = useEditor();
  const set = (
    id: string,
    patch: Partial<ResumeData["technical_skills"][number]>,
  ) =>
    edit((d) => ({
      ...d,
      technical_skills: d.technical_skills.map((g) =>
        g.id === id ? { ...g, ...patch } : g,
      ),
    }));
  if (data.technical_skills.length === 0)
    return <Empty>No skill groups added yet.</Empty>;
  return (
    <SortableList
      items={data.technical_skills}
      onReorder={(technical_skills) =>
        edit((d) => ({ ...d, technical_skills }))
      }
      rowClassName="re-skill-row"
      renderRow={(group, _i, handle) => (
        <>
          {handle}
          <Field
            label="Group"
            value={group.key}
            placeholder="Languages"
            className="re-skill-key"
            onChange={(v) => set(group.id, { key: v })}
          />
          <div className="re-field re-skill-values">
            <span className="re-label">
              Skills
              <span className="re-count">{splitSkills(group.value).length}</span>
            </span>
            <SkillChips
              label={group.key || "this group"}
              value={group.value}
              onChange={(v) => set(group.id, { value: v })}
            />
          </div>
          <IconButton
            label={`Remove ${group.key || "skill group"}`}
            className="re-skill-delete"
            onClick={() =>
              removeWithUndo(group.key || "Skill group", (d) => ({
                ...d,
                technical_skills: d.technical_skills.filter(
                  (g) => g.id !== group.id,
                ),
              }))
            }
          >
            <Trash2Icon className="size-4" aria-hidden="true" />
          </IconButton>
        </>
      )}
    />
  );
}

/* -------------------------------------------------------- add-item actions */

export const ADD_ACTIONS: Record<
  string,
  { label: string; run: (d: ResumeData) => ResumeData }
> = {
  education: {
    label: "Add school",
    run: (d) => ({ ...d, education: [...d.education, newEducation()] }),
  },
  experience: {
    label: "Add job",
    run: (d) => ({ ...d, experience: [...d.experience, newExperience()] }),
  },
  projects: {
    label: "Add project",
    run: (d) => ({ ...d, projects: [...d.projects, newProject()] }),
  },
  technical_skills: {
    label: "Add skill group",
    run: (d) => ({
      ...d,
      technical_skills: [...d.technical_skills, newSkillGroup()],
    }),
  },
  achievements: {
    label: "Add achievement",
    run: (d) => ({
      ...d,
      achievements: [...d.achievements, newAchievement()],
    }),
  },
};
