import type { Change } from "@/lib/api";

/**
 * Map a proposal's atomic changes to the plain-text fragments that should be
 * highlighted in the preview. We highlight the *new* content only ("what's
 * new"), so we read the `after` side of each change.
 *
 * A single change can carry a scalar string (a replaced field) or a nested
 * object/list (an added item with many text fields). We walk any structure and
 * collect its leaf string values, dropping very short fragments that would
 * produce noisy, near-universal matches in the PDF text layer.
 */

const MIN_FRAGMENT_LENGTH = 4;

/** Leaf string values inside an arbitrary JSON structure. */
function collectStrings(value: unknown, out: string[]): void {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.length >= MIN_FRAGMENT_LENGTH) out.push(trimmed);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, out);
    return;
  }
  if (value && typeof value === "object") {
    for (const item of Object.values(value as Record<string, unknown>)) {
      collectStrings(item, out);
    }
  }
}

/**
 * IDs of structural keys to skip when collecting text from an item's `after`.
 * IDs are opaque hex strings, not user text; including them would match nothing
 * useful in the PDF and can produce spurious highlights.
 */
function collectChangeText(ch: Change, out: string[]): void {
  if (ch.op === "remove" || ch.op === "reorder") return; // no new text
  if (ch.after == null) return;

  if (ch.op === "replace") {
    // `after` is the new scalar/object value.
    collectStrings(ch.after, out);
    return;
  }

  // `add`: `after` is a whole new item; skip its "id" field and collect the
  // remaining text fields.
  const after = ch.after as Record<string, unknown>;
  if (Array.isArray(after)) {
    collectStrings(after, out);
    return;
  }
  if (after && typeof after === "object") {
    for (const [key, value] of Object.entries(after)) {
      if (key === "id") continue;
      collectStrings(value, out);
    }
    return;
  }
  collectStrings(after, out);
}

/** Unique, de-duplicated highlight fragments for a set of changes. */
export function extractHighlightFragments(changes: Change[]): string[] {
  const fragments: string[] = [];
  for (const ch of changes) collectChangeText(ch, fragments);
  // De-duplicate while preserving order.
  return [...new Set(fragments)];
}
