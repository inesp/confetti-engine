from datetime import date

from confetti.models import Conference, Presumed, YearEntry
from confetti.views.timeline import build_yearly_dot_timeline


def _conf(name: str, year_entry: YearEntry | None = None, presumed: Presumed | None = None) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years={2026: year_entry} if year_entry else {},
        presumed=presumed or Presumed(),
    )


def _pct(month: int, day: int) -> float:
    return (date(2026, month, day) - date(2026, 1, 1)).days / 365 * 100


def test_empty_conferences():
    result_dots, result_months = build_yearly_dot_timeline([], 2026)
    assert result_dots == []
    assert len(result_months) == 12


def test_factual_dates():
    conf_a = _conf("ConfA", year_entry=YearEntry(conference_start=date(2026, 3, 15)))
    conf_b = _conf("ConfB", year_entry=YearEntry(conference_start=date(2026, 9, 1)))
    result_dots, _ = build_yearly_dot_timeline([conf_a, conf_b], 2026)
    assert [(dot.conf.name, dot.position_pct) for dot in result_dots] == [
        ("ConfA", _pct(3, 15)),
        ("ConfB", _pct(9, 1)),
    ]


def test_presumed_dates_fallback():
    conf = _conf("ConfA", presumed=Presumed(conference_start="06-10"))
    result_dots, _ = build_yearly_dot_timeline([conf], 2026)
    assert [(dot.conf.name, dot.position_pct) for dot in result_dots] == [
        ("ConfA", _pct(6, 10)),
    ]


def test_factual_takes_precedence_over_presumed():
    conf = _conf(
        "ConfA",
        year_entry=YearEntry(conference_start=date(2026, 5, 1)),
        presumed=Presumed(conference_start="09-01"),
    )
    result_dots, _ = build_yearly_dot_timeline([conf], 2026)
    assert [(dot.conf.name, dot.position_pct) for dot in result_dots] == [
        ("ConfA", _pct(5, 1)),
    ]


def test_no_dates_skipped():
    conferences = [
        _conf("NoDate"),
        _conf("HasDate", year_entry=YearEntry(conference_start=date(2026, 4, 1))),
    ]
    result_dots, _ = build_yearly_dot_timeline(conferences, 2026)
    assert [dot.conf.name for dot in result_dots] == ["HasDate"]


def test_sorted_by_date():
    conferences = [
        _conf("Later", year_entry=YearEntry(conference_start=date(2026, 11, 1))),
        _conf("Earlier", year_entry=YearEntry(conference_start=date(2026, 2, 1))),
    ]
    result_dots, _ = build_yearly_dot_timeline(conferences, 2026)
    assert [dot.conf.name for dot in result_dots] == ["Earlier", "Later"]


def test_overlapping_dots_get_different_rows():
    conferences = [
        _conf("ConfA", year_entry=YearEntry(conference_start=date(2026, 6, 10))),
        _conf("ConfB", year_entry=YearEntry(conference_start=date(2026, 6, 10))),
        _conf("ConfC", year_entry=YearEntry(conference_start=date(2026, 6, 11))),
    ]
    result_dots, _ = build_yearly_dot_timeline(conferences, 2026)
    assert [dot.row for dot in result_dots] == [0, 1, 2]


def test_distant_dots_stay_on_row_zero():
    conferences = [
        _conf("ConfA", year_entry=YearEntry(conference_start=date(2026, 3, 1))),
        _conf("ConfB", year_entry=YearEntry(conference_start=date(2026, 9, 1))),
    ]
    result_dots, _ = build_yearly_dot_timeline(conferences, 2026)
    assert [dot.row for dot in result_dots] == [0, 0]


def test_months_always_jan_to_dec():
    _, result_months = build_yearly_dot_timeline([], 2026)
    assert [m.label for m in result_months] == [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
