from confetti.yaml import yaml_parser
from confetti.yaml.yaml_parser import ConfError
from confetti.yaml.yaml_parser import ErrorLevel
from confetti.yaml.yaml_parser import load_and_validate_conferences


def test_cfp_missing_presumed_dates_warns(tmp_path, monkeypatch):
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

    assert result[1] == [
        ConfError(
            file="test_conf.yaml",
            conference="Test Conf",
            errors=[
                "CFP is missing presumed_open and presumed_close. Fill in:\n"
                "      presumed_open: MM-DD\n"
                "      presumed_close: MM-DD"
            ],
            level=ErrorLevel.warning,
        )
    ]
