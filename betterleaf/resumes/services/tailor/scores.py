"""Coverage scoring for tailored requirements."""

from betterleaf.resumes.services.tailor.schemas import Requirement

_CREDIT = {"met": 1.0, "partial": 0.5, "not_met": 0.0}


def score_requirements(requirements: list[Requirement]) -> dict[str, dict[str, float]]:
    """Earned vs total points, separately for must-have and nice-to-have."""
    scores = {
        "must_have": {"earned": 0.0, "total": 0},
        "nice_to_have": {"earned": 0.0, "total": 0},
    }
    for req in requirements:
        scores[req.importance]["total"] += 1
        scores[req.importance]["earned"] += _CREDIT[req.status]
    return scores
