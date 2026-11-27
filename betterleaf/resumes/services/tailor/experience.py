"""Total work experience from the master resume's experience durations."""

import re
from datetime import date

_MONTHS = {
    m: i
    for i, names in enumerate(
        ["jan january", "feb february", "mar march", "apr april", "may",
         "jun june", "jul july", "aug august", "sep sept september",
         "oct october", "nov november", "dec december"],
        start=1,
    )
    for m in names.split()
}
_DATE = re.compile(
    r"(?:(?P<month>[A-Za-z]{3,9})\.?,?\s+)?(?P<year>(?:19|20)\d{2})|(?P<now>present|current|now|ongoing|today)",
    re.IGNORECASE,
)
_YEARS = re.compile(r"(\d+(?:\.\d+)?)")


def _to_index(match: re.Match, *, end: bool, today: date) -> int:
    """Month number since year 0; a bare year spans Jan (start) to Dec (end)."""
    if match.group("now"):
        return today.year * 12 + today.month
    month = _MONTHS.get((match.group("month") or "").lower())
    if month is None:
        month = 12 if end else 1
    return int(match.group("year")) * 12 + month


def duration_to_range(duration: str, today: date) -> tuple[int, int] | None:
    found = list(_DATE.finditer(duration or ""))
    if not found:
        return None
    start = _to_index(found[0], end=False, today=today)
    stop = _to_index(found[-1], end=True, today=today) if len(found) > 1 else start
    if len(found) == 1 and not found[0].group("now"):
        stop = start + 1  # a lone date counts as one month
    return (start, stop) if stop >= start else None


def total_experience_years(master_data: dict, today: date | None = None) -> float:
    """Years across all experience entries, overlapping spans counted once."""
    today = today or date.today()
    ranges = sorted(
        r
        for item in master_data.get("experience") or []
        if (r := duration_to_range(item.get("duration", ""), today))
    )
    months = 0
    cur_start = cur_end = None
    for start, stop in ranges:
        if cur_end is None or start > cur_end:
            if cur_end is not None:
                months += cur_end - cur_start
            cur_start, cur_end = start, stop
        else:
            cur_end = max(cur_end, stop)
    if cur_end is not None:
        months += cur_end - cur_start
    return round(months / 12, 1)


def required_years(text: str) -> float | None:
    """Years from strings like '3 years' or '5+ years'; None for 'Not Mentioned'."""
    match = _YEARS.search(text or "")
    return float(match.group(1)) if match else None
