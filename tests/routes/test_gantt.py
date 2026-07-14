from datetime import date

from freezegun import freeze_time

from confetti.conference_view import KanbanColumn, build_timeline
from confetti.models import Conference, TalkEntry, TalkStatus, YearEntry


def _conf(name: str, years: dict[int, YearEntry | None] | None = None) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years or {},
    )


@freeze_time("2026-05-01")
def test_rejected_goes_to_past():
    """EuroPython bug: rejected/withdrawn conferences should not appear in pipeline or timeline."""
    conf = _conf(
        "EuroPython",
        {
            2026: YearEntry(
                conference_start=date(2026, 7, 14),
                talks=[
                    TalkEntry(talk="t1", status=TalkStatus.rejected, title="Talk 1"),
                    TalkEntry(talk="t2", status=TalkStatus.withdrawn, title="Talk 2"),
                ],
            )
        },
    )
    timeline = build_timeline([conf])
    result = timeline[0]
    assert result.kanban_column == KanbanColumn.past


@freeze_time("2026-05-01")
def test_all_withdrawn_goes_to_past():
    conf = _conf(
        "Conf",
        {
            2026: YearEntry(
                conference_start=date(2026, 7, 14),
                talks=[TalkEntry(talk="t1", status=TalkStatus.withdrawn, title="Talk 1")],
            )
        },
    )
    timeline = build_timeline([conf])
    result = timeline[0]
    assert result.kanban_column == KanbanColumn.past


@freeze_time("2026-05-01")
def test_accepted_stays_in_accepted():
    conf = _conf(
        "Conf",
        {
            2026: YearEntry(
                conference_start=date(2026, 7, 14),
                talks=[TalkEntry(talk="t1", status=TalkStatus.accepted, title="Talk 1")],
            )
        },
    )
    timeline = build_timeline([conf])
    result = timeline[0]
    assert result.kanban_column == KanbanColumn.accepted


@freeze_time("2026-05-01")
def test_submitted_stays_in_submitted():
    conf = _conf(
        "Conf",
        {
            2026: YearEntry(
                conference_start=date(2026, 7, 14),
                talks=[TalkEntry(talk="t1", status=TalkStatus.submitted, title="Talk 1")],
            )
        },
    )
    timeline = build_timeline([conf])
    result = timeline[0]
    assert result.kanban_column == KanbanColumn.submitted
