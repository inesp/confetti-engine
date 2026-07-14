from datetime import date

from freezegun import freeze_time

from confetti.models import Conference, Presumed, TalkEntry, TalkStatus, YearEntry
from confetti.conference_view import best_year, build_detail_nav


def _conf(
    name: str,
    years: dict[int, YearEntry | None] | None = None,
) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years or {},
    )


def _year(
    conference_start: date | None = None,
    conference_end: date | None = None,
    status: TalkStatus = TalkStatus.submitted,
    cfp_open: date | None = None,
    cfp_close: date | None = None,
) -> YearEntry:
    return YearEntry(
        conference_start=conference_start,
        conference_end=conference_end,
        cfp_open=cfp_open,
        cfp_close=cfp_close,
        talks=[TalkEntry(talk="test-talk", status=status, title="Test Talk")],
    )


# --- best_year ---


@freeze_time("2026-05-01")
def testbest_year_current_year_future_conference():
    """Conference this year hasn't happened yet - show current year."""
    conf = _conf("Conf", {2026: _year(conference_start=date(2026, 9, 15))})
    result = best_year(conf)
    assert result == 2026


@freeze_time("2026-05-01")
def testbest_year_current_year_no_start_date():
    """Current year entry exists but no start date - show current year."""
    conf = _conf("Conf", {2026: _year()})
    result = best_year(conf)
    assert result == 2026


@freeze_time("2026-05-01")
def testbest_year_current_year_passed_next_year_exists():
    """J-Fall scenario: 2026 edition passed, 2027 entry exists - show 2027."""
    conf = _conf(
        "J-Fall",
        {
            2026: _year(conference_start=date(2026, 1, 15), status=TalkStatus.accepted),
            2027: _year(conference_start=date(2027, 1, 20)),
        },
    )
    result = best_year(conf)
    assert result == 2027


@freeze_time("2026-05-01")
def testbest_year_current_year_passed_no_next_year():
    """BitBash scenario: 2026 edition passed, no 2027 entry - show 2027 anyway."""
    conf = _conf(
        "BitBash",
        {
            2026: _year(conference_start=date(2026, 1, 20), status=TalkStatus.rejected),
        },
    )
    result = best_year(conf)
    assert result == 2027


@freeze_time("2026-05-01")
def testbest_year_no_current_year_entry():
    """No entry for current year at all - show next year."""
    conf = _conf("NewConf", {2025: _year(conference_start=date(2025, 6, 1))})
    result = best_year(conf)
    assert result == 2027


@freeze_time("2026-07-14")
def testbest_year_matches_timeline_for_presumed_edition():
    """NewCrafts scenario: empty 2026 entry but a future presumed date.

    best_year must agree with next_event (2026), not jump to 2027, so the skip
    button targets the same edition the timeline shows.
    """
    conf = Conference(
        filename="test.yaml",
        name="NewCrafts",
        city="Paris",
        country="France",
        website="https://ncrafts.io",
        years={2026: None},
        presumed=Presumed(conference_start="11-06", conference_end="11-07"),
    )
    result = best_year(conf)
    assert result == 2026


@freeze_time("2026-05-01")
def testbest_year_conference_today():
    """Conference starts today - still show current year."""
    conf = _conf("Conf", {2026: _year(conference_start=date(2026, 5, 1))})
    result = best_year(conf)
    assert result == 2026


# --- build_detail_nav: prev/next ---


@freeze_time("2026-05-01")
def test_nav_sorted_by_conference_date():
    """Prev/next should be sorted by conference date, not alphabetically."""
    confs = [
        _conf("Zebra Conf", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("Alpha Conf", {2026: _year(conference_start=date(2026, 9, 1))}),
        _conf("Middle Conf", {2026: _year(conference_start=date(2026, 7, 15))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "Middle Conf")
    assert prev_name == "Zebra Conf"
    assert next_name == "Alpha Conf"


@freeze_time("2026-05-01")
def test_nav_excludes_rejected():
    """Rejected conferences should not appear in prev/next."""
    confs = [
        _conf("First", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("Rejected", {2026: _year(conference_start=date(2026, 7, 1), status=TalkStatus.rejected)}),
        _conf("Third", {2026: _year(conference_start=date(2026, 8, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "First")
    assert prev_name is None
    assert next_name == "Third"


@freeze_time("2026-05-01")
def test_nav_excludes_withdrawn():
    """Withdrawn conferences should not appear in prev/next."""
    confs = [
        _conf("First", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("Withdrawn", {2026: _year(conference_start=date(2026, 7, 1), status=TalkStatus.withdrawn)}),
        _conf("Third", {2026: _year(conference_start=date(2026, 8, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "First")
    assert next_name == "Third"


@freeze_time("2026-05-01")
def test_nav_excludes_past_conferences():
    """Conferences that already happened should not appear in prev/next."""
    confs = [
        _conf("Past", {2026: _year(conference_start=date(2026, 3, 1))}),
        _conf("Future", {2026: _year(conference_start=date(2026, 9, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "Future")
    assert prev_name is None
    assert next_name is None


@freeze_time("2026-05-01")
def test_nav_includes_accepted():
    """Accepted future conferences should appear in prev/next."""
    confs = [
        _conf("Accepted", {2026: _year(conference_start=date(2026, 6, 1), status=TalkStatus.accepted)}),
        _conf("Submitted", {2026: _year(conference_start=date(2026, 8, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "Submitted")
    assert prev_name == "Accepted"


@freeze_time("2026-05-01")
def test_nav_includes_waitlisted():
    """Waitlisted future conferences should appear in prev/next."""
    confs = [
        _conf("Waitlisted", {2026: _year(conference_start=date(2026, 6, 1), status=TalkStatus.waitlisted)}),
        _conf("Other", {2026: _year(conference_start=date(2026, 8, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "Other")
    assert prev_name == "Waitlisted"


@freeze_time("2026-05-01")
def test_nav_no_talks_excluded():
    """Conferences without talks for their best year are excluded from prev/next."""
    confs = [
        _conf("Has Talks", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("No Talks", {2026: YearEntry(conference_start=date(2026, 7, 1))}),
    ]
    _, prev_name, next_name = build_detail_nav(confs, "Has Talks")
    assert next_name is None


# --- build_detail_nav: dropdown ---


@freeze_time("2026-05-01")
def test_dropdown_lists_all_conferences_alphabetically():
    """Dropdown should list ALL conferences sorted alphabetically."""
    confs = [
        _conf("Zebra", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("Alpha", {}),
        _conf("Middle", {2026: _year(conference_start=date(2026, 7, 1), status=TalkStatus.rejected)}),
    ]
    all_confs, _, _ = build_detail_nav(confs, "Zebra")
    assert all_confs == ["Alpha", "Middle", "Zebra"]


@freeze_time("2026-05-01")
def test_dropdown_includes_confs_without_talks():
    """Dropdown includes conferences even if they have no talks or year data."""
    confs = [
        _conf("Active", {2026: _year(conference_start=date(2026, 6, 1))}),
        _conf("Empty", {}),
    ]
    all_confs, _, _ = build_detail_nav(confs, "Active")
    assert "Empty" in all_confs
