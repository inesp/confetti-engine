from datetime import date

from freezegun import freeze_time

from confetti.conference_view import build_timeline
from confetti.models import Cfp, Conference, TalkEntry, TalkStatus, YearEntry
from confetti.views.timeline import CfpBarStatus, build_cfp_gantt

TODAY = date(2026, 7, 9)


def _conf(
    name: str,
    *,
    years: dict[int, YearEntry | None] | None = None,
    cfp: Cfp | None = None,
    skip: bool = False,
    favorite: bool = False,
) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years or {},
        cfp=cfp,
        skip=skip,
        favorite=favorite,
    )


def _presumed(open_md: str, close_md: str) -> Cfp:
    return Cfp(url=None, site=None, formats=None, notes=None, presumed_open=open_md, presumed_close=close_md)


def _bars(confs: list[Conference]) -> list:
    timeline = build_timeline(confs)
    bars, _ = build_cfp_gantt(timeline, TODAY)
    return bars


@freeze_time("2026-07-09")
def test_empty_gives_no_bars():
    result = _bars([])
    assert result == []


@freeze_time("2026-07-09")
def test_factual_close_is_known():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(conference_start=date(2026, 10, 1), cfp_open=date(2026, 8, 1), cfp_close=date(2026, 9, 1))
        },
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.known


@freeze_time("2026-07-09")
def test_presumed_dates_are_a_guess():
    conf = _conf(
        "Conf",
        years={2026: YearEntry(conference_start=date(2026, 10, 1))},
        cfp=_presumed("08-01", "09-01"),
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.guess


@freeze_time("2026-07-09")
def test_submitted_talk_is_submitted():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(
                conference_start=date(2026, 10, 1),
                cfp_open=date(2026, 8, 1),
                cfp_close=date(2026, 9, 1),
                talks=[TalkEntry(talk="t1", status=TalkStatus.submitted, title="T")],
            )
        },
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.submitted


@freeze_time("2026-07-09")
def test_accepted_talk_is_accepted():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(
                conference_start=date(2026, 10, 1),
                cfp_open=date(2026, 8, 1),
                cfp_close=date(2026, 9, 1),
                talks=[TalkEntry(talk="t1", status=TalkStatus.accepted, title="T")],
            )
        },
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.accepted


@freeze_time("2026-07-09")
def test_skipped_conference_is_skipped():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(conference_start=date(2026, 10, 1), cfp_open=date(2026, 8, 1), cfp_close=date(2026, 9, 1))
        },
        skip=True,
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.skipped


@freeze_time("2026-07-09")
def test_favorite_does_not_change_the_status():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(conference_start=date(2026, 10, 1), cfp_open=date(2026, 8, 1), cfp_close=date(2026, 9, 1))
        },
        favorite=True,
    )
    result = _bars([conf])[0]
    assert result.status == CfpBarStatus.known


@freeze_time("2026-07-09")
def test_window_ending_before_today_is_excluded():
    conf = _conf(
        "Conf",
        years={
            2026: YearEntry(conference_start=date(2026, 7, 20), cfp_open=date(2026, 5, 1), cfp_close=date(2026, 6, 1))
        },
    )
    result = _bars([conf])
    assert result == []


@freeze_time("2026-07-09")
def test_window_after_the_range_is_excluded():
    conf = _conf(
        "Conf",
        years={2027: YearEntry(conference_start=date(2027, 10, 1))},
        cfp=_presumed("08-01", "09-01"),
    )
    result = _bars([conf])
    assert result == []


@freeze_time("2026-07-09")
def test_skipped_conferences_sort_to_the_end():
    normal = _conf(
        "Normal",
        years={
            2026: YearEntry(
                conference_start=date(2026, 10, 1), cfp_open=date(2026, 8, 1), cfp_close=date(2026, 8, 15)
            )
        },
    )
    skipped = _conf(
        "Skipped",
        years={
            2026: YearEntry(
                conference_start=date(2026, 10, 1), cfp_open=date(2026, 7, 20), cfp_close=date(2026, 8, 1)
            )
        },
        skip=True,
    )
    result = [bar.conf.name for bar in _bars([skipped, normal])]
    assert result == ["Normal", "Skipped"]
