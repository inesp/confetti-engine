import json
import logging
from dataclasses import dataclass

from confetti.models import Conference
from confetti.constants import DISCOVER_LOG
from confetti.constants import DISCOVER_MAX_BUDGET_USD
from confetti.constants import DISCOVER_MODEL
from confetti.constants import DISCOVER_TIMEOUT
from confetti.scouting.claude_runner import clear_stop
from confetti.scouting.claude_runner import extract_json
from confetti.scouting.claude_runner import is_stopped
from confetti.scouting.claude_runner import reset_log
from confetti.scouting.claude_runner import run_claude
from confetti.scouting.claude_runner import stop
from confetti.talks import load_talk_descriptions
from confetti.yaml.skipped import load_skipped

logger = logging.getLogger(__name__)

# Re-export for use by routes
stop_discovering = stop


@dataclass
class DiscoverResult:
    name: str
    city: str
    country: str
    website: str
    why: str
    budget: str | None = None
    topic_fit: str | None = None
    attendees: str | None = None
    cfp_url: str | None = None
    cfp_deadline: str | None = None
    conference_dates: str | None = None
    selectivity: str | None = None
    difficulty_for_me: str | None = None
    suggested_filename: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "city": self.city,
            "country": self.country,
            "website": self.website,
            "why": self.why,
            "budget": self.budget,
            "topic_fit": self.topic_fit,
            "attendees": self.attendees,
            "cfp_url": self.cfp_url,
            "cfp_deadline": self.cfp_deadline,
            "conference_dates": self.conference_dates,
            "selectivity": self.selectivity,
            "difficulty_for_me": self.difficulty_for_me,
            "suggested_filename": self.suggested_filename,
            "notes": self.notes,
        }


def discover_conferences(existing: list[Conference]) -> list[DiscoverResult]:
    prompt = _build_prompt(existing)

    clear_stop()
    reset_log(DISCOVER_LOG)
    try:
        raw = run_claude(
            prompt,
            log_file=DISCOVER_LOG,
            timeout=DISCOVER_TIMEOUT.total_seconds(),
            model=DISCOVER_MODEL,
            max_budget_usd=DISCOVER_MAX_BUDGET_USD,
        )
    except FileNotFoundError:
        return [_error("'claude' CLI not found")]
    except TimeoutError:
        return [_error("Timed out after 10 minutes")]
    except RuntimeError as e:
        # A stopped run kills the process (exit -9); report it as stopped, not an error.
        if is_stopped():
            return []
        return [_error(str(e))]

    return _parse_output(raw)


def _error(msg: str) -> DiscoverResult:
    return DiscoverResult(name="Error", city="", country="", website="", why=msg)


def _parse_output(raw: str) -> list[DiscoverResult]:
    json_str = extract_json(raw)
    if not json_str:
        return [_error(f"Could not find JSON in response: {raw[:300]}")]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return [_error("Could not parse JSON response")]

    conf_list = data.get("conferences", data) if isinstance(data, dict) else data
    if not isinstance(conf_list, list):
        return [_error("Unexpected response format")]

    results = []
    for entry in conf_list:
        results.append(
            DiscoverResult(
                name=entry.get("name", "Unknown"),
                city=entry.get("city", ""),
                country=entry.get("country", ""),
                website=entry.get("website", ""),
                why=entry.get("why", ""),
                budget=entry.get("budget"),
                topic_fit=entry.get("topic_fit"),
                attendees=entry.get("attendees"),
                cfp_url=entry.get("cfp_url"),
                cfp_deadline=entry.get("cfp_deadline"),
                conference_dates=entry.get("conference_dates"),
                selectivity=entry.get("selectivity"),
                difficulty_for_me=entry.get("difficulty_for_me"),
                suggested_filename=entry.get("suggested_filename"),
                notes=entry.get("notes"),
            )
        )

    return results


def _build_prompt(existing: list[Conference]) -> str:
    existing_names = [c.name for c in existing]
    skipped_names = load_skipped()
    all_excluded = sorted(set(existing_names + skipped_names))
    excluded_list = "\n".join(f"- {name}" for name in all_excluded)

    talks = load_talk_descriptions()
    talk_descriptions = "\n".join(
        f"- {talk.title}: {talk.description}" if talk.description else f"- {talk.title}" for talk in talks
    )

    return f"""You are helping a software developer find 10 new conferences to speak at in Europe.

## Speaker profile

They are a backend developer based in Europe who speaks at tech conferences. Their talks cover:

{talk_descriptions}

## What they're looking for

PRIORITIES (in order of importance):
1. **Travel budget**: Conferences that cover speaker travel expenses (flights, hotel) — partially or fully. This is the #1 priority.
2. **Talk fit**: Conferences where the talks listed above would be a good fit.
3. **Community & networking**: Conferences with a strong developer community, good hallway track, where they could meet interesting people or find job/collaboration opportunities.
4. **Accessibility**: Conferences in Europe, preferably reachable by affordable flights or train.

## Conferences they already track or have skipped (DO NOT suggest these)

{excluded_list}

## Your task

Search the web and find 10-15 conferences they should consider. Focus on:
- European developer conferences (general software engineering, Python, backend, DevOps, agile/process)
- Conferences known to cover speaker travel
- Community-driven conferences (not purely corporate/vendor events)
- Conferences happening in the next 12 months that still have open or upcoming CFPs

For each conference, visit its website to verify details. Don't guess — only include info you actually find.

IMPORTANT: Do NOT spawn sub-agents. Do all web searches yourself directly.

## Output format

Respond with JSON:
{{"conferences": [
  {{
    "name": "Conference Name",
    "city": "City",
    "country": "Country",
    "website": "https://...",
    "why": "Why this is a good fit (1-2 sentences)",
    "budget": "full / partial / unknown / none",
    "topic_fit": "Which of their talks fit best",
    "attendees": "Approximate number or range",
    "cfp_url": "URL or null",
    "cfp_deadline": "YYYY-MM-DD or null",
    "conference_dates": "YYYY-MM-DD to YYYY-MM-DD or null",
    "selectivity": "low / medium / high — how picky they are with selecting speakers (based on acceptance rate, reputation, speaker lineup quality)",
    "difficulty_for_me": "longshot / hard / null — how much of a lottery this conference's CFP is, based on its selectivity (submission volume vs slots, prestige, star-studded lineups). Use 'longshot' for a massive cattle call (thousands of submissions, marquee names), 'hard' for a notably competitive but not hopeless one, and null for everything ordinary. This is about the conference's selectivity, NOT the speaker's personal odds.",
    "suggested_filename": "a short .yaml filename to save this conference under, e.g. techorama.yaml, devopsdays.yaml — group related conferences under one file",
    "notes": "Any useful context (community vibe, past speaker experience reports, etc.)"
  }}
]}}
"""
