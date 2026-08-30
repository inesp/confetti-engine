from datetime import date

from confetti.models import Cfp, Conference, TalkEntry, TalkStatus, YearEntry
from confetti.views.conf_stats import ConfSubmissionSummary
from confetti.views.conf_stats import build_conf_summaries
from confetti.views.conf_stats import build_submissions
from confetti.views.conf_stats import edition_outcome
from confetti.views.conf_stats import submissions_by_year


def _summaries(confs: list[Conference]) -> list[ConfSubmissionSummary]:
    return build_conf_summaries(build_submissions(confs))


def _years(confs: list[Conference]) -> list:
    return submissions_by_year(build_submissions(confs))


def _boxes(confs: list[Conference]) -> dict[int, list[str]]:
    return {year_subs.year: [box.name for box in year_subs.boxes] for year_subs in _years(confs)}


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
    result = _summaries(confs)
    assert result[0].rejected == 1
    assert result[0].withdrawn == 0


def test_all_withdrawn():
    confs = [_conf("Conf", {2026: _year(TalkStatus.withdrawn)})]
    result = _summaries(confs)
    assert result[0].withdrawn == 1
    assert result[0].rejected == 0


def test_mix_withdrawn_and_rejected_counts_as_withdrawn():
    """EuroPython bug: one talk withdrawn, one rejected - should count as withdrawn, not rejected."""
    confs = [_conf("EuroPython", {2026: _year(TalkStatus.withdrawn, TalkStatus.rejected)})]
    result = _summaries(confs)
    assert result[0].withdrawn == 1
    assert result[0].rejected == 0


def test_accepted_beats_withdrawn():
    confs = [_conf("Conf", {2026: _year(TalkStatus.accepted, TalkStatus.withdrawn)})]
    result = _summaries(confs)
    assert result[0].accepted == 1
    assert result[0].withdrawn == 0


def test_accepted_beats_rejected():
    confs = [_conf("Conf", {2026: _year(TalkStatus.accepted, TalkStatus.rejected)})]
    result = _summaries(confs)
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
    result = _summaries(confs)
    assert result[0].accepted == 1
    assert result[0].rejected == 1


def test_acceptance_by_year_splits_years():
    confs = [
        _conf("Alpha", {2025: _year(TalkStatus.accepted), 2026: _year(TalkStatus.rejected)}),
        _conf("Beta", {2026: _year(TalkStatus.accepted)}),
    ]
    result = _years(confs)
    assert [(y.year, y.accepted, y.total, y.rate) for y in result] == [(2026, 1, 2, 50), (2025, 1, 1, 100)]


def test_acceptance_by_year_excludes_withdrawn_from_second_rate():
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted)}),
        _conf("Beta", {2026: _year(TalkStatus.withdrawn)}),
    ]
    result = _years(confs)
    assert [(y.year, y.rate, y.total_no_withdrawn, y.rate_no_withdrawn) for y in result] == [(2026, 50, 1, 100)]


def test_acceptance_by_year_carries_the_conferences_behind_the_number():
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted)}),
        _conf("Beta", {2026: _year(TalkStatus.rejected)}),
        _conf("Gamma", {2026: _year(TalkStatus.withdrawn)}),
    ]
    result = _years(confs)[0]
    assert [(box.name, box.status) for box in result.boxes] == [
        ("Alpha", TalkStatus.accepted),
        ("Beta", TalkStatus.rejected),
        ("Gamma", TalkStatus.withdrawn),
    ]


def test_acceptance_year_is_the_cfp_close_year_not_the_conference_year():
    """Bitbash bug: a CFP that closed in 2025 counts towards 2025, even though the conference is 2026."""
    confs = [
        _conf(
            "Bitbash",
            {
                2026: YearEntry(
                    conference_start=date(2026, 4, 1),
                    cfp_close=date(2025, 9, 15),
                    talks=[TalkEntry(talk="a", status=TalkStatus.rejected)],
                )
            },
        ),
        _conf(
            "Alpha",
            {
                2025: YearEntry(
                    conference_start=date(2025, 6, 1),
                    cfp_close=date(2025, 3, 1),
                    talks=[TalkEntry(talk="b", status=TalkStatus.accepted)],
                )
            },
        ),
    ]
    result = _years(confs)
    assert [(y.year, y.accepted, y.total, y.rate) for y in result] == [(2025, 1, 2, 50)]


def test_the_year_strip_and_the_year_rate_count_the_same_submissions():
    """One dataset, two slices: every box on the strip is a submission the rate knows about."""
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted), 2025: _year(TalkStatus.rejected)}),
        _conf("Beta", {2026: _year(TalkStatus.withdrawn)}),
    ]
    result = [(y.year, len(y.boxes), y.total + y.waiting) for y in _years(confs)]
    assert result == [(2026, 2, 2), (2025, 1, 1)]


def test_a_submission_still_waiting_shows_on_the_strip_but_not_in_the_rate():
    confs = [
        _conf("Alpha", {2026: _year(TalkStatus.accepted)}),
        _conf("Beta", {2026: _year(TalkStatus.submitted)}),
    ]
    result = _years(confs)[0]
    assert (len(result.boxes), result.waiting, result.accepted, result.total, result.rate) == (2, 1, 1, 1, 100)


def test_a_conference_still_waiting_stays_out_of_the_pills():
    confs = [_conf("Alpha", {2026: _year(TalkStatus.submitted)})]
    result = _summaries(confs)
    assert result == []


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
    result = build_submissions([_conf("Conf", {2026: entry})])
    assert [box.talks for box in result] == [["Talk 1"]]


def test_submission_box_lists_only_the_withdrawn_talk():
    entry = _year(TalkStatus.rejected, TalkStatus.withdrawn)
    result = build_submissions([_conf("Conf", {2026: entry})])
    assert [box.talks for box in result] == [["Talk 1"]]


def test_submission_box_lists_every_rejection_including_sidelined():
    entry = _year(TalkStatus.rejected, TalkStatus.sidelined)
    result = build_submissions([_conf("Conf", {2026: entry})])
    assert [box.talks for box in result] == [["Talk 0", "Talk 1"]]


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
    result = _boxes(confs)
    assert result == {2025: ["Conf"]}


def test_submission_boxes_fall_back_to_the_presumed_cfp_close():
    confs = [
        _conf(
            "Conf",
            {2026: YearEntry(conference_start=date(2026, 11, 1), talks=[TalkEntry(talk="a")])},
            cfp=_cfp("06-30"),
        )
    ]
    result = _boxes(confs)
    assert result == {2026: ["Conf"]}


def test_presumed_close_after_the_conference_belongs_to_the_year_before():
    confs = [
        _conf(
            "Conf",
            {2026: YearEntry(conference_start=date(2026, 3, 1), talks=[TalkEntry(talk="a")])},
            cfp=_cfp("10-01"),
        )
    ]
    result = _boxes(confs)
    assert result == {2025: ["Conf"]}


def test_submission_boxes_guess_120_days_before_the_conference():
    """No dates at all: a CFP is assumed to open 180 days out and run 60, so it closed 120 days out."""
    confs = [
        _conf("Late", {2026: YearEntry(conference_start=date(2026, 11, 1), talks=[TalkEntry(talk="a")])}),
        _conf("Early", {2026: YearEntry(conference_start=date(2026, 3, 1), talks=[TalkEntry(talk="b")])}),
        _conf("Older", {2025: YearEntry(conference_start=date(2025, 5, 1), talks=[TalkEntry(talk="c")])}),
    ]
    result = _boxes(confs)
    assert result == {
        2026: ["Late"],
        2025: ["Older", "Early"],
    }


def test_pill_gradient_is_flat_when_every_year_landed_the_same():
    summary = ConfSubmissionSummary(name="Conf", accepted=3)
    result = summary.pill_gradient
    assert result == "linear-gradient(90deg, #dcfce7 0%, #dcfce7 50.0%, #dcfce7 100%)"


def test_pill_gradient_washes_from_rejected_into_accepted():
    summary = ConfSubmissionSummary(name="Conf", accepted=1, rejected=1)
    result = summary.pill_gradient
    assert result == "linear-gradient(90deg, #fee2e2 0%, #fee2e2 25.0%, #dcfce7 75.0%, #dcfce7 100%)"


def test_pill_gradient_passes_through_withdrawn_in_the_middle():
    summary = ConfSubmissionSummary(name="Conf", accepted=1, rejected=1, withdrawn=1)
    result = summary.pill_gradient
    assert result == ("linear-gradient(90deg, #fee2e2 0%, #fee2e2 16.7%, #ffedd5 50.0%, #dcfce7 83.3%, #dcfce7 100%)")


def test_pill_gradient_weights_bands_by_year_count():
    summary = ConfSubmissionSummary(name="Conf", accepted=3, rejected=1)
    result = summary.pill_gradient
    assert result == "linear-gradient(90deg, #fee2e2 0%, #fee2e2 12.5%, #dcfce7 62.5%, #dcfce7 100%)"


def test_pill_border_goes_neutral_once_the_record_is_mixed():
    summary = ConfSubmissionSummary(name="Conf", accepted=1, rejected=1)
    result = summary.pill_border
    assert result == "border border-gray-300"
