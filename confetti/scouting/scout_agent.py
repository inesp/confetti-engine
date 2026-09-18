import json
from datetime import date

from confetti.models import Conference
from confetti.constants import SCOUT_CHUNK_SIZE
from confetti.constants import SCOUT_LOG
from confetti.constants import SCOUT_MAX_BUDGET_USD
from confetti.constants import SCOUT_MODEL
from confetti.constants import SCOUT_TIMEOUT
from confetti.scouting.claude_runner import clear_stop
from confetti.scouting.claude_runner import extract_json
from confetti.scouting.claude_runner import is_stopped
from confetti.scouting.claude_runner import reset_log
from confetti.scouting.claude_runner import run_claude
from confetti.scouting.claude_runner import stop
from confetti.scouting.confs import ScoutResult
from confetti.yaml.yaml_updater import fill_dates_with_guesses
from confetti.yaml.yaml_updater import update_conf_dates

# Re-export for use by routes
stop_scouting = stop

_DATE_FIELDS = ["cfp_open", "cfp_close", "conference_start", "conference_end"]


def scout_conferences(confs: list[Conference]) -> list[ScoutResult]:
    if not confs:
        return []

    # Scout in small batches: each batch is a fresh Claude session, so the context
    # can't pile up across every conference's website in one long, costly run.
    clear_stop()
    reset_log(SCOUT_LOG)
    results: list[ScoutResult] = []
    for start in range(0, len(confs), SCOUT_CHUNK_SIZE):
        if is_stopped():
            break
        results.extend(_scout_chunk(confs[start : start + SCOUT_CHUNK_SIZE]))
    return results


def _scout_chunk(confs: list[Conference]) -> list[ScoutResult]:
    prompt = _build_prompt(confs)

    try:
        raw = run_claude(
            prompt,
            log_file=SCOUT_LOG,
            timeout=SCOUT_TIMEOUT.total_seconds(),
            model=SCOUT_MODEL,
            max_budget_usd=SCOUT_MAX_BUDGET_USD,
        )
    except FileNotFoundError:
        return [ScoutResult(conf=confs[0], outcome="Error: 'claude' CLI not found")]
    except TimeoutError:
        return [ScoutResult(conf=confs[0], outcome="Error: timed out after 5 minutes")]
    except RuntimeError as e:
        # A stopped run kills the process (exit -9); report it as stopped, not an error.
        if is_stopped():
            return []
        return [ScoutResult(conf=confs[0], outcome=str(e))]

    return _parse_output(confs, raw)


def _parse_output(confs: list[Conference], raw: str) -> list[ScoutResult]:
    confs_by_name = {c.name: c for c in confs}
    results = []

    json_str = extract_json(raw)
    if not json_str:
        return [ScoutResult(conf=confs[0], outcome=raw[:500], raw_response=raw)]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return [ScoutResult(conf=confs[0], outcome="Could not parse JSON response", raw_response=raw)]

    conf_list = data.get("conferences", data) if isinstance(data, dict) else data
    if not isinstance(conf_list, list):
        return [ScoutResult(conf=confs[0], outcome="Unexpected response format", raw_response=raw)]

    for entry in conf_list:
        name = entry.get("name", "")
        conf = confs_by_name.get(name)
        if not conf:
            for cname, c in confs_by_name.items():
                if cname.lower() in name.lower() or name.lower() in cname.lower():
                    conf = c
                    break
        if not conf:
            continue

        dates = {field: entry.get(field) for field in _DATE_FIELDS}
        notify = entry.get("notify") or None
        edition_year = _edition_year(conf)
        parsed_dates = {field: _parse_date(value) for field, value in dates.items()}

        parts = []
        mismatch = _edition_mismatch(parsed_dates, edition_year)
        if mismatch:
            parts.append(f"Nothing written: {mismatch}, looks like another edition")
        else:
            written = _apply_dates(conf, edition_year, parsed_dates, notify)
            found = [(field, value.isoformat()) for field, value in parsed_dates.items() if value]
            if notify:
                found.append(("notify", notify))
            written_parts = [f"{field}: {value}" for field, value in found if field in written]
            already_set = [f"{field}: {value}" for field, value in found if field not in written]
            not_found = [field for field, value in parsed_dates.items() if not value]
            if written_parts:
                parts.append("Written: " + ", ".join(written_parts))
            if already_set:
                parts.append("Already set: " + ", ".join(already_set))
            if not_found:
                parts.append("Not found: " + ", ".join(not_found))
        source = entry.get("source")
        if source:
            parts.append(f"Source: {source}")
        notes = entry.get("notes")
        if notes:
            parts.append(f"Notes: {notes}")

        outcome = "\n".join(parts) if parts else "No dates found"

        results.append(
            ScoutResult(
                conf=conf,
                outcome=outcome,
                found_dates=dates,
                raw_response=json.dumps(entry, indent=2),
            )
        )

    seen = {r.conf.name for r in results}
    for conf in confs:
        if conf.name not in seen:
            results.append(ScoutResult(conf=conf, outcome="Not mentioned in response"))

    return results


def _edition_year(conf: Conference) -> int:
    """The edition to scout: the next one, which is next year's once this year's conference is over."""
    return conf.next_event.edition_year or date.today().year


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _edition_mismatch(dates: dict[str, date | None], edition_year: int) -> str | None:
    """Explain why these dates can't belong to the edition we asked for, or None if they can.

    Sites often still show the edition that just happened. The conference runs in the edition's year,
    its CFP in that year or the one before.
    """
    conference_start = dates["conference_start"]
    if conference_start and conference_start.year != edition_year:
        return f"conference_start {conference_start} is not in {edition_year}"
    for field in ("cfp_open", "cfp_close"):
        value = dates[field]
        if value and value.year not in (edition_year - 1, edition_year):
            return f"{field} {value} is too far from {edition_year}"
    return None


def _apply_dates(conf: Conference, edition_year: int, dates: dict[str, date | None], notify: str | None) -> list[str]:
    written = update_conf_dates(
        conf,
        edition_year,
        cfp_open=dates["cfp_open"],
        cfp_close=dates["cfp_close"],
        conference_start=dates["conference_start"],
        conference_end=dates["conference_end"],
        notify=notify,
    )
    fill_dates_with_guesses(conf, edition_year)
    return written


def _build_prompt(confs: list[Conference]) -> str:
    today = date.today()

    conf_sections = []
    for conf in confs:
        edition_year = _edition_year(conf)
        missing = []
        known = []
        year_entry = conf.years.get(edition_year)
        for field in ["cfp_open", "cfp_close", "conference_start", "conference_end", "notify"]:
            value = getattr(year_entry, field, None) if year_entry else None
            if value:
                known.append(f"  {field}: {value}")
            else:
                missing.append(field)

        section = f"- {conf.name} ({conf.city}, {conf.country}), {edition_year} edition\n"
        section += f"  Website: {conf.website}\n"
        if conf.cfp and conf.cfp.url:
            section += f"  CFP URL: {conf.cfp.url}\n"
        if known:
            section += "  Known:" + ", ".join(known) + "\n"
        section += f"  Missing: {', '.join(missing)}\n"
        conf_sections.append(section)

    return f"""Find missing dates for these conferences. Today is {today.isoformat()}.

Each conference below names the edition to look for. Websites and CFP links often still show the edition that
already happened; its dates don't count. Set them to null.

For each conference, visit its website and find: cfp_open, cfp_close, conference_start, conference_end dates.
Only report dates you actually find on the website. Don't guess. Set unfound dates to null.

Also find "notify": when speakers hear back about their submission (the decision / notification date).
This is free text, not a single date, because conferences word it differently and often have several dates
(e.g. "Notifications by 5 Apr" or "review ends 10 Aug; 1st round 25 Aug, 2nd round 10 Sep"). Copy what they
publish, kept short. Set to null if the site says nothing about when decisions are announced.

Conferences to scout:
{"".join(conf_sections)}

Respond with JSON in this exact format:
{{"conferences": [{{"name": "Conference Name", "cfp_open": "YYYY-MM-DD or null", "cfp_close": "YYYY-MM-DD or null", "conference_start": "YYYY-MM-DD or null", "conference_end": "YYYY-MM-DD or null", "notify": "short free text or null", "source": "URL", "notes": "any context"}}]}}
"""
