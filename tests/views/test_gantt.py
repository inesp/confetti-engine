from datetime import date

from freezegun import freeze_time

from confetti.conference_view import build_timeline
from confetti.models import Conference, TalkEntry, TalkStatus, YearEntry
from confetti.views.timeline import build_gantt

TODAY = date(2026, 10, 12)


def _conf(years: dict[int, YearEntry | None]) -> Conference:
    return Conference(
        filename="test.yaml",
        name="Conf",
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
    )


def _statuses(confs: list[Conference]) -> list[str]:
    bars, _ = build_gantt(build_timeline(confs), TODAY)
    return [bar.status for bar in bars]


@freeze_time("2026-10-12")
def test_next_edition_uses_its_own_status_not_this_years():
    conf = _conf(
        {
            2026: YearEntry(
                conference_start=date(2026, 4, 1),
                talks=[TalkEntry(talk="talk-a", status=TalkStatus.accepted, title="Talk A")],
            ),
            2027: YearEntry(
                conference_start=date(2027, 4, 1),
                talks=[TalkEntry(talk="talk-b", status=TalkStatus.submitted, title="Talk B")],
            ),
        }
    )
    result = _statuses([conf])
    assert result == ["submitted"]


@freeze_time("2026-10-12")
def test_accepted_edition_is_accepted():
    conf = _conf(
        {
            2026: YearEntry(
                conference_start=date(2026, 11, 20),
                talks=[TalkEntry(talk="talk-a", status=TalkStatus.accepted, title="Talk A")],
            ),
        }
    )
    result = _statuses([conf])
    assert result == ["accepted"]
