from pathlib import Path

from confetti.yaml import yaml_parser
from confetti.yaml.yaml_parser import load_and_validate_conferences

REPO_ROOT = Path(__file__).parent.parent.parent


def test_bundled_sample_conferences_still_validate(monkeypatch):
    # The sample data ships with the engine; a model change that forgets to migrate it breaks every fresh install.
    monkeypatch.setattr(yaml_parser, "CONFERENCES_DIR", REPO_ROOT / "conferences")
    monkeypatch.setattr(yaml_parser, "TALKS_FILE", REPO_ROOT / "talks" / "talks.yml")
    monkeypatch.setattr(yaml_parser, "_cache", None)

    _, errors = load_and_validate_conferences()

    result = [(error.file, error.conference, error.errors) for error in errors]
    assert result == []
