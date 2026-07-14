from confetti.yaml import skipped


def test_load_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(skipped, "SKIPPED_FILE", tmp_path / "skipped.yaml")
    result = skipped.load_skipped()
    assert result == []


def test_load_empty_file(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    f.write_text("")
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)
    result = skipped.load_skipped()
    assert result == []


def test_load_valid_list(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    f.write_text("- SomeConf\n- Another Conf\n")
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)
    result = skipped.load_skipped()
    assert result == ["SomeConf", "Another Conf"]


def test_load_malformed_yaml(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    f.write_text(": : : broken\n  bad:\n-")
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)
    result = skipped.load_skipped()
    assert result == []


def test_load_non_list(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    f.write_text("key: value\n")
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)
    result = skipped.load_skipped()
    assert result == []


def test_add_skipped(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)

    skipped.add_skipped("NewConf")
    result = skipped.load_skipped()
    assert result == ["NewConf"]

    skipped.add_skipped("SecondConf")
    result = skipped.load_skipped()
    assert result == ["NewConf", "SecondConf"]


def test_add_skipped_no_duplicates(tmp_path, monkeypatch):
    f = tmp_path / "skipped.yaml"
    f.write_text("- Existing\n")
    monkeypatch.setattr(skipped, "SKIPPED_FILE", f)

    skipped.add_skipped("Existing")
    result = skipped.load_skipped()
    assert result == ["Existing"]
