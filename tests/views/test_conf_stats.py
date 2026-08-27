from datetime import date

from confetti.models import Cfp, Conference, TalkEntry, TalkStatus, YearEntry
from confetti.views.conf_stats import build_conf_summaries
from confetti.views.conf_stats import build_submission_boxes
from confetti.views.conf_stats import conf_acceptance_by_year
from confetti.views.conf_stats import edition_outcome


def _conf(name: str, years: dict[int, YearEntry], cfp: Cfp | None = None) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
        cfp=cfp,
    )


def _cfp(presumed_close: str) -> Cfp:
    return Cfp(url=None, site=None, formats=None, notes=None, presumed_open=None, presumed_close=presumed_close)


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


def test_acceptance_by_year_splits_years():
    confs = [
        _conf("Alpha", {2025: _year(TalkStatus.accepted), 2026: _year(TalkStatus.rejected)}),
        _conf("Beta", {2026: _year(TalkStatus.accepted)}),
    ]
    result = conf_acceptance_by_year(build_conf_summaries(confs))
    assert [(y.year, y.accepted, y.total, y.rate) for y in result] == [(2026, 1, 2, 50), (2025, 1, 1, 100)]


def test_acceptance_by_year_excludes_withdrawn_from_second_rate():
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted)}),
        _conf("Beta", {2026: _year(TalkStatus.withdrawn)}),
    ]
    result = conf_acceptance_by_year(build_conf_summaries(confs))
    assert [(y.year, y.rate, y.total_no_withdrawn, y.rate_no_withdrawn) for y in result] == [(2026, 50, 1, 100)]


def test_acceptance_by_year_lists_conferences_per_outcome():
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted)}),
        _conf("Beta", {2026: _year(TalkStatus.rejected)}),
        _conf("Gamma", {2026: _year(TalkStatus.withdrawn)}),
    ]
    result = conf_acceptance_by_year(build_conf_summaries(confs))[0]
    assert (
        [c.name for c in result.accepted_confs],
        [c.name for c in result.rejected_confs],
        [c.name for c in result.withdrawn_confs],
    ) == (["Alpha"], ["Beta"], ["Gamma"])


def test_edition_outcome_withdrawn_beats_rejected():
    entry = _year(TalkStatus.withdrawn, TalkStatus.rejected)
    result = edition_outcome(entry)
    assert result == TalkStatus.withdrawn


def test_edition_outcome_waiting_beats_decided():
    entry = _year(TalkStatus.rejected, TalkStatus.submitted)
    result = edition_outcome(entry)
    assert result == TalkStatus.submitted


def test_submission_box_lists_only_the_accepted_talk():
    entry = _year(TalkStatus.rejected, TalkStatus.accepted, TalkStatus.submitted)
    result = build_submission_boxes([_conf("Conf", {2026: entry})])
    assert [box.talks for boxes in result.values() for box in boxes] == [["Talk 1"]]


def test_submission_box_lists_only_the_withdrawn_talk():
    entry = _year(TalkStatus.rejected, TalkStatus.withdrawn)
    result = build_submission_boxes([_conf("Conf", {2026: entry})])
    assert [box.talks for boxes in result.values() for box in boxes] == [["Talk 1"]]


def test_submission_box_lists_every_rejection_including_sidelined():
    entry = _year(TalkStatus.rejected, TalkStatus.sidelined)
    result = build_submission_boxes([_conf("Conf", {2026: entry})])
    assert [box.talks for boxes in result.values() for box in boxes] == [["Talk 0", "Talk 1"]]


def test_submission_boxes_use_the_factual_cfp_close_year():
    confs = [
        _conf(
            "Conf",
            {
                2026: YearEntry(
                    conference_start=date(2026, 3, 1), cfp_close=date(2025, 10, 1), talks=[TalkEntry(talk="a")]
                )
            },
        )
    ]
    result = build_submission_boxes(confs)
    assert {year: [box.name for box in boxes] for year, boxes in result.items()} == {2025: ["Conf"]}


def test_submission_boxes_fall_back_to_the_presumed_cfp_close():
    confs = [
        _conf(
            "Conf",
            {2026: YearEntry(conference_start=date(2026, 11, 1), talks=[TalkEntry(talk="a")])},
            cfp=_cfp("06-30"),
        )
    ]
    result = build_submission_boxes(confs)
    assert {year: [box.name for box in boxes] for year, boxes in result.items()} == {2026: ["Conf"]}


def test_presumed_close_after_the_conference_belongs_to_the_year_before():
    confs = [
        _conf(
            "Conf",
            {2026: YearEntry(conference_start=date(2026, 3, 1), talks=[TalkEntry(talk="a")])},
            cfp=_cfp("10-01"),
        )
    ]
    result = build_submission_boxes(confs)
    assert {year: [box.name for box in boxes] for year, boxes in result.items()} == {2025: ["Conf"]}


def test_submission_boxes_guess_120_days_before_the_conference():
    """No dates at all: a CFP is assumed to open 180 days out and run 60, so it closed 120 days out."""
    confs = [
        _conf("Late", {2026: YearEntry(conference_start=date(2026, 11, 1), talks=[TalkEntry(talk="a")])}),
        _conf("Early", {2026: YearEntry(conference_start=date(2026, 3, 1), talks=[TalkEntry(talk="b")])}),
        _conf("Older", {2025: YearEntry(conference_start=date(2025, 5, 1), talks=[TalkEntry(talk="c")])}),
    ]
    result = build_submission_boxes(confs)
    assert {year: [box.name for box in boxes] for year, boxes in result.items()} == {
        2026: ["Late"],
        2025: ["Older", "Early"],
    }
