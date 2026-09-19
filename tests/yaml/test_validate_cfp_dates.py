from confetti.yaml import yaml_parser
from confetti.yaml.yaml_parser import load_and_validate_conferences


def test_cfp_missing_presumed_dates_is_not_flagged(tmp_path, monkeypatch):
    # The 180/60-day defaults (CFP_BEFORE_CONFERENCE, CFP_ESTIMATED_DURATION) estimate missing CFP dates.
    conf_yaml = """\
- name: Test Conf
  city: Test City
  country: Netherlands
  website: https://example.com
  cfp:
    url:
    site:
    formats:
    notes:
    presumed_open:
    presumed_close:
"""
    (tmp_path / "test_conf.yaml").write_text(conf_yaml)
    monkeypatch.setattr(yaml_parser, "CONFERENCES_DIR", tmp_path)

    result = load_and_validate_conferences()

    assert result[1] == []
