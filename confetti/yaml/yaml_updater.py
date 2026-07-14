from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from confetti.models import Conference

_yaml = YAML()
_yaml.preserve_quotes = True
# Never wrap long scalars onto continuation lines; editors soft-wrap for display.
_yaml.width = 1_000_000


@contextmanager
def _edit_conf(conf: Conference) -> Iterator[dict | None]:
    """Load the conference's YAML entry, yield it for mutation, then write it back.

    Yields None (and writes nothing) when the conference isn't found in its file, so
    callers only need `if entry is None: return` instead of hand-rolling load and write.
    """
    data, entry = _find_conf(conf)
    if data is None or entry is None:
        yield None
        return
    yield entry
    _write(conf.filepath, data)


@contextmanager
def _edit_year(conf: Conference, year: int) -> Iterator[dict | None]:
    """Like _edit_conf, but ensure the year section exists and yield that year's dict."""
    data, entry = _find_conf(conf)
    if data is None or entry is None:
        yield None
        return
    _ensure_year(entry, year)
    yield entry["years"][year]
    _write(conf.filepath, data)


def add_conference(conf: Conference) -> None:
    """Add a conference to its YAML file, creating the file if needed."""
    filepath = conf.filepath
    if filepath.exists():
        with open(filepath) as f:
            data = _yaml.load(f)
        if not isinstance(data, list):
            data = []
    else:
        data = []

    entry = conf.model_dump(exclude={"filename"}, exclude_none=True)
    data.append(entry)
    _write(filepath, data)


def backfill_presumed_dates(conferences: list[Conference]) -> None:
    year = date.today().year
    for conf in conferences:
        fill_dates_with_guesses(conf, year)


def fill_dates_with_guesses(conf: Conference, year: int) -> None:
    """Set cfp.presumed_open/close from actual year dates if not already set."""
    year_entry = conf.years.get(year)
    if year_entry is None:
        return

    cfp = conf.cfp
    updates: dict[str, str] = {}
    if year_entry.cfp_open and (not cfp or not cfp.presumed_open):
        updates["presumed_open"] = year_entry.cfp_open.strftime("%m-%d")
    if year_entry.cfp_close and (not cfp or not cfp.presumed_close):
        updates["presumed_close"] = year_entry.cfp_close.strftime("%m-%d")

    if not updates:
        return

    with _edit_conf(conf) as entry:
        if entry is None:
            return
        if "cfp" not in entry or entry["cfp"] is None:
            entry["cfp"] = {}
        for field, value in updates.items():
            entry["cfp"][field] = value


def update_conf_dates(
    conf: Conference,
    year: int,
    cfp_open: date | None = None,
    cfp_close: date | None = None,
    conference_start: date | None = None,
    conference_end: date | None = None,
    notify: str | None = None,
) -> None:
    """Update actual dates for a conference year. Only sets missing fields."""
    dates = {
        "cfp_open": cfp_open,
        "cfp_close": cfp_close,
        "conference_start": conference_start,
        "conference_end": conference_end,
        "notify": notify,
    }
    dates = {field: value for field, value in dates.items() if value is not None}
    if not dates:
        return

    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        for field, value in dates.items():
            if field not in year_data or year_data[field] is None:
                year_data[field] = value


def update_cfp_url(conf: Conference, url: str | None) -> None:
    """Set (or clear) the CFP submission URL for a conference."""
    with _edit_conf(conf) as entry:
        if entry is None:
            return
        if entry.get("cfp") is None:
            entry["cfp"] = {}
        entry["cfp"]["url"] = url or None


def update_favorite(conf: Conference, favorite: bool) -> None:
    """Set the top-level favorite flag for a conference."""
    with _edit_conf(conf) as entry:
        if entry is None:
            return
        if favorite:
            _set_after(entry, "favorite", True, after="website")
        else:
            entry.pop("favorite", None)


def update_difficulty(conf: Conference, difficulty: str | None) -> None:
    """Set (or clear) the conference's longshot marker (stored in `difficulty`)."""
    with _edit_conf(conf) as entry:
        if entry is None:
            return
        entry["difficulty"] = difficulty if difficulty else None


def update_year_skip(conf: Conference, year: int, skip: bool) -> None:
    """Set the skip flag for a single conference year (edition)."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        if skip:
            year_data["skip"] = True
        else:
            year_data.pop("skip", None)


def update_cfp_window(conf: Conference, year: int, cfp_open: date | None, cfp_close: date | None) -> None:
    """Set (or clear) the CFP open and close dates for a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        for field, value in (("cfp_open", cfp_open), ("cfp_close", cfp_close)):
            if value is None:
                year_data.pop(field, None)
            else:
                year_data[field] = value


def update_talk_status(conf: Conference, year: int, talk_id: str, status: str) -> None:
    """Update the status of a specific talk for a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        for talk in year_data.get("talks", []):
            if talk.get("talk") == talk_id:
                talk["status"] = status
                break


def update_talk_title(conf: Conference, year: int, talk_id: str, title: str) -> None:
    """Update the submission title of a specific talk for a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        for talk in year_data.get("talks", []) or []:
            if talk.get("talk") == talk_id:
                talk["title"] = title
                break


def add_talk(conf: Conference, year: int, talk_id: str, title: str) -> None:
    """Append a new submitted talk to a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        talks = year_data.get("talks")
        if talks is None:
            talks = []
            year_data["talks"] = talks

        new_talk = {"talk": talk_id, "status": "submitted"}
        if title:
            new_talk["title"] = title
        talks.append(new_talk)


def update_talk_time(
    conf: Conference,
    year: int,
    talk_id: str,
    talk_start: datetime | None,
    talk_duration: int,
    schedule_notes: str,
) -> None:
    """Update talk_start, talk_duration, and schedule_notes for a specific talk."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        for talk in year_data.get("talks", []):
            if talk.get("talk") == talk_id:
                if talk_start:
                    talk["talk_start"] = talk_start.strftime("%Y-%m-%d %H:%M")
                elif "talk_start" in talk:
                    del talk["talk_start"]
                talk["talk_duration"] = talk_duration
                if schedule_notes:
                    talk["schedule_notes"] = schedule_notes
                elif "schedule_notes" in talk:
                    del talk["schedule_notes"]
                break


def update_vacation_days(conf: Conference, year: int, vacation_days: int) -> None:
    """Update vacation_days for a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        year_data["vacation_days"] = vacation_days


def update_cost(
    conf: Conference,
    year: int,
    flight: float | None,
    hotel: float | None,
    extra: float | None,
    promised: float | None,
    covered: float | None,
) -> None:
    """Update cost fields for a conference year."""
    with _edit_year(conf, year) as year_data:
        if year_data is None:
            return
        if year_data.get("cost") is None:
            year_data["cost"] = {}
        cost = year_data["cost"]
        cost["flight"] = flight
        cost["hotel"] = hotel
        cost["extra"] = extra
        cost["promised"] = promised
        cost["covered"] = covered


def update_skip(conf: Conference, skip: bool) -> None:
    """Set the top-level skip flag for a conference."""
    with _edit_conf(conf) as entry:
        if entry is None:
            return
        if skip:
            _set_after(entry, "skip", True, after="website")
        else:
            entry.pop("skip", None)


def _find_conf(conf: Conference) -> tuple[list | None, dict | None]:
    filename = conf.filename
    assert filename, "No filename given"

    with open(conf.filepath) as f:
        data: list | Any = _yaml.load(f)

    assert isinstance(data, list), f"File {conf.filepath} has faulty data, it should be a list"

    for entry in data:
        if entry.get("name") == conf.name:
            return data, entry

    return None, None


def _set_after(mapping: Any, key: str, value: Any, after: str) -> None:
    """Set key=value, inserting a brand-new key right after `after` instead of appending."""
    if key in mapping:
        mapping[key] = value
        return

    keys = list(mapping.keys())
    index = keys.index(after) + 1 if after in keys else len(keys)
    mapping.insert(index, key, value)


def _ensure_year(entry: dict, year: int) -> None:
    """Make sure the years section and year entry exist."""
    if "years" not in entry or entry["years"] is None:
        entry["years"] = {}
    if year not in entry["years"] or entry["years"][year] is None:
        entry["years"][year] = {}


def _strip_blank_lines(node: Any) -> None:
    """Drop blank-line/comment tokens so each conference renders compact, no inner gaps."""
    comments = getattr(node, "ca", None)
    if comments is not None:
        comments.items.clear()
        comments.comment = None
    if isinstance(node, dict):
        for value in node.values():
            _strip_blank_lines(value)
    elif isinstance(node, list):
        for item in node:
            _strip_blank_lines(item)


def _write(filepath: Path, data: list) -> None:
    # Compact each conference (no blank lines within), then one blank line between them.
    _strip_blank_lines(data)
    for i in range(1, len(data)):
        data[i].yaml_set_start_comment("\n", indent=0)

    stream = StringIO()
    _yaml.dump(data, stream)

    with open(filepath, "w") as f:
        f.write(stream.getvalue())
