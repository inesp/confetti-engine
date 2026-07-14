import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from confetti.google.calendar_sync import (
    _build_event_body,
    _build_talk_event_body,
    fetch_calendars,
    get_selected_calendar_id,
    get_selected_calendar_name,
    save_selected_calendar,
    sync_accepted_conferences,
)
from confetti.models import Conference, Presumed, TalkEntry, TalkStatus, YearEntry


def _conf(
    name: str = "TestConf",
    city: str = "Amsterdam",
    country: str = "Netherlands",
    years: dict | None = None,
    website: str = "https://example.com",
    address: str | None = None,
    budget: str | None = None,
    notes: str | None = None,
) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city=city,
        country=country,
        website=website,
        years=years or {},
        presumed=Presumed(),
        address=address,
        budget=budget,
        notes=notes,
    )


def _accepted_talk(talk_id: str = "talk", title: str = "My Talk") -> TalkEntry:
    return TalkEntry(talk=talk_id, title=title, status=TalkStatus.accepted)


def _rejected_talk(talk_id: str = "talk", title: str = "Bad Talk") -> TalkEntry:
    return TalkEntry(talk=talk_id, title=title, status=TalkStatus.rejected)


class TestCalendarConfig:
    def test_save_and_load_id(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        save_selected_calendar("abc123", "My Calendar")
        result = get_selected_calendar_id()
        assert result == "abc123"

    def test_save_and_load_name(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        save_selected_calendar("abc123", "My Calendar")
        result = get_selected_calendar_name()
        assert result == "My Calendar"

    def test_no_file_returns_none_for_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", tmp_path / "nope.json")
        result = get_selected_calendar_id()
        assert result is None

    def test_no_file_returns_none_for_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", tmp_path / "nope.json")
        result = get_selected_calendar_name()
        assert result is None

    def test_corrupt_file_returns_none_for_id(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not json")
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        result = get_selected_calendar_id()
        assert result is None

    def test_corrupt_file_returns_none_for_name(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not json")
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        result = get_selected_calendar_name()
        assert result is None

    def test_save_overwrites_existing(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        save_selected_calendar("old_id", "Old Name")
        save_selected_calendar("new_id", "New Name")
        result = json.loads(config_file.read_text())
        assert result == {"calendar_id": "new_id", "calendar_name": "New Name"}

    def test_old_config_without_name(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"calendar_id": "legacy123"}))
        monkeypatch.setattr("confetti.google.calendar_sync.GOOGLE_CALENDAR_CONFIG_FILE", config_file)
        result = (get_selected_calendar_id(), get_selected_calendar_name())
        assert result == ("legacy123", None)


class TestFetchCalendars:
    @patch("confetti.google.calendar_sync.get_credentials", return_value=None)
    def test_no_credentials(self, _mock_creds):
        result = fetch_calendars()
        assert result == []

    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_credentials")
    def test_api_error(self, mock_creds, mock_requests):
        mock_creds.return_value = MagicMock(token="tok")
        mock_requests.get.return_value = MagicMock(status_code=403)
        result = fetch_calendars()
        assert result == []

    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_credentials")
    def test_parses_response(self, mock_creds, mock_requests):
        mock_creds.return_value = MagicMock(token="tok")
        mock_requests.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"id": "cal1", "summary": "Work"}, {"id": "cal2", "summary": "Personal"}]},
        )
        result = [(c.calendar_id, c.name) for c in fetch_calendars()]
        assert result == [("cal1", "Work"), ("cal2", "Personal")]

    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_credentials")
    def test_empty_items(self, mock_creds, mock_requests):
        mock_creds.return_value = MagicMock(token="tok")
        mock_requests.get.return_value = MagicMock(status_code=200, json=lambda: {"items": []})
        result = fetch_calendars()
        assert result == []


class TestSyncAcceptedConferences:
    @patch("confetti.google.calendar_sync.get_credentials", return_value=None)
    def test_no_credentials(self, _mock_creds):
        result = sync_accepted_conferences([])
        assert result.errors == ["Not authenticated with Google Calendar."]

    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value=None)
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_no_calendar_selected(self, _mock_creds, _mock_cal_id):
        result = sync_accepted_conferences([])
        assert result.errors == ["No calendar selected. Pick a calendar first."]

    @patch("confetti.google.calendar_sync.get_selected_calendar_name", return_value="Družina")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_calendar_not_found_with_name(self, _mock_creds, _mock_cal_id, mock_requests, _mock_cal_name):
        mock_requests.get.return_value = MagicMock(status_code=404)
        result = sync_accepted_conferences([])
        assert result.errors == [
            'Selected calendar "Družina" not found. Please re-select a calendar from the dropdown.'
        ]

    @patch("confetti.google.calendar_sync.get_selected_calendar_name", return_value=None)
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal@group.calendar.google.com")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_calendar_not_found_falls_back_to_id(self, _mock_creds, _mock_cal_id, mock_requests, _mock_cal_name):
        mock_requests.get.return_value = MagicMock(status_code=404)
        result = sync_accepted_conferences([])
        assert result.errors == [
            'Selected calendar "cal@group.calendar.google.com" not found. Please re-select a calendar from the dropdown.'
        ]

    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_calendar_access_error(self, _mock_creds, _mock_cal_id, mock_requests):
        mock_requests.get.return_value = MagicMock(status_code=500, text="Internal Server Error")
        result = sync_accepted_conferences([])
        assert result.errors == ["Could not access calendar: 500 Internal Server Error"]

    @patch("confetti.google.calendar_sync._delete_stale_events")
    @patch("confetti.google.calendar_sync._find_existing_event", return_value=None)
    @patch("confetti.google.calendar_sync._create_event")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_skips_past_conferences(self, _creds, _cal_id, mock_requests, mock_create, _find, _delete):
        mock_requests.get.return_value = MagicMock(status_code=200)
        past_conf = _conf(
            years={
                2025: YearEntry(
                    conference_start=date(2025, 6, 1),
                    conference_end=date(2025, 6, 3),
                    talks=[_accepted_talk()],
                )
            }
        )
        sync_accepted_conferences([past_conf])
        result = mock_create.call_count
        assert result == 0

    @patch("confetti.google.calendar_sync._delete_stale_events")
    @patch("confetti.google.calendar_sync._find_existing_event", return_value=None)
    @patch("confetti.google.calendar_sync._create_event")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_skips_rejected_conferences(self, _creds, _cal_id, mock_requests, mock_create, _find, _delete):
        mock_requests.get.return_value = MagicMock(status_code=200)
        future = date.today() + timedelta(days=30)
        rejected_conf = _conf(years={future.year: YearEntry(conference_start=future, talks=[_rejected_talk()])})
        sync_accepted_conferences([rejected_conf])
        result = mock_create.call_count
        assert result == 0

    @patch("confetti.google.calendar_sync._delete_stale_events")
    @patch("confetti.google.calendar_sync._find_existing_event", return_value=None)
    @patch("confetti.google.calendar_sync._create_event")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_skips_conferences_without_start_date(self, _creds, _cal_id, mock_requests, mock_create, _find, _delete):
        mock_requests.get.return_value = MagicMock(status_code=200)
        no_date_conf = _conf(years={2027: YearEntry(talks=[_accepted_talk()])})
        sync_accepted_conferences([no_date_conf])
        result = mock_create.call_count
        assert result == 0

    @patch("confetti.google.calendar_sync._delete_stale_events")
    @patch("confetti.google.calendar_sync._find_existing_event", return_value=None)
    @patch("confetti.google.calendar_sync._create_event")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_creates_event_for_future_accepted(self, _creds, _cal_id, mock_requests, mock_create, _find, _delete):
        mock_requests.get.return_value = MagicMock(status_code=200)
        future = date.today() + timedelta(days=30)
        conf = _conf(
            name="FutureConf",
            years={
                future.year: YearEntry(
                    conference_start=future,
                    conference_end=future + timedelta(days=2),
                    talks=[_accepted_talk()],
                )
            },
        )
        sync_accepted_conferences([conf])
        result = mock_create.call_args[0][3]
        assert result == f"FutureConf_{future.year}"

    @patch("confetti.google.calendar_sync._delete_stale_events")
    @patch("confetti.google.calendar_sync._find_existing_event", return_value="existing_id")
    @patch("confetti.google.calendar_sync._update_event")
    @patch("confetti.google.calendar_sync._create_event")
    @patch("confetti.google.calendar_sync.requests")
    @patch("confetti.google.calendar_sync.get_selected_calendar_id", return_value="cal123")
    @patch("confetti.google.calendar_sync.get_credentials", return_value=MagicMock(token="tok"))
    def test_updates_existing_event(self, _creds, _cal_id, mock_requests, mock_create, mock_update, _find, _delete):
        mock_requests.get.return_value = MagicMock(status_code=200)
        future = date.today() + timedelta(days=30)
        conf = _conf(
            years={
                future.year: YearEntry(
                    conference_start=future,
                    talks=[_accepted_talk()],
                )
            }
        )
        sync_accepted_conferences([conf])
        result = (mock_create.call_count, mock_update.call_count)
        assert result == (0, 1)


class TestBuildEventBody:
    def test_basic(self):
        entry = YearEntry(conference_start=date(2026, 9, 15), conference_end=date(2026, 9, 17))
        result = _build_event_body(_conf(name="TestConf", city="Amsterdam"), entry, "TestConf_2026")
        assert result == {
            "summary": "TestConf (Amsterdam)",
            "description": '<a href="https://example.com">https://example.com</a>',
            "location": "Amsterdam, Netherlands",
            "start": {"date": "2026-09-15"},
            "end": {"date": "2026-09-18"},
            "extendedProperties": {"private": {"confetti_id": "TestConf_2026"}},
        }

    def test_with_accepted_talk(self):
        entry = YearEntry(
            conference_start=date(2026, 9, 15),
            conference_end=date(2026, 9, 17),
            talks=[_accepted_talk(title="My Talk")],
        )
        result = _build_event_body(_conf(), entry, "TestConf_2026")
        assert result["summary"] == "TestConf (Amsterdam) - My Talk"

    def test_excludes_rejected_talks_from_summary(self):
        entry = YearEntry(
            conference_start=date(2026, 9, 15),
            talks=[_accepted_talk(title="Good Talk"), _rejected_talk(title="Bad Talk")],
        )
        result = _build_event_body(_conf(), entry, "TestConf_2026")
        assert result["summary"] == "TestConf (Amsterdam) - Good Talk"

    def test_uses_address_when_available(self):
        entry = YearEntry(conference_start=date(2026, 9, 15))
        result = _build_event_body(_conf(address="Grand Hall, Amsterdam"), entry, "TestConf_2026")
        assert result["location"] == "Grand Hall, Amsterdam"

    def test_single_day_conference(self):
        entry = YearEntry(conference_start=date(2026, 9, 15))
        result = _build_event_body(_conf(), entry, "TestConf_2026")
        assert result["end"] == {"date": "2026-09-16"}

    def test_description_includes_budget(self):
        entry = YearEntry(conference_start=date(2026, 9, 15))
        result = _build_event_body(_conf(budget="full"), entry, "TestConf_2026")
        assert result["description"] == (
            '<a href="https://example.com">https://example.com</a>' "<br><b>Budget:</b> full"
        )

    def test_description_includes_notes(self):
        entry = YearEntry(conference_start=date(2026, 9, 15))
        result = _build_event_body(_conf(notes="Bring adapter"), entry, "TestConf_2026")
        assert result["description"] == (
            '<a href="https://example.com">https://example.com</a>' "<br><b>Notes:</b> Bring adapter"
        )


class TestBuildTalkEventBody:
    def test_basic(self):
        talk = TalkEntry(
            talk="my-talk",
            title="My Talk",
            status=TalkStatus.accepted,
            talk_start=datetime(2026, 9, 15, 14, 0),
            talk_duration=30,
        )
        result = _build_talk_event_body(_conf(name="TestConf"), talk, "TestConf_2026_talk_my-talk")
        assert result == {
            "summary": "🎤 My Talk @ TestConf",
            "location": "Amsterdam, Netherlands",
            "start": {"dateTime": "2026-09-15T14:00:00", "timeZone": "Europe/Amsterdam"},
            "end": {"dateTime": "2026-09-15T14:30:00", "timeZone": "Europe/Amsterdam"},
            "extendedProperties": {"private": {"confetti_id": "TestConf_2026_talk_my-talk"}},
        }

    def test_defaults_to_45_min(self):
        talk = TalkEntry(
            talk="my-talk", title="My Talk", status=TalkStatus.accepted, talk_start=datetime(2026, 9, 15, 14, 0)
        )
        result = _build_talk_event_body(_conf(), talk, "id")
        assert result["end"] == {"dateTime": "2026-09-15T14:45:00", "timeZone": "Europe/Amsterdam"}

    def test_uses_talk_id_when_no_title(self):
        talk = TalkEntry(talk="my-talk", status=TalkStatus.accepted, talk_start=datetime(2026, 9, 15, 14, 0))
        result = _build_talk_event_body(_conf(name="Conf"), talk, "id")
        assert result["summary"] == "🎤 my-talk @ Conf"

    def test_includes_schedule_notes(self):
        talk = TalkEntry(
            talk="my-talk",
            title="My Talk",
            status=TalkStatus.accepted,
            talk_start=datetime(2026, 9, 15, 14, 0),
            schedule_notes="Room 3, second floor",
        )
        result = _build_talk_event_body(_conf(), talk, "id")
        assert result["description"] == "Room 3, second floor"

    def test_no_description_without_notes(self):
        talk = TalkEntry(talk="my-talk", status=TalkStatus.accepted, talk_start=datetime(2026, 9, 15, 14, 0))
        result = _build_talk_event_body(_conf(), talk, "id")
        assert "description" not in result
