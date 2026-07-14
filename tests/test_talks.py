from confetti import talks
from confetti.talks import TalkDescription


def test_load_skips_readme_and_videos(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "videos.md").write_text("# Videos")
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    assert talks.load_talk_descriptions() == []


def test_load_parses_title_and_description(tmp_path, monkeypatch):
    (tmp_path / "estimation.md").write_text(
        "# Titles\n\n### Public\n- Software estimation is a delusion\n\n# Description\n\nFirst line.\nSecond line.\n"
    )
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    response = talks.load_talk_descriptions()

    assert response == [
        TalkDescription(
            talk_id="estimation", title="Software estimation is a delusion", description="First line. Second line."
        )
    ]


def test_load_title_only_no_description(tmp_path, monkeypatch):
    (tmp_path / "my-talk.md").write_text("# Titles\n\n### Public\n- Just a title\n")
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    response = talks.load_talk_descriptions()
    assert response == [TalkDescription(talk_id="my-talk", title="Just a title", description="")]


def test_load_description_limited_to_3_lines(tmp_path, monkeypatch):
    (tmp_path / "verbose.md").write_text(
        "# Titles\n\n- My Talk\n\n# Description\n\nLine 1.\nLine 2.\nLine 3.\nLine 4.\nLine 5.\n"
    )
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    response = talks.load_talk_descriptions()
    assert response == [TalkDescription(talk_id="verbose", title="My Talk", description="Line 1. Line 2. Line 3.")]


def test_load_multiple_talks_sorted(tmp_path, monkeypatch):
    (tmp_path / "beta.md").write_text("# Titles\n\n- Beta Talk\n")
    (tmp_path / "alpha.md").write_text("# Titles\n\n- Alpha Talk\n")
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    response = talks.load_talk_descriptions()
    assert response == [
        TalkDescription(talk_id="alpha", title="Alpha Talk", description=""),
        TalkDescription(talk_id="beta", title="Beta Talk", description=""),
    ]


def test_load_no_title_skips_file(tmp_path, monkeypatch):
    (tmp_path / "empty.md").write_text("# Description\n\nSome text but no title.\n")
    monkeypatch.setattr(talks, "TALKS_DIR", tmp_path)
    response = talks.load_talk_descriptions()
    assert response == []
