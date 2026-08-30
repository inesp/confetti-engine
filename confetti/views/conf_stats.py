from dataclasses import dataclass, field
from datetime import date

from confetti.constants import CFP_BEFORE_CONFERENCE
from confetti.constants import CFP_ESTIMATED_DURATION
from confetti.models import Conference, TalkStatus, YearEntry

# Pill washes for the conference list: light enough to read gray text over, saturated enough that a
# mixed record still reads as red-to-green at a glance.
PILL_REJECTED = "#fee2e2"
PILL_WITHDRAWN = "#ffedd5"
PILL_ACCEPTED = "#dcfce7"
PILL_NEUTRAL = "#f9fafb"


def edition_outcome(entry: YearEntry) -> TalkStatus | None:
    """How one conference edition landed: accepted beats still-waiting beats withdrawn beats rejected.

    One edition, one outcome, however many talks I threw at it. Sidelined talks count as rejected -
    they did not put me on stage.
    """
    statuses = {talk.status for talk in entry.talks}
    if not statuses:
        return None
    for status in (TalkStatus.accepted, TalkStatus.submitted, TalkStatus.waitlisted, TalkStatus.withdrawn):
        if status in statuses:
            return status
    return TalkStatus.rejected


def outcome_talks(entry: YearEntry, outcome: TalkStatus) -> list[str]:
    """Only the talks that produced the edition's outcome: the accepted one, the withdrawn one, or every rejection.

    Sidelined talks ride along with the rejected ones, the same way edition_outcome counts them.
    """
    wanted = {outcome, TalkStatus.sidelined} if outcome == TalkStatus.rejected else {outcome}
    return [talk.title or talk.talk for talk in entry.talks if talk.status in wanted]


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


@dataclass
class SubmissionBox:
    """One submission to one conference edition: the atom every number on the page is counted from."""

    conf: Conference
    year: int
    status: TalkStatus
    talks: list[str]
    cfp_close: date
    cfp_year: int

    @property
    def name(self) -> str:
        return self.conf.name

    @property
    def country_code(self) -> str:
        return self.conf.country_code

    @property
    def decided(self) -> bool:
        return self.status != TalkStatus.submitted


def build_submissions(conferences: list[Conference]) -> list[SubmissionBox]:
    """Every submission I ever sent, oldest CFP deadline first."""
    submissions: list[SubmissionBox] = []

    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            outcome = edition_outcome(entry) if entry else None
            if entry is None or outcome is None:
                continue

            close_date = submission_close_date(conf, year, entry) or date(year, 12, 31)
            submissions.append(
                SubmissionBox(
                    conf=conf,
                    year=year,
                    status=outcome,
                    talks=outcome_talks(entry, outcome),
                    cfp_close=close_date,
                    cfp_year=close_date.year,
                )
            )

    submissions.sort(key=lambda box: (box.cfp_close, box.conf.name))
    return submissions


@dataclass
class SubmissionTally:
    """A pile of submissions - one year of them, or all of them - counted into a rate.

    A waitlist counts as a no: it did not put me on stage. Submissions still waiting for an answer
    count as nothing at all, so a pending CFP cannot drag a rate down.
    """

    boxes: list[SubmissionBox] = field(default_factory=list)

    def _count(self, *statuses: TalkStatus) -> int:
        return sum(1 for box in self.boxes if box.status in statuses)

    @property
    def accepted(self) -> int:
        return self._count(TalkStatus.accepted)

    @property
    def rejected(self) -> int:
        return self._count(TalkStatus.rejected, TalkStatus.waitlisted)

    @property
    def withdrawn(self) -> int:
        return self._count(TalkStatus.withdrawn)

    @property
    def waiting(self) -> int:
        return self._count(TalkStatus.submitted)

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


@dataclass
class YearSubmissions(SubmissionTally):
    """One year of submissions, the year being the one the CFP closed in - when I did the submitting."""

    year: int = 0


def submissions_by_year(submissions: list[SubmissionBox]) -> list[YearSubmissions]:
    """The same submissions sliced by the year their CFP closed, most recent year first."""
    by_year: dict[int, YearSubmissions] = {}

    for box in submissions:
        by_year.setdefault(box.cfp_year, YearSubmissions(year=box.cfp_year)).boxes.append(box)

    return [by_year[year] for year in sorted(by_year, reverse=True)]


@dataclass
class ConfYearDetail:
    year: int
    status: TalkStatus
    talks: list[str]


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
        for detail in sorted(self.year_details, key=lambda d: d.year):
            parts.append(f"{detail.year} ({detail.status}): {', '.join(detail.talks)}")
        return " | ".join(parts)

    @property
    def pill_gradient(self) -> str:
        """The pill's background: rejected years on the left bleeding through withdrawn into accepted.

        Each colour is pinned to the middle of its share of the pill, so a conference that went one
        rejection and two acceptances reads as a wash from red into green rather than two hard blocks.
        A conference with a single outcome ends up with that colour flat across the whole pill.
        """
        bands = [
            (self.rejected, PILL_REJECTED),
            (self.withdrawn, PILL_WITHDRAWN),
            (self.accepted, PILL_ACCEPTED),
        ]
        present = [(count, colour) for count, colour in bands if count]
        if not present:
            return f"linear-gradient(90deg, {PILL_NEUTRAL} 0%, {PILL_NEUTRAL} 100%)"

        stops = []
        walked = 0.0
        for count, colour in present:
            share = count / self.total * 100
            stops.append(f"{colour} {walked + share / 2:.1f}%")
            walked += share

        first_colour = present[0][1]
        last_colour = present[-1][1]
        return f"linear-gradient(90deg, {first_colour} 0%, {', '.join(stops)}, {last_colour} 100%)"

    @property
    def pill_border(self) -> str:
        """Tailwind border classes: coloured when every year landed the same way, neutral once mixed."""
        if self.rejected == 0 and self.withdrawn == 0:
            return "border border-green-300"
        if self.accepted == 0 and self.withdrawn == 0:
            return "border border-red-300"
        if self.accepted == 0 and self.rejected == 0:
            return "border-2 border-orange-400"
        return "border border-gray-300"


def build_conf_summaries(submissions: list[SubmissionBox]) -> list[ConfSubmissionSummary]:
    """The same submissions sliced by conference, the one I submitted to most recently first."""
    by_name: dict[str, ConfSubmissionSummary] = {}
    last_submitted: dict[str, date] = {}

    for box in submissions:
        if not box.decided:
            continue

        summary = by_name.setdefault(
            box.name,
            ConfSubmissionSummary(
                name=box.name,
                conf=box.conf,
                country_code=box.country_code,
                difficulty=box.conf.difficulty,
            ),
        )

        if box.status == TalkStatus.accepted:
            summary.accepted += 1
        elif box.status == TalkStatus.withdrawn:
            summary.withdrawn += 1
        else:
            summary.rejected += 1
        summary.year_details.append(ConfYearDetail(box.year, box.status, box.talks))
        last_submitted[box.name] = box.cfp_close

    summaries = list(by_name.values())
    summaries.sort(key=lambda summary: last_submitted[summary.name], reverse=True)
    return summaries


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
