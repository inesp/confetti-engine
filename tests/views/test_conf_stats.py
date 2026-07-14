from confetti.models import Conference, TalkEntry, TalkStatus, YearEntry
from confetti.views.conf_stats import build_conf_summaries


def _conf(name: str, years: dict[int, YearEntry]) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
    )


def _year(*statuses: TalkStatus) -> YearEntry:
    return YearEntry(talks=[TalkEntry(talk=f"talk-{i}", status=s, title=f"Talk {i}") for i, s in enumerate(statuses)])


def test_all_rejected():
    confs = [_conf("Conf", {2026: _year(TalkStatus.rejected)})]
    result = build_conf_summaries(confs)
    assert result[0].rejected == 1
    assert result[0].withdrawn == 0


def test_all_withdrawn():
    confs = [_conf("Conf", {2026: _year(TalkStatus.withdrawn)})]
    result = build_conf_summaries(confs)
    assert result[0].withdrawn == 1
    assert result[0].rejected == 0


def test_mix_withdrawn_and_rejected_counts_as_withdrawn():
    """EuroPython bug: one talk withdrawn, one rejected - should count as withdrawn, not rejected."""
    confs = [_conf("EuroPython", {2026: _year(TalkStatus.withdrawn, TalkStatus.rejected)})]
    result = build_conf_summaries(confs)
    assert result[0].withdrawn == 1
    assert result[0].rejected == 0


def test_accepted_beats_withdrawn():
    confs = [_conf("Conf", {2026: _year(TalkStatus.accepted, TalkStatus.withdrawn)})]
    result = build_conf_summaries(confs)
    assert result[0].accepted == 1
    assert result[0].withdrawn == 0


def test_accepted_beats_rejected():
    confs = [_conf("Conf", {2026: _year(TalkStatus.accepted, TalkStatus.rejected)})]
    result = build_conf_summaries(confs)
    assert result[0].accepted == 1
    assert result[0].rejected == 0


def test_multiple_years():
    confs = [
        _conf(
            "Conf",
            {
                2025: _year(TalkStatus.rejected),
                2026: _year(TalkStatus.accepted),
            },
        )
    ]
    result = build_conf_summaries(confs)
    assert result[0].accepted == 1
    assert result[0].rejected == 1
