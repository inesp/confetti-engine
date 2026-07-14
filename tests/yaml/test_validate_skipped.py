from confetti.yaml.yaml_parser import ConfError
from confetti.yaml.yaml_parser import ErrorLevel
from confetti.yaml.yaml_parser import _validate_skipped_file


def test_valid_list(tmp_path):
    f = tmp_path / "skipped.yaml"
    f.write_text("- SomeConf\n- Another\n")
    result = _validate_skipped_file(f)
    assert result == []


def test_empty_file(tmp_path):
    f = tmp_path / "skipped.yaml"
    f.write_text("")
    result = _validate_skipped_file(f)
    assert result == []


def test_yaml_parse_error(tmp_path):
    f = tmp_path / "skipped.yaml"
    f.write_text(": : : broken\n  bad:\n-")
    result = _validate_skipped_file(f)
    # Can't assert the whole ConfError because the YAML error message varies
    assert len(result) == 1
    assert result[0].file == "skipped.yaml"
    assert result[0].level == ErrorLevel.error


def test_non_list(tmp_path):
    f = tmp_path / "skipped.yaml"
    f.write_text("key: value\n")
    result = _validate_skipped_file(f)
    assert result == [ConfError("skipped.yaml", "-", ["Expected a list, got dict"])]


def test_non_string_entries(tmp_path):
    f = tmp_path / "skipped.yaml"
    f.write_text("- ValidConf\n- 42\n- true\n")
    result = _validate_skipped_file(f)
    assert result == [ConfError("skipped.yaml", "-", ["Non-string entries: 42, True"], level=ErrorLevel.warning)]
