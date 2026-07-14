import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import requests

from confetti.constants import CALENDAR_TIMEZONE, GOOGLE_CALENDAR_CONFIG_FILE
from confetti.google.auth import get_credentials
from confetti.models import Conference, TalkEntry, TalkStatus, YearEntry

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.googleapis.com/calendar/v3"


@dataclass
class CalendarInfo:
    calendar_id: str
    name: str


@dataclass
class SyncResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fetch_calendars() -> list[CalendarInfo]:
    creds = get_credentials()
    if not creds:
        return []

    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get(f"{_BASE_URL}/users/me/calendarList", headers=headers, timeout=15)
    if response.status_code != 200:
        return []

    items = response.json().get("items", [])
    return [CalendarInfo(calendar_id=item["id"], name=item["summary"]) for item in items]


def get_selected_calendar_id() -> str | None:
    if not GOOGLE_CALENDAR_CONFIG_FILE.exists():
        return None
    try:
        with open(GOOGLE_CALENDAR_CONFIG_FILE) as f:
            return json.load(f).get("calendar_id")
    except Exception:
        return None


def get_selected_calendar_name() -> str | None:
    if not GOOGLE_CALENDAR_CONFIG_FILE.exists():
        return None
    try:
        with open(GOOGLE_CALENDAR_CONFIG_FILE) as f:
            return json.load(f).get("calendar_name")
    except Exception:
        return None


def save_selected_calendar(calendar_id: str, calendar_name: str) -> None:
    with open(GOOGLE_CALENDAR_CONFIG_FILE, "w") as f:
        json.dump({"calendar_id": calendar_id, "calendar_name": calendar_name}, f)


def sync_accepted_conferences(conferences: list[Conference]) -> SyncResult:
    creds = get_credentials()
    if not creds:
        return SyncResult(errors=["Not authenticated with Google Calendar."])

    calendar_id = get_selected_calendar_id()
    if not calendar_id:
        return SyncResult(errors=["No calendar selected. Pick a calendar first."])

    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

    # Verify the selected calendar is still accessible
    cal_response = requests.get(f"{_BASE_URL}/calendars/{calendar_id}", headers=headers, timeout=15)
    if cal_response.status_code == 404:
        calendar_name = get_selected_calendar_name() or calendar_id
        return SyncResult(
            errors=[f'Selected calendar "{calendar_name}" not found. Please re-select a calendar from the dropdown.']
        )
    if cal_response.status_code != 200:
        return SyncResult(errors=[f"Could not access calendar: {cal_response.status_code} {cal_response.text}"])

    result = SyncResult()

    accepted_confetti_ids: set[str] = set()

    today = date.today()

    for conference in conferences:
        for year, entry in conference.years.items():
            if entry is None or entry.status != TalkStatus.accepted:
                continue
            if not entry.conference_start:
                continue
            if (entry.conference_end or entry.conference_start) < today:
                continue

            confetti_id = f"{conference.name}_{year}"
            accepted_confetti_ids.add(confetti_id)
            event_body = _build_event_body(conference, entry, confetti_id)

            existing_event_id = _find_existing_event(headers, calendar_id, confetti_id)
            if existing_event_id:
                _update_event(headers, calendar_id, existing_event_id, event_body, confetti_id, result)
            else:
                _create_event(headers, calendar_id, event_body, confetti_id, result)

            # Sync individual talk schedule events
            for talk in entry.talks:
                if talk.status == TalkStatus.accepted and talk.talk_start:
                    talk_confetti_id = f"{confetti_id}_talk_{talk.talk}"
                    accepted_confetti_ids.add(talk_confetti_id)
                    talk_body = _build_talk_event_body(conference, talk, talk_confetti_id)
                    existing_talk_id = _find_existing_event(headers, calendar_id, talk_confetti_id)
                    if existing_talk_id:
                        _update_event(headers, calendar_id, existing_talk_id, talk_body, talk_confetti_id, result)
                    else:
                        _create_event(headers, calendar_id, talk_body, talk_confetti_id, result)

    _delete_stale_events(headers, calendar_id, accepted_confetti_ids, result)

    return result


def _build_event_body(conference: Conference, entry: YearEntry, confetti_id: str) -> dict:
    assert entry.conference_start is not None
    # Google Calendar all-day events use exclusive end date
    end_exclusive = (entry.conference_end or entry.conference_start) + timedelta(days=1)

    accepted_talks = [t.title or t.talk for t in entry.talks if t.status == TalkStatus.accepted]

    talk_suffix = f" - {', '.join(accepted_talks)}" if accepted_talks else ""

    lines = [
        f'<a href="{conference.website}">{conference.website}</a>',
    ]
    if conference.budget:
        lines.append(f"<b>Budget:</b> {conference.budget}")
    if conference.notes:
        lines.append(f"<b>Notes:</b> {conference.notes}")

    return {
        "location": conference.address or f"{conference.city}, {conference.country}",
        "summary": f"{conference.name} ({conference.city}){talk_suffix}",
        "description": "<br>".join(lines),
        "start": {"date": entry.conference_start.isoformat()},
        "end": {"date": end_exclusive.isoformat()},
        "extendedProperties": {"private": {"confetti_id": confetti_id}},
    }


def _build_talk_event_body(conference: Conference, talk: TalkEntry, confetti_id: str) -> dict:
    assert talk.talk_start is not None
    talk_title = talk.title or talk.talk
    talk_end = talk.talk_end or (talk.talk_start + timedelta(minutes=45))
    body: dict = {
        "summary": f"🎤 {talk_title} @ {conference.name}",
        "location": conference.address or f"{conference.city}, {conference.country}",
        "start": {"dateTime": talk.talk_start.isoformat(), "timeZone": CALENDAR_TIMEZONE},
        "end": {"dateTime": talk_end.isoformat(), "timeZone": CALENDAR_TIMEZONE},
        "extendedProperties": {"private": {"confetti_id": confetti_id}},
    }
    if talk.schedule_notes:
        body["description"] = talk.schedule_notes
    return body


def _find_existing_event(headers: dict, calendar_id: str, confetti_id: str) -> str | None:
    response = requests.get(
        f"{_BASE_URL}/calendars/{calendar_id}/events",
        headers=headers,
        params={"privateExtendedProperty": f"confetti_id={confetti_id}", "singleEvents": "true"},
        timeout=15,
    )
    if response.status_code != 200:
        return None

    items = response.json().get("items", [])
    return items[0]["id"] if items else None


def _create_event(headers: dict, calendar_id: str, event_body: dict, confetti_id: str, result: SyncResult) -> None:
    response = requests.post(
        f"{_BASE_URL}/calendars/{calendar_id}/events",
        headers=headers,
        json=event_body,
        timeout=15,
    )
    if response.status_code in (200, 201):
        result.created.append(confetti_id)
        logger.info(f"Created calendar event for {confetti_id}")
    else:
        error_msg = f"Failed to create event for {confetti_id}: {response.status_code} {response.text}"
        result.errors.append(error_msg)
        logger.warning(error_msg)


def _find_all_confetti_events(headers: dict, calendar_id: str) -> list[dict]:
    """Find all events in the calendar that were created by confetti."""
    events: list[dict] = []
    page_token: str | None = None

    while True:
        params: dict[str, str] = {"privateExtendedProperty": "confetti_id=", "singleEvents": "true"}
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            f"{_BASE_URL}/calendars/{calendar_id}/events", headers=headers, params=params, timeout=15
        )
        if response.status_code != 200:
            break

        data = response.json()
        events.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return events


def _delete_stale_events(
    headers: dict, calendar_id: str, accepted_confetti_ids: set[str], result: SyncResult
) -> None:
    all_events = _find_all_confetti_events(headers, calendar_id)

    today = date.today().isoformat()

    for event in all_events:
        confetti_id = event.get("extendedProperties", {}).get("private", {}).get("confetti_id", "")
        event_end = event.get("end", {}).get("date", "")
        if confetti_id and confetti_id not in accepted_confetti_ids and event_end >= today:
            event_id = event["id"]
            response = requests.delete(
                f"{_BASE_URL}/calendars/{calendar_id}/events/{event_id}", headers=headers, timeout=15
            )
            if response.status_code in (200, 204):
                result.deleted.append(confetti_id)
                logger.info(f"Deleted calendar event for {confetti_id}")
            else:
                error_msg = f"Failed to delete event for {confetti_id}: {response.status_code} {response.text}"
                result.errors.append(error_msg)
                logger.warning(error_msg)


def _update_event(
    headers: dict, calendar_id: str, event_id: str, event_body: dict, confetti_id: str, result: SyncResult
) -> None:
    response = requests.patch(
        f"{_BASE_URL}/calendars/{calendar_id}/events/{event_id}",
        headers=headers,
        json=event_body,
        timeout=15,
    )
    if response.status_code == 200:
        result.updated.append(confetti_id)
        logger.info(f"Updated calendar event for {confetti_id}")
    else:
        error_msg = f"Failed to update event for {confetti_id}: {response.status_code} {response.text}"
        result.errors.append(error_msg)
        logger.warning(error_msg)
