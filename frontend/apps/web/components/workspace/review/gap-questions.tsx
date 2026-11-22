"use client";

import { useId } from "react";
import { toast } from "sonner";
import { LoaderIcon } from "lucide-react";
import type {
  AnswerTarget,
  GapAnswerInput,
  GapQuestion,
  SourceType,
  TailorRequirement,
  TailorRequestDto,
} from "@/lib/api";
import { submitAnswers, useTailorStore } from "@/stores/tailor-store";
import { AutoTextarea } from "../resume-editor/primitives";

const GROUPS: { type: SourceType; label: string }[] = [
  { type: "experience", label: "Jobs" },
  { type: "projects", label: "Projects" },
  { type: "achievements", label: "Achievements" },
];

const targetKey = (t: AnswerTarget) => `${t.source_type}:${t.item_id}`;

function Question({
  requestId,
  gap,
  requirement,
  targets,
  disabled,
}: {
  requestId: string;
  gap: GapQuestion;
  requirement: TailorRequirement | undefined;
  targets: AnswerTarget[];
  disabled: boolean;
}) {
  const id = useId();
  const draft = useTailorStore(
    (s) => s.answers[requestId]?.[gap.requirement_id],
  );
  const setAnswer = useTailorStore((s) => s.setAnswer);
  const patch = (p: { target?: string; text?: string }) =>
    setAnswer(requestId, gap.requirement_id, p);

  return (
    <li className="rv-card">
      <span
        className={`rv-tag${requirement?.importance === "must_have" ? "rv-tag-must" : ""}`}
      >
        {requirement?.importance === "must_have" ? "Must-have" : "Good to have"}
      </span>
      <p className="rv-q">{requirement?.text ?? gap.question}</p>
      {requirement && <p className="rv-hint">{gap.question}</p>}
      {targets.length === 0 ? (
        <p className="rv-hint">
          Add a job, project or achievement to your resume first, then you can
          answer this.
        </p>
      ) : (
        <>
          <div className="rv-field">
            <label htmlFor={`${id}-answer`} className="re-label">
              Your answer (leave empty to skip)
            </label>
            <AutoTextarea
              id={`${id}-answer`}
              disabled={disabled}
              value={draft?.text ?? ""}
              placeholder="A sentence or two is enough."
              onChange={(e) => patch({ text: e.target.value })}
            />
          </div>
          <div className="rv-field">
            <label htmlFor={`${id}-where`} className="re-label">
              Where was this?
            </label>
            <select
              id={`${id}-where`}
              className="re-input rv-select"
              disabled={disabled}
              value={draft?.target || targetKey(targets[0])}
              onChange={(e) => patch({ target: e.target.value })}
            >
              {GROUPS.map(({ type, label }) => {
                const inGroup = targets.filter((t) => t.source_type === type);
                return inGroup.length === 0 ? null : (
                  <optgroup key={type} label={label}>
                    {inGroup.map((t) => (
                      <option key={targetKey(t)} value={targetKey(t)}>
                        {t.label}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          </div>
        </>
      )}
    </li>
  );
}

export function GapQuestions({ dto }: { dto: TailorRequestDto }) {
  const answers = useTailorStore((s) => s.answers[dto.id]);
  const gaps = dto.gap_questions ?? [];
  const targets = dto.answer_targets ?? [];
  const drafting = dto.status === "drafting";
  const reqs = Object.fromEntries(
    (dto.requirements ?? []).map((r) => [r.id, r]),
  );

  if (gaps.length === 0) {
    return (
      <section className="rv-section" aria-label="Gaps">
        <h2 className="rv-h">Nothing is missing</h2>
        <p className="rv-hint">
          Your resume covers everything the job asks for.
        </p>
      </section>
    );
  }

  const ready: GapAnswerInput[] = [];
  for (const gap of gaps) {
    const draft = answers?.[gap.requirement_id];
    const text = draft?.text.trim();
    if (!text || targets.length === 0) continue;
    const key = draft?.target || targetKey(targets[0]);
    const [source_type, ...rest] = key.split(":");
    ready.push({
      requirement_id: gap.requirement_id,
      source_type: source_type as SourceType,
      item_id: rest.join(":"),
      text,
    });
  }

  const send = async () => {
    try {
      await submitAnswers(dto.id, ready);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  return (
    <section className="rv-section" aria-label="Gaps">
      <h2 className="rv-h">
        What&apos;s missing <span className="rv-count">{gaps.length}</span>
      </h2>
      <p className="rv-hint">
        Answer any you like and skip the rest. Only what you write is used.
      </p>
      <ul className="rv-list">
        {gaps.map((gap) => (
          <Question
            key={gap.requirement_id}
            requestId={dto.id}
            gap={gap}
            requirement={reqs[gap.requirement_id]}
            targets={targets}
            disabled={drafting}
          />
        ))}
      </ul>
      <div className="rv-actions">
        <button
          type="button"
          className="rv-primary"
          disabled={drafting || ready.length === 0}
          onClick={send}
        >
          {drafting ? (
            <>
              <LoaderIcon className="re-spin size-4" aria-hidden="true" />
              Writing bullets…
            </>
          ) : (dto.proposals?.length ?? 0) > 0 ? (
            "Draft again"
          ) : (
            `Draft bullets${ready.length ? ` (${ready.length})` : ""}`
          )}
        </button>
      </div>
    </section>
  );
}
