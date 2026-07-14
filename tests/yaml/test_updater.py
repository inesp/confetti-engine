from datetime import date

import yaml

from confetti.models import Conference
from confetti.yaml.yaml_updater import (
    add_talk,
    update_cfp_url,
    update_cfp_window,
    update_difficulty,
    update_favorite,
    update_skip,
    update_talk_title,
    update_year_skip,
)

_BASE = """- name: Conf
  city: Test
  country: Netherlands
  website: https://example.com
  years:
    2026:
      talks:
      - talk: impacts
        status: submitted
        title: Old Title
"""


_TWO_SPACED = """- name: Conf
  city: Test
  country: Netherlands

  website: https://example.com

  years:
    2026:
      talks:
      - talk: impacts
        status: submitted
        title: Old Title

- name: Other
  city: Test
  country: Netherlands
  website: https://other.com
"""


def _conf(tmp_path, monkeypatch) -> Conference:
    monkeypatch.setattr("confetti.models.CONFERENCES_DIR", tmp_path)
    (tmp_path / "test.yaml").write_text(_BASE)
    return Conference(
        filename="test.yaml",
        name="Conf",
        city="Test",
        country="Netherlands",
        website="https://example.com",
    )


def _reload(tmp_path) -> dict:
    with open(tmp_path / "test.yaml") as handle:
        return yaml.safe_load(handle)[0]


def test_update_favorite_sets_flag(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_favorite(conf, True)
    result = _reload(tmp_path)
    assert result["favorite"] is True


def test_update_favorite_lands_after_website(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_favorite(conf, True)
    keys = list(_reload(tmp_path).keys())
    assert keys[keys.index("website") + 1] == "favorite"


def test_update_favorite_clears_flag(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_favorite(conf, True)
    update_favorite(conf, False)
    result = _reload(tmp_path)
    assert "favorite" not in result


def test_update_skip_lands_after_website(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_skip(conf, True)
    keys = list(_reload(tmp_path).keys())
    assert keys[keys.index("website") + 1] == "skip"


def test_update_difficulty_sets_longshot(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_difficulty(conf, "longshot")
    result = _reload(tmp_path)
    assert result["difficulty"] == "longshot"


def test_update_year_skip_sets_edition_flag(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_year_skip(conf, 2026, True)
    result = _reload(tmp_path)
    assert result["years"][2026]["skip"] is True


def test_update_cfp_window_writes_both_dates(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_cfp_window(conf, 2026, date(2026, 8, 1), date(2026, 9, 1))
    result = _reload(tmp_path)["years"][2026]
    assert (result["cfp_open"], result["cfp_close"]) == (date(2026, 8, 1), date(2026, 9, 1))


def test_update_cfp_url_creates_cfp_block(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_cfp_url(conf, "https://cfp.example.com")
    result = _reload(tmp_path)
    assert result["cfp"]["url"] == "https://cfp.example.com"


def test_update_talk_title_edits_existing_talk(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    update_talk_title(conf, 2026, "impacts", "New Title")
    result = _reload(tmp_path)["years"][2026]["talks"][0]
    assert result["title"] == "New Title"


def test_add_talk_appends_submission(tmp_path, monkeypatch):
    conf = _conf(tmp_path, monkeypatch)
    add_talk(conf, 2026, "estimation", "A Fresh Talk")
    result = _reload(tmp_path)["years"][2026]["talks"][-1]
    assert result == {"talk": "estimation", "status": "submitted", "title": "A Fresh Talk"}


def test_write_does_not_wrap_long_values(tmp_path, monkeypatch):
    monkeypatch.setattr("confetti.models.CONFERENCES_DIR", tmp_path)
    long_note = "word " * 60  # ~300 chars, well past the old ~80-char wrap width
    (tmp_path / "test.yaml").write_text(
        "- name: Conf\n"
        "  city: Test\n"
        "  country: Netherlands\n"
        "  website: https://example.com\n"
        f'  notes: "{long_note.strip()}"\n'
    )
    conf = Conference(
        filename="test.yaml", name="Conf", city="Test", country="Netherlands", website="https://example.com"
    )
    update_favorite(conf, True)
    longest_line = max(len(line) for line in (tmp_path / "test.yaml").read_text().splitlines())
    assert longest_line > 250


def test_write_compacts_within_conf_keeps_one_blank_between(tmp_path, monkeypatch):
    monkeypatch.setattr("confetti.models.CONFERENCES_DIR", tmp_path)
    (tmp_path / "test.yaml").write_text(_TWO_SPACED)
    conf = Conference(
        filename="test.yaml", name="Conf", city="Test", country="Netherlands", website="https://example.com"
    )
    update_favorite(conf, True)
    blank_lines = (tmp_path / "test.yaml").read_text().count("\n\n")
    assert blank_lines == 1
