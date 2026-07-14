import logging
from dataclasses import dataclass
from enum import StrEnum, auto
from pathlib import Path

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from confetti.constants import CONFERENCES_DIR
from confetti.constants import TALKS_FILE
from confetti.models import Conference
from confetti.models import Talk
from confetti.models import TalkStatus

logger = logging.getLogger(__name__)


class ErrorLevel(StrEnum):
    error = auto()
    warning = auto()


@dataclass
class ConfError:
    file: str
    conference: str
    errors: list[str]
    level: ErrorLevel = ErrorLevel.error


# Cache of (sources fingerprint, result). Recomputed only when a conference YAML
# file or talks.yml is added, removed, or modified, so the per-request nav check
# (app.py context processor) doesn't re-parse every file on every page load.
_cache: tuple[tuple, tuple[list[Conference], list[ConfError]]] | None = None


def _sources_fingerprint() -> tuple:
    parts = [(f.name, f.stat().st_mtime_ns) for f in sorted(CONFERENCES_DIR.glob("*.yaml"))]
    if TALKS_FILE.exists():
        parts.append((TALKS_FILE.name, TALKS_FILE.stat().st_mtime_ns))
    return tuple(parts)


def load_and_validate_conferences() -> tuple[list[Conference], list[ConfError]]:
    """Load all conference YAML files and validate them, cached by file mtime.

    Returns (conferences, errors). Writes to any YAML file change its mtime and so
    invalidate the cache, so callers always see fresh data after an edit.
    """
    global _cache
    fingerprint = _sources_fingerprint()
    if _cache is None or _cache[0] != fingerprint:
        _cache = (fingerprint, _load_and_validate_conferences())
    conferences, errors = _cache[1]
    # Return copies so callers can't mutate the cached lists (the home page appends
    # its own warnings, which would otherwise pile up in the cache on every view).
    return list(conferences), list(errors)


def _load_and_validate_conferences() -> tuple[list[Conference], list[ConfError]]:
    all_conferences: list[Conference] = []
    all_errors: list[ConfError] = []

    yml_files = sorted(CONFERENCES_DIR.glob("*.yaml"))
    yml_files = [f for f in yml_files if f.name not in ("template.yaml", "skipped.yaml")]

    if not yml_files:
        return [], [ConfError("conferences/", "-", ["No .yaml files found"])]

    for yml_file in yml_files:
        conferences, errors = _load_one_yml_file(yml_file)
        all_conferences.extend(conferences)
        all_errors.extend(errors)

    # Validate skipped.yaml if it exists
    skipped_file = CONFERENCES_DIR / "skipped.yaml"
    if skipped_file.exists():
        all_errors.extend(_validate_skipped_file(skipped_file))

    # Post-load validation
    known_talks = load_talks()
    known_talk_ids = {t.id for t in known_talks}
    ids_hint = " | ".join(t.id for t in known_talks) if known_talks else "your-talk-id"

    for conf in all_conferences:
        # #14: a cfp block should have presumed open/close dates so the pipeline can estimate timing
        if conf.cfp:
            missing_dates = [
                name
                for name, value in (
                    ("presumed_open", conf.cfp.presumed_open),
                    ("presumed_close", conf.cfp.presumed_close),
                )
                if not value
            ]
            if missing_dates:
                all_errors.append(
                    ConfError(
                        conf.filename,
                        conf.name,
                        [
                            f"CFP is missing {' and '.join(missing_dates)}. Fill in:\n"
                            + "\n".join(f"      {name}: MM-DD" for name in missing_dates)
                        ],
                        level=ErrorLevel.warning,
                    )
                )

        for year, entry in (conf.years or {}).items():
            if entry is None:
                continue

            # #1: Accepted talk → conference dates required
            if entry.status == TalkStatus.accepted and not entry.conference_start:
                all_errors.append(
                    ConfError(
                        conf.filename,
                        conf.name,
                        [
                            f"Year {year} has accepted talks but no conference dates. Add:\n"
                            f"      conference_start: {year}-MM-DD\n"
                            f"      conference_end: {year}-MM-DD"
                        ],
                    )
                )

            # #4: Accepted talks → cost required
            if entry.status == TalkStatus.accepted and not entry.cost:
                all_errors.append(
                    ConfError(
                        conf.filename,
                        conf.name,
                        [
                            f"Year {year} has accepted talks but no cost. Add:\n"
                            f"      cost:\n"
                            f"        flight:\n"
                            f"        hotel:\n"
                            f"        extra:\n"
                            f"        covered:"
                        ],
                        level=ErrorLevel.warning,
                    )
                )

            # #9: Duplicate talk ID in same year
            talk_ids = [t.talk for t in entry.talks]
            seen = set()
            for talk_id in talk_ids:
                if talk_id in seen:
                    all_errors.append(
                        ConfError(
                            conf.filename,
                            conf.name,
                            [f"Year {year} has duplicate talk '{talk_id}'"],
                        )
                    )
                seen.add(talk_id)

            # #12: Accepted year entries must have vacation_days set
            if entry.status == TalkStatus.accepted and entry.vacation_days == 0:
                all_errors.append(
                    ConfError(
                        conf.filename,
                        conf.name,
                        [f"Year {year} has accepted talk but no vacation_days. Add:\n" f"      vacation_days: 1"],
                        level=ErrorLevel.warning,
                    )
                )

            for talk in entry.talks:
                # #11: Talk IDs must reference existing talks
                if talk.talk not in known_talk_ids:
                    all_errors.append(
                        ConfError(
                            conf.filename,
                            conf.name,
                            [f"Year {year} references unknown talk '{talk.talk}'. Available talk IDs: {ids_hint}"],
                        )
                    )
                # #13: talk_start must fall within conference dates
                if talk.talk_start and entry.conference_start:
                    talk_date = talk.talk_start.date()
                    conf_end = entry.conference_end or entry.conference_start
                    if talk_date < entry.conference_start or talk_date > conf_end:
                        all_errors.append(
                            ConfError(
                                conf.filename,
                                conf.name,
                                [
                                    f"Year {year}, talk '{talk.talk}' is scheduled on {talk_date}"
                                    f" but conference runs {entry.conference_start} to {conf_end}"
                                ],
                            )
                        )
                # #10: All talks need a title
                if not talk.title:
                    all_errors.append(
                        ConfError(
                            conf.filename,
                            conf.name,
                            [
                                f"Year {year}, talk '{talk.talk}' has no title. Add:\n"
                                f'          title: "The title you submitted it as"'
                            ],
                            level=ErrorLevel.warning,
                        )
                    )

    return all_conferences, all_errors


def _validate_skipped_file(skipped_file: Path) -> list[ConfError]:
    """Validate that skipped.yaml is a well-formed list of strings."""
    try:
        data = yaml.safe_load(skipped_file.read_text())
    except yaml.YAMLError as e:
        return [ConfError("skipped.yaml", "-", [f"YAML parse error: {e}"])]
    if data is None:
        return []
    if not isinstance(data, list):
        return [ConfError("skipped.yaml", "-", [f"Expected a list, got {type(data).__name__}"])]
    bad = [str(item) for item in data if not isinstance(item, str)]
    if bad:
        return [ConfError("skipped.yaml", "-", [f"Non-string entries: {', '.join(bad)}"], level=ErrorLevel.warning)]
    return []


def _load_one_yml_file(yml_file: Path) -> tuple[list[Conference], list[ConfError]]:
    filename = yml_file.name
    try:
        with open(yml_file) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [], [ConfError(filename, "-", [f"YAML parse error: {e}"])]

    if not data:
        return [], []

    if not isinstance(data, list):
        return [], [ConfError(filename, "-", ["File must contain a list of conferences"])]

    conferences: list[Conference] = []
    errors: list[ConfError] = []

    for i, raw_conf in enumerate(data):
        conf_name = raw_conf.get("name", f"entry #{i + 1}") if isinstance(raw_conf, dict) else f"entry #{i + 1}"
        try:
            conferences.append(Conference(**raw_conf, filename=filename))
        except ValidationError as e:
            problems = [_summarize_error(err) for err in e.errors()]
            errors.append(ConfError(filename, conf_name, problems))
        except TypeError as e:
            errors.append(ConfError(filename, conf_name, [str(e)]))

    return conferences, errors


def load_talks() -> list[Talk]:
    """Load talk definitions from talks/talks.yml."""
    if not TALKS_FILE.exists():
        return []
    with open(TALKS_FILE) as f:
        data = yaml.safe_load(f)
    if not data or not isinstance(data, list):
        return []
    return [Talk(**t) for t in data]


def _summarize_error(err: ErrorDetails) -> str:
    field = ".".join(str(loc) for loc in err["loc"])
    error_type = err["type"]

    match error_type:
        case "missing":
            return f"'{field}' is required"
        case "extra_forbidden":
            return f"'{field}' is not a valid field"
        case "enum":
            return f"'{field}' must be one of: {', '.join(TalkStatus)}"
        case "bool_parsing":
            return f"'{field}' must be true or false"
        case s if "date" in s:
            return f"'{field}' must be a date (YYYY-MM-DD)"
        case _:
            return f"'{field}': {err['msg']}"
