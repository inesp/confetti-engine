from confetti.models import Conference, HistorySummary, TalkEntry, TalkStatus, YearEntry


def _conf(years: dict[int, YearEntry | None]) -> Conference:
    return Conference(
        filename="test.yaml",
        name="TestConf",
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
    )


def _year(status: TalkStatus) -> YearEntry:
    return YearEntry(talks=[TalkEntry(talk="test-talk", status=status)])


def test_no_talks():
    conf = _conf({2026: YearEntry()})
    assert conf.history is None


def test_no_years():
    conf = _conf({})
    assert conf.history is None


def test_rejected_only():
    conf = _conf({2024: _year(TalkStatus.rejected), 2025: _year(TalkStatus.rejected)})
    assert conf.history == HistorySummary(applied=[2024, 2025], accepted=[], notes=[])


def test_accepted():
    conf = _conf({2024: _year(TalkStatus.rejected), 2025: _year(TalkStatus.accepted)})
    assert conf.history == HistorySummary(applied=[2024, 2025], accepted=[2025], notes=[])


def test_withdrawn():
    conf = _conf({2024: _year(TalkStatus.accepted), 2025: _year(TalkStatus.withdrawn)})
    assert conf.history == HistorySummary(applied=[2024, 2025], accepted=[2024], notes=["withdrawn 2025"])


def test_waitlisted():
    conf = _conf({2026: _year(TalkStatus.waitlisted)})
    assert conf.history == HistorySummary(applied=[2026], accepted=[], notes=["waitlisted 2026"])


def test_submitted():
    conf = _conf({2026: _year(TalkStatus.submitted)})
    assert conf.history == HistorySummary(applied=[2026], accepted=[], notes=[])


def test_years_sorted():
    conf = _conf({2026: _year(TalkStatus.rejected), 2024: _year(TalkStatus.accepted)})
    assert conf.history == HistorySummary(applied=[2024, 2026], accepted=[2024], notes=[])
