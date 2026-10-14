"""Proposal service: diff, apply, and accept/reject logic for resume edits.

A resume edit is driven by IDs, not indexes. The LLM returns a full new
:class:`ResumeData`; we compute the set of atomic changes between the live
structured data and that result, store them on a
:class:`ResumeEditProposal`, and let the user accept/reject each change
individually.

Design rules (see the proposal spec):
- Every list item and bullet carries an ``id``. ``diff`` maps by ID, so
  insertions and reordering never corrupt other items' paths.
- Diffs are independent and atomic. A ``reorder`` change on a parent list
  (e.g. moving an experience entry) is unrelated to the contents of that
  entry; a bullet reorder is unrelated to its siblings. No change depends on
  another being accepted first.
- ``op`` is one of ``replace``, ``add``, ``remove``, or ``reorder``.
- A ``reorder`` change carries the list's ID key and the new ID order in
  ``after``; ``before`` is the previous order. Accepting it reorders the
  existing items in place without touching their contents.
"""

from __future__ import annotations

import uuid

from django.db import transaction

from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import ResumeEditProposal
from betterleaf.resumes.services.latex import render_resume


def new_id() -> str:
    """Return a short, URL-safe change ID."""
    return uuid.uuid4().hex[:8]


def _is_id_list(value) -> bool:
    """True when ``value`` is a list of dicts that all carry an ``id``."""
    return isinstance(value, list) and all(
        isinstance(item, dict) and "id" in item for item in value
    )


def diff(old, new, path: tuple = ()) -> list[dict]:
    """Compute atomic changes between two structured-resume dicts.

    ``old`` and ``new`` are ``ResumeData.model_dump()`` results. ID-bearing
    lists are compared by ID (add/remove/reorder), everything else is compared
    by value (replace).
    """
    changes: list[dict] = []

    if isinstance(old, dict) and isinstance(new, dict):
        for key in old.keys() | new.keys():
            changes += diff(old.get(key), new.get(key), (*path, key))

    elif _is_id_list(old) and _is_id_list(new):
        old_map = {item["id"]: item for item in old}
        new_map = {item["id"]: item for item in new}

        for id_, item in old_map.items():
            if id_ not in new_map:
                changes.append(
                    {
                        "op": "remove",
                        "path": [*path, id_],
                        "before": item,
                        "after": None,
                    },
                )

        # Order change: a single `reorder` change over the items present in
        # BOTH lists — pure reordering of surviving items. Newly added and
        # removed items are handled by their own `add`/`remove` ops and are
        # excluded here so ordering stays independent of membership.
        old_ids = list(old_map)
        new_ids = list(new_map)
        common = [id_ for id_ in new_ids if id_ in old_map]
        common_old = [id_ for id_ in old_ids if id_ in new_map]
        if common != common_old:
            changes.append(
                {
                    "op": "reorder",
                    "path": list(path),
                    "before": common_old,
                    "after": common,
                },
            )

        for id_, item in new_map.items():
            if id_ not in old_map:
                changes.append(
                    {
                        "op": "add",
                        "path": [*path, id_],
                        "before": None,
                        "after": item,
                    },
                )
            else:
                changes += diff(old_map[id_], item, (*path, id_))

    elif old != new:
        changes.append(
            {"op": "replace", "path": list(path), "before": old, "after": new},
        )

    return changes


_STALE_MSG = "stale"


def _find(container, key):
    if isinstance(container, list):
        return next(item for item in container if item["id"] == key)
    return container[key]


def apply_change(data: dict, ch: dict) -> None:
    """Apply one atomic change to ``data`` in place.

    ``path`` always resolves to the *container* the change lives in:

    - ``replace`` / ``add`` / ``remove``: the last segment is the target
      item's ID (list container) or field key (dict container).
    - ``reorder``: the path points directly at the list to reorder.

    Raises :class:`ValueError` when a ``replace`` target no longer matches its
    ``before`` value (the resume was edited manually while the proposal was
    pending). Callers treat that as a stale change to skip/flag.
    """
    op = ch["op"]

    if op == "reorder":
        # The entire path names the list to reorder. Reorder the items whose
        # IDs appear in ``after`` to the front in the given order; keep any
        # items not mentioned (e.g. freshly added by a separate `add` op)
        # after them in their existing relative order.
        parent = data
        for key in ch["path"]:
            parent = _find(parent, key)
        order = list(ch["after"])
        by_id = {item["id"]: item for item in parent}
        kept = [by_id[id_] for id_ in order]
        stragglers = [item for item in parent if item["id"] not in order]
        parent[:] = kept + stragglers
        return

    *parent_path, last = ch["path"]
    parent = data
    for key in parent_path:
        parent = _find(parent, key)

    if op == "replace":
        if isinstance(parent, list):
            _find(parent, last).update(ch["after"])
        else:
            if parent.get(last) != ch["before"]:
                raise ValueError(_STALE_MSG)
            parent[last] = ch["after"]
    elif op == "add":
        # New items append to the end; their id is already present in
        # ``after``, so no positional index is needed.
        parent.append(ch["after"])
    elif op == "remove":
        parent[:] = [item for item in parent if item["id"] != last]
    else:
        msg = f"unknown op: {op}"
        raise ValueError(msg)


def apply_one(data: dict, ch: dict) -> str:
    """Apply a change, returning its final status: ``accepted`` or ``skipped``.

    ``skipped`` means the change's path no longer resolves or its ``before``
    guard failed, so it was left unapplied.
    """
    try:
        apply_change(data, ch)
    except (KeyError, ValueError, StopIteration, IndexError):
        return "skipped"
    return "accepted"


@transaction.atomic
def accept(proposal: ResumeEditProposal, change_ids: list[str]) -> ResumeEditProposal:
    """Apply the accepted changes and re-render the resume's LaTeX.

    Only ``pending`` changes whose IDs are in ``change_ids`` are applied; the
    remaining pending changes are left untouched. Skipped changes (stale /
    path no longer resolvable) are marked ``skipped`` and never touch data.
    The proposal is marked ``applied`` once it has no pending changes left.
    """
    resume = Resume.objects.select_for_update().get(pk=proposal.resume_id)
    data = resume.structured_data
    accepted_ids = set(change_ids)

    for ch in proposal.changes:
        if ch["status"] != "pending":
            continue
        if ch["id"] in accepted_ids:
            ch["status"] = apply_one(data, ch)

    resume.structured_data = data
    resume.main_tex = render_resume(data)
    resume.save(update_fields=["structured_data", "main_tex", "updated_at"])

    if all(ch["status"] != "pending" for ch in proposal.changes):
        proposal.status = ResumeEditProposal.Status.APPLIED
    proposal.save(update_fields=["changes", "status"])

    return proposal


@transaction.atomic
def reject(proposal: ResumeEditProposal, change_ids: list[str]) -> ResumeEditProposal:
    """Mark the named pending changes as rejected; never touch resume data."""
    rejected_ids = set(change_ids)
    for ch in proposal.changes:
        if ch["status"] == "pending" and ch["id"] in rejected_ids:
            ch["status"] = "rejected"

    if all(ch["status"] != "pending" for ch in proposal.changes):
        proposal.status = ResumeEditProposal.Status.APPLIED
    proposal.save(update_fields=["changes", "status"])

    return proposal
