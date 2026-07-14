from datetime import date
from unittest.mock import patch

from confetti.models import Cfp, Conference, Presumed, YearEntry
from confetti.scouting.confs import SkipReason, _filter_conferences


def _conf(
    name: str = "TestConf",
    years: dict[int, YearEntry] | None = None,
    presumed: Presumed | None = None,
    cfp: Cfp | None = None,
    skip: bool = False,
) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years or {},
        presumed=presumed or Presumed(),
        cfp=cfp,
        skip=skip,
    )


@patch("confetti.models.date")
@patch("confetti.scouting.confs.date")
def test_factual_cfp_close_is_skipped(mock_date, mock_models_date):
    mock_date.today.return_value = date(2026, 3, 1)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    mock_models_date.today.return_value = date(2026, 3, 1)
    mock_models_date.side_effect = lambda *args, **kw: date(*args, **kw)
    conf = _conf(
        years={2026: YearEntry(cfp_close=date(2026, 4, 15), conference_start=date(2026, 6, 10))},
        presumed=Presumed(conference_start="06-10"),
    )
    to_scout, skipped = _filter_conferences([conf])
    assert to_scout == []
    assert len(skipped) == 1
    assert skipped[0].reason == SkipReason.all_dates_known


@patch("confetti.models.date")
@patch("confetti.scouting.confs.date")
def test_presumed_cfp_close_is_not_skipped_as_all_dates_known(mock_date, mock_models_date):
    mock_date.today.return_value = date(2026, 3, 1)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    mock_models_date.today.return_value = date(2026, 3, 1)
    mock_models_date.side_effect = lambda *args, **kw: date(*args, **kw)
    conf = _conf(
        cfp=Cfp(url=None, site=None, formats=None, notes=None, presumed_open=None, presumed_close="04-15"),
        presumed=Presumed(conference_start="06-10"),
    )
    to_scout, skipped = _filter_conferences([conf])
    # Should not be skipped as all_dates_known since the close date is only presumed
    for result in skipped:
        assert result.reason != SkipReason.all_dates_known


@patch("confetti.models.date")
@patch("confetti.scouting.confs.date")
def test_factual_cfp_open_and_close_and_conference_start_all_known(mock_date, mock_models_date):
    mock_date.today.return_value = date(2026, 3, 1)
    mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
    mock_models_date.today.return_value = date(2026, 3, 1)
    mock_models_date.side_effect = lambda *args, **kw: date(*args, **kw)
    conf = _conf(
        years={
            2026: YearEntry(
                cfp_open=date(2026, 2, 1),
                cfp_close=date(2026, 4, 15),
                conference_start=date(2026, 6, 10),
            )
        },
    )
    to_scout, skipped = _filter_conferences([conf])
    assert to_scout == []
    assert len(skipped) == 1
    assert skipped[0].reason == SkipReason.all_dates_known
