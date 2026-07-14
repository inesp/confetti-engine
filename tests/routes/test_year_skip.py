from datetime import date

from freezegun import freeze_time

from confetti.conference_view import KanbanColumn, Urgency, build_timeline
from confetti.models import Conference, YearEntry


def _conf(name: str, years: dict[int, YearEntry | None]) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
    )


@freeze_time("2026-07-09")
def test_skipped_edition_is_marked_skipped():
    conf = _conf("Conf", {2026: YearEntry(conference_start=date(2026, 10, 1), skip=True)})
    result = build_timeline([conf])[0]
    assert result.skipped is True


@freeze_time("2026-07-09")
def test_skipped_edition_drops_out_of_action_lists():
    conf = _conf("Conf", {2026: YearEntry(conference_start=date(2026, 10, 1), skip=True)})
    result = build_timeline([conf])[0]
    assert result.urgency == Urgency.past


@freeze_time("2026-07-09")
def test_unskipped_edition_stays_active():
    conf = _conf("Conf", {2026: YearEntry(conference_start=date(2026, 10, 1))})
    result = build_timeline([conf])[0]
    assert result.kanban_column != KanbanColumn.past
