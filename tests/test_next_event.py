from datetime import date

from freezegun import freeze_time

from confetti.constants import CFP_ESTIMATED_DURATION
from confetti.models import Cfp, Conference, YearEntry


def _conf(entry: YearEntry, cfp: Cfp | None = None) -> Conference:
    return Conference(
        filename="test.yaml",
        name="Conf",
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years={2027: entry},
        cfp=cfp,
    )


def _presumed_close(close_md: str) -> Cfp:
    return Cfp(url=None, site=None, formats=None, notes=None, presumed_open=None, presumed_close=close_md)


@freeze_time("2026-10-12")
def test_factual_open_without_close_falls_back_to_presumed_close():
    conf = _conf(
        YearEntry(conference_start=date(2027, 3, 31), cfp_open=date(2026, 10, 7)),
        cfp=_presumed_close("01-31"),
    )
    event = conf.next_event
    result = (event.cfp_open, event.cfp_close, event.cfp_close_is_factual)
    assert result == (date(2026, 10, 7), date(2027, 1, 31), False)


@freeze_time("2026-10-12")
def test_factual_open_without_any_close_guesses_the_usual_duration():
    conf = _conf(YearEntry(conference_start=date(2027, 3, 31), cfp_open=date(2026, 10, 7)))
    event = conf.next_event
    result = (event.cfp_open, event.cfp_close, event.cfp_close_is_factual)
    assert result == (date(2026, 10, 7), date(2026, 10, 7) + CFP_ESTIMATED_DURATION, False)


@freeze_time("2026-10-12")
def test_factual_open_and_close_stay_factual():
    conf = _conf(
        YearEntry(conference_start=date(2027, 3, 31), cfp_open=date(2026, 10, 7), cfp_close=date(2026, 12, 19)),
        cfp=_presumed_close("01-31"),
    )
    event = conf.next_event
    result = (event.cfp_open, event.cfp_close, event.cfp_close_is_factual)
    assert result == (date(2026, 10, 7), date(2026, 12, 19), True)
