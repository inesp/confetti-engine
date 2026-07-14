from dataclasses import dataclass, field
from datetime import date

from confetti.constants import TALK_STATS_FILE
from confetti.models import Conference, Talk, TalkStatus


@dataclass
class TalkSubmission:
    conf_name: str
    year: int
    status: str
    title: str | None
    conf_date: date | None = None
    country_code: str = ""


@dataclass
class TalkStats:
    talk: Talk
    submissions: list[TalkSubmission] = field(default_factory=list)

    @property
    def _decided(self) -> list[TalkSubmission]:
        return [
            s
            for s in self.submissions
            if s.status in (TalkStatus.accepted, TalkStatus.rejected, TalkStatus.waitlisted)
        ]

    @property
    def _decided_with_sidelined(self) -> list[TalkSubmission]:
        return [
            s
            for s in self.submissions
            if s.status in (TalkStatus.accepted, TalkStatus.rejected, TalkStatus.sidelined, TalkStatus.waitlisted)
        ]

    @property
    def accepted_count(self) -> int:
        return sum(1 for s in self._decided if s.status == TalkStatus.accepted)

    @property
    def total_count(self) -> int:
        return len(self._decided)

    @property
    def total_count_with_sidelined(self) -> int:
        return len(self._decided_with_sidelined)

    @property
    def acceptance_rate(self) -> float:
        if not self._decided:
            return 0.0
        return self.accepted_count / self.total_count * 100

    @property
    def acceptance_rate_with_sidelined(self) -> float:
        if not self._decided_with_sidelined:
            return 0.0
        return self.accepted_count / self.total_count_with_sidelined * 100


def build_talk_stats(conferences: list[Conference], talks: list[Talk]) -> list[TalkStats]:
    stats_by_id: dict[str, TalkStats] = {}
    talks_by_id = {t.id: t for t in talks}

    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            if entry is None:
                continue
            for talk_entry in entry.talks:
                if talk_entry.talk not in stats_by_id:
                    talk_def = talks_by_id.get(talk_entry.talk)
                    if not talk_def:
                        continue
                    stats_by_id[talk_entry.talk] = TalkStats(talk=talk_def)
                stats_by_id[talk_entry.talk].submissions.append(
                    TalkSubmission(
                        conf_name=conf.name,
                        year=year,
                        status=talk_entry.status or "unknown",
                        title=talk_entry.title,
                        conf_date=entry.conference_start,
                        country_code=conf.country_code,
                    )
                )

    result = list(stats_by_id.values())
    for ts in result:
        ts.submissions.sort(key=lambda s: s.conf_date or date(s.year, 12, 31), reverse=True)
    result.sort(key=lambda ts: -ts.acceptance_rate)
    return result


def save_talk_stats(conferences: list[Conference], talks: list[Talk]) -> None:
    """Build talk stats and save them to talks/talk_stats.md."""
    stats = build_talk_stats(conferences, talks)
    lines = [
        "# Talk submission stats",
        "",
        "| Talk | Accepted | Rejected | Sidelined | Withdrawn | Rate |",
        "|------|----------|----------|-----------|-----------|------|",
    ]
    for ts in stats:
        decided = [
            s for s in ts.submissions if s.status in (TalkStatus.accepted, TalkStatus.rejected, TalkStatus.waitlisted)
        ]
        accepted = sum(1 for s in decided if s.status == TalkStatus.accepted)
        rejected = sum(1 for s in decided if s.status in (TalkStatus.rejected, TalkStatus.waitlisted))
        sidelined = sum(1 for s in ts.submissions if s.status == TalkStatus.sidelined)
        withdrawn = sum(1 for s in ts.submissions if s.status == TalkStatus.withdrawn)
        rate = f"{ts.acceptance_rate:.0f}%" if decided else "-"
        lines.append(f"| {ts.talk.title} | {accepted} | {rejected} | {sidelined} | {withdrawn} | {rate} |")

    lines.append("")
    lines.append("## Submission history")
    lines.append("")
    for ts in stats:
        lines.append(f"### {ts.talk.title}")
        for s in ts.submissions:
            lines.append(f"- {s.conf_name} {s.year}: {s.status}")
        lines.append("")

    TALK_STATS_FILE.write_text("\n".join(lines))
