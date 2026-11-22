"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import {
  ChevronDownIcon,
  PlusIcon,
  Trash2Icon,
} from "lucide-react";
import { useDocumentStore } from "@/stores/document-store";
import {
  SECTION_KEYS,
  SECTION_TITLES,
  hasResumeData,
  type ResumeData,
  type SectionKey,
} from "@/lib/resume-data";
import {
  EditorProvider,
  Field,
  IconButton,
  SortableList,
  type EditorApi,
} from "./primitives";
import {
  ADD_ACTIONS,
  AchievementsSection,
  EducationSection,
  ExperienceSection,
  ProjectsSection,
  SkillsSection,
  SummarySection,
} from "./sections";
import "@/styles/resume-editor.css";

const SECTION_BODY: Record<SectionKey, (p: { data: ResumeData }) => ReactNode> =
  {
    summary: (p) => <SummarySection {...p} />,
    education: (p) => <EducationSection {...p} />,
    experience: (p) => <ExperienceSection {...p} />,
    projects: (p) => <ProjectsSection {...p} />,
    technical_skills: (p) => <SkillsSection {...p} />,
    achievements: (p) => <AchievementsSection {...p} />,
  };

function sectionCount(data: ResumeData, key: SectionKey): number | null {
  if (key === "summary") return null;
  return data[key].length;
}

/** Remove a section from the page and clear what it held. */
function withoutSection(data: ResumeData, key: SectionKey): ResumeData {
  const next = {
    ...data,
    section_order: data.section_order.filter((k) => k !== key),
  };
  if (key === "summary") next.summary = null;
  else (next[key] as unknown[]) = [];
  return next;
}

function withSection(data: ResumeData, key: SectionKey): ResumeData {
  const next = { ...data, section_order: [...data.section_order, key] };
  if (key === "summary") next.summary = { text: "" };
  return next;
}

export function ResumeEditor({ fileId }: { fileId: string }) {
  const file = useDocumentStore((s) => s.files.find((f) => f.id === fileId));
  const openDraft = useDocumentStore((s) => s.openDraft);
  const editDraft = useDocumentStore((s) => s.editDraft);
  const flushDraft = useDocumentStore((s) => s.flushDraft);
  const [folded, setFolded] = useState<Set<SectionKey>>(new Set());

  useEffect(() => {
    openDraft(fileId);
  }, [fileId, openDraft]);

  // Save whatever is pending when leaving the tab or the page.
  useEffect(() => {
    const flush = () => flushDraft(fileId);
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("pagehide", flush);
      flush();
    };
  }, [fileId, flushDraft]);

  const api = useMemo<EditorApi>(
    () => ({
      edit: (update) => editDraft(fileId, update),
      removeWithUndo: (label, update) => {
        const before = useDocumentStore
          .getState()
          .files.find((f) => f.id === fileId)?.draft;
        editDraft(fileId, update);
        if (!before) return;
        toast(`${label} removed`, {
          action: { label: "Undo", onClick: () => editDraft(fileId, () => before) },
        });
      },
    }),
    [fileId, editDraft],
  );

  const toggle = useCallback((key: SectionKey) => {
    setFolded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  if (!file) return null;

  if (!hasResumeData(file.structuredData)) {
    return (
      <div className="re-root">
        <div className="re-state">
          <h2 className="re-state-title">Nothing to edit here yet</h2>
          <p>
            This resume wasn&apos;t made from an uploaded PDF, so it has no
            form to fill in. You can still edit it in the LaTeX tab.
          </p>
        </div>
      </div>
    );
  }

  const data = file.draft;
  if (!data) {
    return (
      <div className="re-root" aria-busy="true">
        <div className="re-column">
          <div className="re-skeleton" />
          <div className="re-skeleton re-skeleton-tall" />
        </div>
      </div>
    );
  }

  const missing = SECTION_KEYS.filter((k) => !data.section_order.includes(k));

  return (
    <EditorProvider value={api}>
      <div className="re-root">
          <div className="re-column">
          <section className="re-card" aria-label="Name and contact">
            <div className="re-card-body">
              <Field
                label="Full name"
                large
                value={data.name}
                onChange={(name) => api.edit((d) => ({ ...d, name }))}
              />
              <div className="re-grid re-grid-2">
                {(
                  [
                    ["email", "Email", "email", "email"],
                    ["phone", "Phone", "tel", "tel"],
                    ["linkedin", "LinkedIn", "url", "url"],
                    ["github", "GitHub", "url", "url"],
                    ["portfolio", "Portfolio", "url", "url"],
                  ] as const
                ).map(([key, label, type, inputMode]) => (
                  <Field
                    key={key}
                    label={label}
                    type={type}
                    inputMode={inputMode}
                    value={data.contact[key]}
                    onChange={(v) =>
                      api.edit((d) => ({
                        ...d,
                        contact: { ...d.contact, [key]: v },
                      }))
                    }
                  />
                ))}
              </div>
            </div>
          </section>

          <SortableList
            items={data.section_order.map((key) => ({ id: key }))}
            onReorder={(next) =>
              api.edit((d) => ({
                ...d,
                section_order: next.map((n) => n.id as SectionKey),
              }))
            }
            rowClassName="re-section"
            renderRow={({ id }, _i, handle) => {
              const key = id as SectionKey;
              const count = sectionCount(data, key);
              const isFolded = folded.has(key);
              const add = ADD_ACTIONS[key];
              return (
                <section className="re-card" aria-labelledby={`re-h-${key}`}>
                  <header className="re-card-head">
                    {handle}
                    <h2 id={`re-h-${key}`} className="re-card-title">
                      {SECTION_TITLES[key]}
                      {count !== null && (
                        <span className="re-count">{count}</span>
                      )}
                    </h2>
                    <div className="re-card-actions">
                      {add && !isFolded && (
                        <button
                          type="button"
                          className="re-pill"
                          onClick={() => api.edit(add.run)}
                        >
                          <PlusIcon className="size-3.5" aria-hidden="true" />
                          {add.label}
                        </button>
                      )}
                      <IconButton
                        label={`Remove ${SECTION_TITLES[key]} section`}
                        onClick={() =>
                          api.removeWithUndo(
                            `${SECTION_TITLES[key]} section`,
                            (d) => withoutSection(d, key),
                          )
                        }
                      >
                        <Trash2Icon className="size-4" aria-hidden="true" />
                      </IconButton>
                      <button
                        type="button"
                        className="re-icon-btn"
                        aria-expanded={!isFolded}
                        aria-label={`${isFolded ? "Expand" : "Collapse"} ${SECTION_TITLES[key]}`}
                        onClick={() => toggle(key)}
                      >
                        <ChevronDownIcon
                          className={`size-4 re-chevron${isFolded ? " is-folded" : ""}`}
                          aria-hidden="true"
                        />
                      </button>
                    </div>
                  </header>
                  {!isFolded && (
                    <div className="re-card-body">
                      {SECTION_BODY[key]({ data })}
                    </div>
                  )}
                </section>
              );
            }}
          />

          {missing.length > 0 && (
            <div className="re-add-section">
              <span className="re-add-section-label">Add a section</span>
              {missing.map((key) => (
                <button
                  key={key}
                  type="button"
                  className="re-pill"
                  onClick={() => api.edit((d) => withSection(d, key))}
                >
                  <PlusIcon className="size-3.5" aria-hidden="true" />
                  {SECTION_TITLES[key]}
                </button>
              ))}
            </div>
          )}
          </div>
      </div>
    </EditorProvider>
  );
}
