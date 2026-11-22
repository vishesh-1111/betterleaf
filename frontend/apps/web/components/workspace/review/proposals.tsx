"use client";

import { useId, useState } from "react";
import { toast } from "sonner";
import { LoaderIcon } from "lucide-react";
import type {
  AcceptedProposalInput,
  GapProposal,
  TailorRequestDto,
} from "@/lib/api";
import {
  confirmAccepted,
  useTailorStore,
  type ProposalEdit,
} from "@/stores/tailor-store";
import { AutoTextarea } from "../resume-editor/primitives";

function Proposal({
  requestId,
  proposal,
  where,
  edit,
}: {
  requestId: string;
  proposal: GapProposal;
  where: string;
  edit: ProposalEdit | undefined;
}) {
  const id = useId();
  const setEdit = useTailorStore((s) => s.setEdit);

  if (proposal.change === "no_change") {
    return (
      <li className="rv-card rv-card-quiet">
        <p className="rv-q-req">{proposal.requirement_text}</p>
        <p className="rv-hint">
          Nothing added. {proposal.reason || "The answer was too thin to use."}
        </p>
      </li>
    );
  }

  const accepted = edit?.accepted ?? true;
  return (
    <li className={`rv-card${accepted ? "" : "rv-card-off"}`}>
      <p className="rv-q-req">{proposal.requirement_text}</p>
      <p className="rv-hint">Goes under {where}</p>
      <label htmlFor={id} className="re-label">
        New bullet
      </label>
      <AutoTextarea
        id={id}
        disabled={!accepted}
        value={edit?.bullet ?? proposal.bullet}
        onChange={(e) =>
          setEdit(requestId, proposal.id, { bullet: e.target.value })
        }
      />
      {proposal.skill && (
        <p className="rv-hint">
          Also adds the skill &ldquo;{proposal.skill}&rdquo;.
        </p>
      )}
      <label className="rv-check">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) =>
            setEdit(requestId, proposal.id, { accepted: e.target.checked })
          }
        />
        Add this to my resume
      </label>
    </li>
  );
}

export function Proposals({
  dto,
  fileId,
  onEditAnswers,
}: {
  dto: TailorRequestDto;
  fileId: string;
  onEditAnswers: () => void;
}) {
  const edits = useTailorStore((s) => s.edits[dto.id]);
  const [saving, setSaving] = useState(false);
  const proposals = dto.proposals ?? [];
  if (proposals.length === 0 || dto.status === "drafting") return null;

  const labels = Object.fromEntries(
    (dto.answer_targets ?? []).map((t) => [
      `${t.source_type}:${t.item_id}`,
      t.label,
    ]),
  );

  const kept: AcceptedProposalInput[] = [];
  let blank = false;
  for (const p of proposals) {
    if (
      p.change !== "add_bullet" ||
      (edits?.[p.id]?.accepted ?? true) === false
    )
      continue;
    const bullet = (edits?.[p.id]?.bullet ?? p.bullet).trim();
    if (!bullet) blank = true;
    kept.push({
      id: p.id,
      bullet,
      skill: p.skill,
      skill_group_id: p.skill_group_id,
    });
  }

  const confirm = async () => {
    setSaving(true);
    try {
      await confirmAccepted(dto.id, fileId, kept);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
      setSaving(false);
    }
  };

  return (
    <section className="rv-section" aria-label="Proposed bullets">
      <h2 className="rv-h">
        Bullets drafted from your answers{" "}
        <span className="rv-count">{proposals.length}</span>
      </h2>
      <p className="rv-hint">
        Edit the wording, or untick one to leave it out. Nothing is saved until
        you confirm.{" "}
        <button type="button" className="rv-link" onClick={onEditAnswers}>
          Edit my answers
        </button>
      </p>
      <ul className="rv-list">
        {proposals.map((p) => (
          <Proposal
            key={p.id}
            requestId={dto.id}
            proposal={p}
            where={labels[`${p.source_type}:${p.item_id}`] ?? "your resume"}
            edit={edits?.[p.id]}
          />
        ))}
      </ul>
      <div className="rv-confirm">
        <button
          type="button"
          className="rv-primary"
          disabled={saving || kept.length === 0 || blank}
          onClick={confirm}
        >
          {saving ? (
            <>
              <LoaderIcon className="re-spin size-4" aria-hidden="true" />
              Saving…
            </>
          ) : (
            `Add ${kept.length} bullet${kept.length === 1 ? "" : "s"} and tailor again`
          )}
        </button>
      </div>
    </section>
  );
}
