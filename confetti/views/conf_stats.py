from dataclasses import dataclass, field
from datetime import date

from confetti.models import Conference, TalkStatus

DECIDED_STATUSES = frozenset(
    {
        TalkStatus.accepted,
        TalkStatus.rejected,
        TalkStatus.sidelined,
        TalkStatus.waitlisted,
        TalkStatus.withdrawn,
    }
)


@dataclass
class ConfYearDetail:
    year: int
    status: str
    talks: list[str]
    conf_date: date | None = None


@dataclass
class ConfSubmissionSummary:
    name: str
    conf: Conference | None = None
    country_code: str = ""
    difficulty: str | None = None
    accepted: int = 0
    rejected: int = 0
    withdrawn: int = 0
    year_details: list[ConfYearDetail] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.accepted + self.rejected + self.withdrawn

    @property
    def hover_text(self) -> str:
        parts = []
        for yd in sorted(self.year_details, key=lambda d: d.year):
            parts.append(f"{yd.year} ({yd.status}): {', '.join(yd.talks)}")
        return " | ".join(parts)


def build_conf_summaries(conferences: list[Conference]) -> list[ConfSubmissionSummary]:
    by_name: dict[str, ConfSubmissionSummary] = {}

    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            if entry is None or not entry.talks:
                continue
            decided_statuses = [t.status for t in entry.talks if t.status in DECIDED_STATUSES]
            if not decided_statuses:
                continue

            if conf.name not in by_name:
                by_name[conf.name] = ConfSubmissionSummary(
                    name=conf.name,
                    conf=conf,
                    country_code=conf.country_code,
                    difficulty=conf.difficulty,
                )

            s = by_name[conf.name]
            talk_names = [t.title or t.talk for t in entry.talks if t.status in DECIDED_STATUSES]

            conf_date = entry.conference_start

            if TalkStatus.accepted in decided_statuses:
                s.accepted += 1
                s.year_details.append(ConfYearDetail(year, TalkStatus.accepted, talk_names, conf_date))
            elif TalkStatus.withdrawn in decided_statuses:
                s.withdrawn += 1
                s.year_details.append(ConfYearDetail(year, TalkStatus.withdrawn, talk_names, conf_date))
            else:
                s.rejected += 1
                s.year_details.append(ConfYearDetail(year, TalkStatus.rejected, talk_names, conf_date))

    result = list(by_name.values())
    result.sort(
        key=lambda s: max(
            (d.conf_date for d in s.year_details if d.conf_date),
            default=date(1970, 1, 1),
        ),
        reverse=True,
    )
    return result


@dataclass
class OwedItem:
    name: str
    year: int
    amount: float
    country_code: str = ""


def reimbursements_owed(conferences: list[Conference]) -> tuple[list[OwedItem], float]:
    """Conferences that still owe me money, most recent year first, plus the running total."""
    owed: list[OwedItem] = []

    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            if entry is None or entry.cost is None or not entry.cost.owed:
                continue
            owed.append(
                OwedItem(
                    name=conf.name,
                    year=year,
                    amount=entry.cost.owed,
                    country_code=conf.country_code,
                )
            )

    owed.sort(key=lambda item: item.year, reverse=True)
    total = round(sum(item.amount for item in owed), 2)
    return owed, total


def conf_acceptance_rate(
    summaries: list[ConfSubmissionSummary],
) -> tuple[int, int, float, int, int, float]:
    """Returns (accepted, total, rate, accepted_no_withdrawn, total_no_withdrawn, rate_no_withdrawn)."""
    accepted = sum(s.accepted for s in summaries)
    total = sum(s.total for s in summaries)
    rate = round(accepted / total * 100) if total else 0.0

    total_no_withdrawn = sum(s.accepted + s.rejected for s in summaries)
    rate_no_withdrawn = round(accepted / total_no_withdrawn * 100) if total_no_withdrawn else 0.0

    return accepted, total, rate, accepted, total_no_withdrawn, rate_no_withdrawn
