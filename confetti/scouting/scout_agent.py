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

        dates = {
            "cfp_open": entry.get("cfp_open"),
            "cfp_close": entry.get("cfp_close"),
            "conference_start": entry.get("conference_start"),
            "conference_end": entry.get("conference_end"),
        }

        notify = entry.get("notify")

        found = [f"{k}: {v}" for k, v in dates.items() if v]
        if notify:
            found.append(f"notify: {notify}")
        not_found = [k for k, v in dates.items() if not v]

        parts = []
        if found:
            parts.append("Found: " + ", ".join(found))
        if not_found:
            parts.append("Not found: " + ", ".join(not_found))
        source = entry.get("source")
        if source:
            parts.append(f"Source: {source}")
        notes = entry.get("notes")
        if notes:
            parts.append(f"Notes: {notes}")

        outcome = "\n".join(parts) if parts else "No dates found"

        _apply_dates(conf, dates, notify)

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


def _apply_dates(conf: Conference, found_dates: dict, notify: str | None = None) -> None:
    def _parse(key: str) -> date | None:
        value = found_dates.get(key)
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    year = date.today().year
    update_conf_dates(
        conf,
        year,
        cfp_open=_parse("cfp_open"),
        cfp_close=_parse("cfp_close"),
        conference_start=_parse("conference_start"),
        conference_end=_parse("conference_end"),
        notify=notify or None,
    )
    fill_dates_with_guesses(conf, year)


def _build_prompt(confs: list[Conference]) -> str:
    today = date.today()
    current_year = today.year

    conf_sections = []
    for conf in confs:
        missing = []
        known = []
        year_entry = conf.years.get(current_year)
        for field in ["cfp_open", "cfp_close", "conference_start", "conference_end", "notify"]:
            value = getattr(year_entry, field, None) if year_entry else None
            if value:
                known.append(f"  {field}: {value}")
            else:
                missing.append(field)

        section = f"- {conf.name} ({conf.city}, {conf.country})\n"
        section += f"  Website: {conf.website}\n"
        if conf.cfp and conf.cfp.url:
            section += f"  CFP URL: {conf.cfp.url}\n"
        if known:
            section += "  Known:" + ", ".join(known) + "\n"
        section += f"  Missing: {', '.join(missing)}\n"
        conf_sections.append(section)

    return f"""Find missing {current_year} dates for these conferences. Today is {today.isoformat()}.

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
