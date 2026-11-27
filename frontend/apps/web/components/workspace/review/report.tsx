"use client";

import type { TailorRequirement, TailorScores } from "@/lib/api";

function Score({
  label,
  earned,
  total,
}: {
  label: string;
  earned: number;
  total: number;
}) {
  const pct = total === 0 ? 0 : Math.round((earned / total) * 100);
  return (
    <div className="rv-score">
      <div className="rv-score-top">
        <span className="rv-score-label">{label}</span>
        <span className="rv-score-num">
          {earned} <span className="rv-muted">of {total}</span>
        </span>
      </div>
      <div
        className="rv-bar"
        role="img"
        aria-label={`${label}: ${earned} of ${total} covered`}
      >
        <div className="rv-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Scores({ scores }: { scores: TailorScores }) {
  return (
    <section className="rv-section" aria-label="Coverage score">
      <h2 className="rv-h">How well you match</h2>
      <div className="rv-scores">
        <Score
          label="Must-have"
          earned={scores.must_have.earned}
          total={scores.must_have.total}
        />
        <Score
          label="Nice-to-have"
          earned={scores.nice_to_have.earned}
          total={scores.nice_to_have.total}
        />
      </div>
    </section>
  );
}

function Requirement({ req }: { req: TailorRequirement }) {
  return (
    <li className="rv-req">
      <div className="rv-req-top">
        <span className="rv-req-text">{req.text}</span>
        <span className="rv-tag">
          {req.status === "partial" ? "Partly covered" : "Matched"}
        </span>
      </div>
      {req.rationale && <p className="rv-req-why">{req.rationale}</p>}
      {req.evidence.length > 0 && (
        <ul className="rv-quotes">
          {req.evidence.map((ev) => (
            <li key={`${ev.source_id}-${ev.quote}`}>
              &ldquo;{ev.quote}&rdquo;
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

const byPriority = (a: TailorRequirement, b: TailorRequirement) =>
  a.priority - b.priority;

/** What already matched, folded away so it never gets in the way of the gaps. */
export function MatchedDetails({
  requirements,
}: {
  requirements: TailorRequirement[];
}) {
  const matched = requirements
    .filter((r) => r.status !== "not_met")
    .sort(byPriority);
  if (matched.length === 0) return null;

  return (
    <details className="rv-fold">
      <summary>
        See what already matched{" "}
        <span className="rv-count">{matched.length}</span>
      </summary>
      <ul className="rv-list">
        {matched.map((r) => (
          <Requirement key={r.id} req={r} />
        ))}
      </ul>
    </details>
  );
}

/** The pasted job description, folded away until the user wants to re-read it. */
export function JobDescription({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <details className="rv-fold">
      <summary>See job description</summary>
      <p className="rv-jobtext">{text}</p>
    </details>
  );
}
