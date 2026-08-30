from confetti.models import Conference, Talk, TalkEntry, TalkStatus, YearEntry
from confetti.views.talk_stats import save_talk_stats


def _conf(name: str, years: dict[int, YearEntry]) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years=years,
    )


def _year(*talks: tuple[str, TalkStatus]) -> YearEntry:
    return YearEntry(
        talks=[TalkEntry(talk=talk_id, status=status, title=f"Title {talk_id}") for talk_id, status in talks]
    )


def test_save_talk_stats_writes_summary_table(tmp_path, monkeypatch):
    monkeypatch.setattr("confetti.views.talk_stats.TALK_STATS_FILE", tmp_path / "talk_stats.md")

    confs = [
        _conf(
            "Conf A",
            {2025: _year(("estimation", TalkStatus.rejected)), 2026: _year(("estimation", TalkStatus.accepted))},
        ),
        _conf("Conf B", {2026: _year(("estimation", TalkStatus.rejected), ("biases", TalkStatus.accepted))}),
    ]
    talks = [Talk(id="estimation", title="Estimation"), Talk(id="biases", title="Biases")]

    save_talk_stats(confs, talks)

    result = (tmp_path / "talk_stats.md").read_text()
    assert "| Estimation | 1        | 2        | 0         | 0         | 33%  |" in result


def test_save_talk_stats_includes_submission_history(tmp_path, monkeypatch):
    monkeypatch.setattr("confetti.views.talk_stats.TALK_STATS_FILE", tmp_path / "talk_stats.md")

    confs = [_conf("DevoxxUK", {2026: _year(("nobody-cares", TalkStatus.rejected))})]
    talks = [Talk(id="nobody-cares", title="Nobody Cares")]

    save_talk_stats(confs, talks)

    result = (tmp_path / "talk_stats.md").read_text()
    assert "- DevoxxUK 2026: rejected" in result


def test_save_talk_stats_pending_and_withdrawn(tmp_path, monkeypatch):
    monkeypatch.setattr("confetti.views.talk_stats.TALK_STATS_FILE", tmp_path / "talk_stats.md")

    confs = [
        _conf("Conf A", {2026: _year(("talk-a", TalkStatus.submitted))}),
        _conf("Conf B", {2025: _year(("talk-a", TalkStatus.withdrawn))}),
    ]
    talks = [Talk(id="talk-a", title="Talk A")]

    save_talk_stats(confs, talks)

    result = (tmp_path / "talk_stats.md").read_text()
    assert "| Talk A | 0        | 0        | 0         | 1         | -    |" in result


def test_save_talk_stats_ends_with_the_yearly_submission_stats(tmp_path, monkeypatch):
    """The same numbers the Submissions section of /past shows, sliced by the year the CFP closed."""
    monkeypatch.setattr("confetti.views.talk_stats.TALK_STATS_FILE", tmp_path / "talk_stats.md")

    confs = [
        _conf("Conf A", {2026: _year(("talk-a", TalkStatus.accepted))}),
        _conf("Conf B", {2026: _year(("talk-a", TalkStatus.withdrawn))}),
        _conf("Conf C", {2026: _year(("talk-a", TalkStatus.rejected))}),
    ]
    talks = [Talk(id="talk-a", title="Talk A")]

    save_talk_stats(confs, talks)

    result = (tmp_path / "talk_stats.md").read_text()
    assert result.endswith("""## Conference submissions per year

The year is the one the CFP closed in - when I did the submitting, not when the conference happened.
A waitlist counts as a rejection; anything still waiting for an answer counts as nothing at all.

| Year | Accepted | Rejected | Withdrawn | Waiting | Rate      | Without withdrawn |
|------|----------|----------|-----------|---------|-----------|-------------------|
| 2026 | 1        | 1        | 1         | 0       | 1/3 (33%) | 1/2 (50%)         |
| All  | 1        | 1        | 1         | 0       | 1/3 (33%) | 1/2 (50%)         |

### 2026
- Conf A 2026: accepted (CFP closed ~31 Dec 2026) - Title talk-a
- Conf B 2026: withdrawn (CFP closed ~31 Dec 2026) - Title talk-a
- Conf C 2026: rejected (CFP closed ~31 Dec 2026) - Title talk-a
""")
