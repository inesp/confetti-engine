from datetime import date
from unittest.mock import patch

import pytest
import yaml

from confetti.models import Conference
from confetti.scouting.confs import ScoutResult
from confetti.scouting.scout_agent import _build_prompt, scout_conferences

# The 2026 edition is over by September 2026, so the next one to scout is 2027.
_CERN = """- name: Voxxed Days CERN
  city: Meyrin
  country: Switzerland
  website: https://voxxeddays.ch/
  cfp:
    url: https://vdcern26.cfp.dev/
    site: cfp.dev
    formats:
    notes:
    presumed_open: 09-01
    presumed_close: 10-21
  presumed:
    conference_start: 02-10
    conference_end: 02-10
  years:
    2026:
      conference_start: 2026-02-10
      conference_end: 2026-02-10
      cfp_close: 2025-10-21
      notify: mid-November 2025
"""

_CERN_2027_START_KNOWN = _CERN + """    2027:
      conference_start: 2027-02-09
"""

_PAST_EDITION = """{"conferences": [{"name": "Voxxed Days CERN", "cfp_open": null, "cfp_close": "2025-10-21",
"conference_start": "2026-02-10", "conference_end": "2026-02-10", "notify": "mid-November 2025",
"source": "https://vdc26.voxxeddays.ch/", "notes": null}]}"""

_NEXT_EDITION = """{"conferences": [{"name": "Voxxed Days CERN", "cfp_open": "2026-09-15", "cfp_close": "2026-10-20",
"conference_start": "2027-02-09", "conference_end": "2027-02-09", "notify": null,
"source": "https://vdcern27.cfp.dev/", "notes": null}]}"""

_YEARS_2026 = {
    2026: {
        "conference_start": date(2026, 2, 10),
        "conference_end": date(2026, 2, 10),
        "cfp_close": date(2025, 10, 21),
        "notify": "mid-November 2025",
    },
}


@pytest.fixture(autouse=True)
def _september_2026():
    # Patched instead of freezegun: ruamel can't write freezegun's fake dates back to YAML.
    with patch("confetti.models.date") as mock_date:
        mock_date.today.return_value = date(2026, 9, 18)
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
        yield


def _conf(tmp_path, monkeypatch, text: str = _CERN) -> Conference:
    monkeypatch.setattr("confetti.models.CONFERENCES_DIR", tmp_path)
    (tmp_path / "test.yaml").write_text(text)
    return Conference(filename="test.yaml", **yaml.safe_load(text)[0])


def _scout(conf: Conference, response: str) -> list[ScoutResult]:
    with patch("confetti.scouting.scout_agent.reset_log"):
        with patch("confetti.scouting.scout_agent.run_claude", return_value=response):
            return scout_conferences([conf])


def _reload_years(tmp_path) -> dict:
    with open(tmp_path / "test.yaml") as handle:
        return yaml.safe_load(handle)[0]["years"]


def test_prompt_asks_for_next_edition_once_this_years_is_over(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    result = _build_prompt([conf])
    assert "- Voxxed Days CERN (Meyrin, Switzerland), 2027 edition\n" in result


def test_scout_writes_dates_under_next_edition_year(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    _scout(conf, _NEXT_EDITION)
    result = _reload_years(tmp_path)
    assert result == {
        **_YEARS_2026,
        2027: {
            "cfp_open": date(2026, 9, 15),
            "cfp_close": date(2026, 10, 20),
            "conference_start": date(2027, 2, 9),
            "conference_end": date(2027, 2, 9),
        },
    }


def test_scout_ignores_dates_from_past_edition(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    _scout(conf, _PAST_EDITION)
    result = _reload_years(tmp_path)
    assert result == _YEARS_2026


def test_scout_outcome_says_nothing_written_for_past_edition(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    result = _scout(conf, _PAST_EDITION)
    assert result[0].outcome == (
        "Nothing written: conference_start 2026-02-10 is not in 2027, looks like another edition\n"
        "Source: https://vdc26.voxxeddays.ch/"
    )


def test_scout_outcome_separates_written_from_already_set(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch, text=_CERN_2027_START_KNOWN)
    result = _scout(conf, _NEXT_EDITION)
    assert result[0].outcome == (
        "Written: cfp_open: 2026-09-15, cfp_close: 2026-10-20, conference_end: 2027-02-09\n"
        "Already set: conference_start: 2027-02-09\n"
        "Source: https://vdcern27.cfp.dev/"
    )
