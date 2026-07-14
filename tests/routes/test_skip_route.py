from confetti.app import create_app
from confetti.yaml import skipped


def test_skip_adds_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(skipped, "SKIPPED_FILE", tmp_path / "skipped.yaml")
    app = create_app()
    client = app.test_client()

    result = client.post("/discover/skip", json={"name": "SkipMe"})
    assert result.get_json() == {"ok": True}
    assert skipped.load_skipped() == ["SkipMe"]


def test_skip_no_name_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(skipped, "SKIPPED_FILE", tmp_path / "skipped.yaml")
    app = create_app()
    client = app.test_client()

    result = client.post("/discover/skip", json={})
    assert result.status_code == 400
