from dataclasses import dataclass, field
from datetime import date

from confetti.constants import CFP_BEFORE_CONFERENCE
from confetti.constants import CFP_ESTIMATED_DURATION
from confetti.models import Conference, TalkStatus, YearEntry

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


@dataclass
class YearConfOutcome:
    """One conference edition, as it landed in a given year."""

    name: str
    country_code: str
    talks: list[str]
    conf_date: date | None = None


@dataclass
class YearAcceptance:
    """Accepted vs. submitted conferences for a single year."""

    year: int
    accepted_confs: list[YearConfOutcome] = field(default_factory=list)
    rejected_confs: list[YearConfOutcome] = field(default_factory=list)
    withdrawn_confs: list[YearConfOutcome] = field(default_factory=list)

    @property
    def accepted(self) -> int:
        return len(self.accepted_confs)

    @property
    def rejected(self) -> int:
        return len(self.rejected_confs)

    @property
    def withdrawn(self) -> int:
        return len(self.withdrawn_confs)

    @property
    def total(self) -> int:
        return self.accepted + self.rejected + self.withdrawn

    @property
    def rate(self) -> int:
        return round(self.accepted / self.total * 100) if self.total else 0

    @property
    def total_no_withdrawn(self) -> int:
        return self.accepted + self.rejected

    @property
    def rate_no_withdrawn(self) -> int:
        return round(self.accepted / self.total_no_withdrawn * 100) if self.total_no_withdrawn else 0


def conf_acceptance_by_year(summaries: list[ConfSubmissionSummary]) -> list[YearAcceptance]:
    """Acceptance rate per conference year, most recent year first, with the conferences behind each number."""
    by_year: dict[int, YearAcceptance] = {}

    for summary in summaries:
        for detail in summary.year_details:
            year_acceptance = by_year.setdefault(detail.year, YearAcceptance(year=detail.year))
            outcome = YearConfOutcome(
                name=summary.name,
                country_code=summary.country_code,
                talks=detail.talks,
                conf_date=detail.conf_date,
            )
            if detail.status == TalkStatus.accepted:
                year_acceptance.accepted_confs.append(outcome)
            elif detail.status == TalkStatus.withdrawn:
                year_acceptance.withdrawn_confs.append(outcome)
            else:
                year_acceptance.rejected_confs.append(outcome)

    def by_date(outcome: YearConfOutcome) -> tuple[date, str]:
        return outcome.conf_date or date(9999, 12, 31), outcome.name

    for year_acceptance in by_year.values():
        year_acceptance.accepted_confs.sort(key=by_date)
        year_acceptance.rejected_confs.sort(key=by_date)
        year_acceptance.withdrawn_confs.sort(key=by_date)

    return [by_year[year] for year in sorted(by_year, reverse=True)]


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


def edition_outcome(entry: YearEntry) -> TalkStatus | None:
    """How one conference edition landed: accepted beats still-waiting beats withdrawn beats rejected.

    Same precedence the acceptance rates use, so the strip and the numbers agree. Sidelined talks
    count as rejected - they did not put me on stage.
    """
    statuses = {talk.status for talk in entry.talks}
    if not statuses:
        return None
    for status in (TalkStatus.accepted, TalkStatus.submitted, TalkStatus.waitlisted, TalkStatus.withdrawn):
        if status in statuses:
            return status
    return TalkStatus.rejected


@dataclass
class SubmissionBox:
    """One submission to one conference edition, for the submission strip."""

    conf: Conference
    year: int
    status: TalkStatus
    talks: list[str]
    sort_date: date

    @property
    def name(self) -> str:
        return self.conf.name

    @property
    def country_code(self) -> str:
        return self.conf.country_code


def submission_close_date(conf: Conference, year: int, entry: YearEntry) -> date | None:
    """When the CFP I submitted to closed, falling back the same way Conference._resolve_next_cfp does.

    Factual close first, then the presumed pattern (shifted back a year when it lands on or after the
    conference itself, the Oct->Jan crossover), then the house guess: a CFP opens 180 days before the
    conference and runs 60, so it closes 120 days out.
    """
    if entry.cfp_close:
        return entry.cfp_close

    conference_start = entry.conference_start
    if conference_start is None and conf.presumed:
        conference_start = conf.presumed.build_conference_start(year)

    if conf.cfp:
        presumed_close = conf.cfp.build_cfp_close(year)
        if presumed_close and conference_start and presumed_close >= conference_start:
            presumed_close = conf.cfp.build_cfp_close(year - 1)
        if presumed_close:
            return presumed_close

    if conference_start:
        return conference_start - (CFP_BEFORE_CONFERENCE - CFP_ESTIMATED_DURATION)

    return None


def build_submission_boxes(conferences: list[Conference]) -> dict[int, list[SubmissionBox]]:
    """Every submission, grouped by the year its CFP closed, each year ordered by that closing date."""
    by_year: dict[int, list[SubmissionBox]] = {}

    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            outcome = edition_outcome(entry) if entry else None
            if entry is None or outcome is None:
                continue

            close_date = submission_close_date(conf, year, entry)
            sort_date = close_date or date(year, 12, 31)
            submitted_in = close_date.year if close_date else year

            by_year.setdefault(submitted_in, []).append(
                SubmissionBox(
                    conf=conf,
                    year=year,
                    status=outcome,
                    talks=[talk.title or talk.talk for talk in entry.talks],
                    sort_date=sort_date,
                )
            )

    for boxes in by_year.values():
        boxes.sort(key=lambda box: (box.sort_date, box.conf.name))

    return {year: by_year[year] for year in sorted(by_year, reverse=True)}
