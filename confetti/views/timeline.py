from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum, auto

from confetti.conference_view import ConferenceTimeline
from confetti.constants import CFP_ESTIMATED_DURATION
from confetti.conference_view import KanbanColumn
from confetti.models import Conference, TalkEntry, TalkStatus, TripCost

_MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class TimelineDot:
    conf: Conference
    position_pct: float
    row: int = 0


@dataclass
class MonthMarker:
    label: str
    position_pct: float


def _build_year_axis(year: int) -> tuple[date, date, int, list[MonthMarker]]:
    """Build the Jan-Dec axis for a given year."""
    range_start = date(year, 1, 1)
    range_end = date(year + 1, 1, 1)
    total_days = (range_end - range_start).days

    months: list[MonthMarker] = []
    month_date = range_start
    while month_date < range_end:
        left = (month_date - range_start).days / total_days * 100
        months.append(MonthMarker(label=_MONTH_NAMES[month_date.month], position_pct=left))
        if month_date.month == 12:
            month_date = date(month_date.year + 1, 1, 1)
        else:
            month_date = date(month_date.year, month_date.month + 1, 1)

    return range_start, range_end, total_days, months


def build_dot_timeline(confs: list["PastConference"]) -> tuple[list[TimelineDot], list[MonthMarker]]:
    """Build a dot-on-axis timeline for a list of past conferences."""
    dated = [(pc.conf, pc.conference_start) for pc in confs if pc.conference_start]
    if not dated:
        return [], []

    dated.sort(key=lambda d: d[1])
    year = dated[0][1].year
    range_start, range_end, total_days, months = _build_year_axis(year)

    dots = []
    for conf, conf_date in dated:
        position = (conf_date - range_start).days / total_days * 100
        dots.append(TimelineDot(conf=conf, position_pct=position))

    return dots, months


def build_yearly_dot_timeline(
    conferences: list[Conference], year: int
) -> tuple[list[TimelineDot], list[MonthMarker]]:
    """Build a dot timeline showing when all conferences happen in a given year.

    Uses factual dates from the year entry, falling back to presumed dates.
    """
    range_start, range_end, total_days, months = _build_year_axis(year)

    dated: list[tuple[Conference, date]] = []
    for conf in conferences:
        year_entry = conf.years.get(year)
        if year_entry and year_entry.conference_start:
            dated.append((conf, year_entry.conference_start))
        elif conf.presumed:
            presumed_start = conf.presumed.build_conference_start(year)
            if presumed_start:
                dated.append((conf, presumed_start))

    if not dated:
        return [], months

    dated.sort(key=lambda d: d[1])
    dots: list[TimelineDot] = []
    for conf, conf_date in dated:
        position = (conf_date - range_start).days / total_days * 100
        row = 0
        for existing in dots:
            if abs(existing.position_pct - position) < 1.5 and existing.row == row:
                row += 1
        dots.append(TimelineDot(conf=conf, position_pct=position, row=row))

    return dots, months


@dataclass
class PastConference:
    conf: Conference
    year: int
    conference_start: date | None
    conference_end: date | None
    talks: list[TalkEntry]
    cost: TripCost | None = None

    vacation_days: int = 0

    @property
    def conf_days(self) -> int:
        if self.conference_start and self.conference_end:
            return (self.conference_end - self.conference_start).days + 1
        return 0


def build_past_conferences(conferences: list[Conference]) -> list[PastConference]:
    """Conferences actually attended (status == accepted), most recent first."""
    past = []
    for conf in conferences:
        for year, entry in (conf.years or {}).items():
            if entry is None or entry.status != TalkStatus.accepted:
                continue
            past.append(
                PastConference(
                    conf=conf,
                    year=year,
                    conference_start=entry.conference_start,
                    conference_end=entry.conference_end,
                    talks=entry.talks,
                    cost=entry.money,
                    vacation_days=entry.vacation_days,
                )
            )
    past.sort(
        key=lambda p: (
            -p.year,
            p.conference_start.isoformat() if p.conference_start else "9999",
        )
    )
    return past


@dataclass
class YearSummary:
    conf_count: int = 0
    conf_days: int = 0
    vacation_days: int = 0
    flight: float = 0
    hotel: float = 0
    extra: float = 0
    covered: float = 0
    promised: float = 0
    organizer_booked: float = 0
    out_of_pocket_per_conf: list[float] = field(default_factory=list)
    costed_conf_days: int = 0

    @property
    def total(self) -> float:
        return round(self.flight + self.hotel + self.extra, 2)

    @property
    def out_of_pocket(self) -> float:
        """My money right now, given only what has actually been covered."""
        return round(self.total - self.covered, 2)

    @property
    def out_of_pocket_after_promised(self) -> float:
        """My money once every promised euro has been paid."""
        return round(self.total - self.promised, 2)

    @property
    def cost_per_conf(self) -> float:
        if not self.out_of_pocket_per_conf:
            return 0
        return round(sum(self.out_of_pocket_per_conf) / len(self.out_of_pocket_per_conf), 0)

    @property
    def cost_per_conf_day(self) -> float:
        return round(self.out_of_pocket / self.costed_conf_days, 0) if self.costed_conf_days else 0

    @property
    def vacation_per_conf(self) -> float:
        return round(self.vacation_days / self.conf_count, 1) if self.conf_count else 0

    @property
    def vacation_per_conf_day(self) -> float:
        return round(self.vacation_days / self.conf_days, 1) if self.conf_days else 0


def build_year_summaries(years: dict[int, list[PastConference]]) -> dict[int, YearSummary]:
    result = {}
    for year, confs in years.items():
        summary = YearSummary(conf_count=len(confs))
        for pc in confs:
            summary.conf_days += pc.conf_days
            summary.vacation_days += pc.vacation_days
            if not pc.cost:
                continue
            summary.costed_conf_days += pc.conf_days
            conf_total = pc.cost.total
            conf_oop = pc.cost.out_of_pocket
            summary.out_of_pocket_per_conf.append(conf_oop)
            summary.flight += pc.cost.flight or 0
            summary.hotel += pc.cost.hotel or 0
            summary.extra += pc.cost.extra or 0
            summary.covered += pc.cost.effective_covered
            summary.organizer_booked += pc.cost.organizer_booked + pc.cost.organizer_booking
            summary.promised += min(pc.cost.promised or 0, conf_total)
        summary.flight = round(summary.flight, 2)
        summary.hotel = round(summary.hotel, 2)
        summary.extra = round(summary.extra, 2)
        summary.covered = round(summary.covered, 2)
        summary.promised = round(summary.promised, 2)
        summary.organizer_booked = round(summary.organizer_booked, 2)
        result[year] = summary
    return result


@dataclass
class TimelineBar:
    conf: Conference
    conf_start: date
    conf_end: date
    left_pct: float
    width_pct: float
    status: str
    dates_presumed: bool = False


class CfpBarStatus(StrEnum):
    skipped = auto()  # the conference is skipped (light gray)
    accepted = auto()  # a talk was accepted for that edition (green)
    submitted = auto()  # a talk is submitted/waitlisted, waiting to hear (light green)
    known = auto()  # the CFP close date is factual (purple)
    guess = auto()  # the CFP close date is a guess (orange)


@dataclass
class CfpBar:
    conf: Conference
    cfp_open: date
    cfp_close: date
    left_pct: float
    width_pct: float
    status: CfpBarStatus
    # "open" when the CFP is open today by real dates, "open?" when by guessed dates, None otherwise.
    # Only for CFPs still to submit to: not for skipped, submitted or accepted ones.
    open_badge: str | None = None


def build_cfp_gantt(
    timeline: list[ConferenceTimeline], today: date, months_ahead: int = 9
) -> tuple[list[CfpBar], list[MonthMarker], float]:
    """Build horizontal bars for CFP windows still open today or opening in the next `months_ahead` months.

    The chart starts on the 1st of this month so today's line sits inside it and an open CFP
    visibly crosses it. Returns the bars, the month markers and today's position in percent.

    Colour per row:
      accepted  -> a talk was accepted for that edition (green)
      submitted -> a talk is submitted/waitlisted, waiting to hear (light green)
      known     -> the CFP close date is factual (purple)
      guess     -> the CFP close date is a guess (orange)
    """
    range_start = date(today.year, today.month, 1)
    range_end = date(
        today.year + (today.month - 1 + months_ahead) // 12, (today.month - 1 + months_ahead) % 12 + 1, 1
    )
    total_days = (range_end - range_start).days or 1

    bars_raw: list[CfpBar] = []
    for item in timeline:
        conf = item.conf
        next_event = conf.next_event
        cfp_open = next_event.cfp_open
        cfp_close = next_event.cfp_close
        # Never drop a row for a missing end: make one up from the other, the house way (a CFP runs 60 days).
        if cfp_open and cfp_close is None:
            cfp_close = cfp_open + CFP_ESTIMATED_DURATION
        if cfp_close and cfp_open is None:
            cfp_open = cfp_close - CFP_ESTIMATED_DURATION
        if cfp_open is None or cfp_close is None:
            continue
        # Keep only CFP windows that overlap [today, range_end].
        if cfp_close < today or cfp_open > range_end:
            continue

        if item.skipped:
            status = CfpBarStatus.skipped
        elif item.kanban_column == KanbanColumn.accepted:
            status = CfpBarStatus.accepted
        elif item.kanban_column == KanbanColumn.submitted:
            status = CfpBarStatus.submitted
        elif next_event.cfp_close_is_factual:
            status = CfpBarStatus.known
        else:
            status = CfpBarStatus.guess

        open_badge = None
        if status in (CfpBarStatus.known, CfpBarStatus.guess) and cfp_open <= today <= cfp_close:
            open_badge = "open" if next_event.cfp_open_is_factual and next_event.cfp_close_is_factual else "open?"

        visible_start = max(cfp_open, range_start)
        visible_end = min(cfp_close, range_end)
        left = (visible_start - range_start).days / total_days * 100
        width = max((visible_end - visible_start).days + 1, 1) / total_days * 100
        width = max(width, 2.0)
        bars_raw.append(
            CfpBar(
                conf=conf,
                cfp_open=cfp_open,
                cfp_close=cfp_close,
                left_pct=left,
                width_pct=width,
                status=status,
                open_badge=open_badge,
            )
        )

    # Skipped conferences (whole or just this edition) sink to the bottom.
    bars_raw.sort(key=lambda bar: (bar.status == CfpBarStatus.skipped, bar.cfp_close))

    today_pct = (today - range_start).days / total_days * 100
    return bars_raw, _month_markers(range_start, range_end, total_days), today_pct


def _month_markers(range_start: date, range_end: date, total_days: int) -> list[MonthMarker]:
    months: list[MonthMarker] = []
    month_cursor = range_start
    while month_cursor <= range_end:
        left = (month_cursor - range_start).days / total_days * 100
        months.append(MonthMarker(label=_MONTH_NAMES[month_cursor.month], position_pct=left))
        if month_cursor.month == 12:
            month_cursor = date(month_cursor.year + 1, 1, 1)
        else:
            month_cursor = date(month_cursor.year, month_cursor.month + 1, 1)
    return months


def build_gantt(
    timeline: list[ConferenceTimeline], today: date, months_ahead: int = 13
) -> tuple[list[TimelineBar], list[MonthMarker], float]:
    """Build Gantt bars for this month and the 12 after it: submitted, accepted or planned conferences.

    Thirteen months, so this month's conference of next year is in view while I plan for it.

    Planned means the edition is marked `planned` and has no talks written down yet, so it shows
    where I mean to apply once the CFP opens, on its presumed dates if the real ones aren't known.
    Returns the bars, the month markers and today's position in percent.
    """
    range_start = date(today.year, today.month, 1)
    range_end = date(
        today.year + (today.month - 1 + months_ahead) // 12, (today.month - 1 + months_ahead) % 12 + 1, 1
    )
    total_days = (range_end - range_start).days or 1

    active_columns = {KanbanColumn.submitted, KanbanColumn.accepted}
    bars_raw: list[tuple[Conference, date, date, str, bool]] = []
    for item in timeline:
        if item.conf.skip or item.skipped:
            continue
        if item.kanban_column in active_columns and item.conf_start:
            year_entry = item.conf.years.get(item.talk_year or item.conf_start.year)
            status = str(year_entry.status) if year_entry and year_entry.status else "submitted"
            bars_raw.append((item.conf, item.conf_start, item.conf_end or item.conf_start, status, False))
            continue
        next_event = item.conf.next_event
        edition_entry = item.conf.years.get(next_event.edition_year) if next_event.edition_year else None
        if edition_entry and edition_entry.planned and not edition_entry.talks and next_event.conference_start:
            conf_start = next_event.conference_start
            conf_end = next_event.conference_end or conf_start
            bars_raw.append((item.conf, conf_start, conf_end, "planned", not next_event.conference_start_is_factual))

    bars: list[TimelineBar] = []
    for conf, conf_start, conf_end, status, dates_presumed in sorted(bars_raw, key=lambda bar: bar[1]):
        # Keep only conferences that overlap the window.
        if conf_end < range_start or conf_start >= range_end:
            continue
        visible_start = max(conf_start, range_start)
        visible_end = min(conf_end, range_end)
        left = (visible_start - range_start).days / total_days * 100
        width = max((visible_end - visible_start).days + 1, 1) / total_days * 100
        width = max(width, 2.0)
        bars.append(
            TimelineBar(
                conf=conf,
                conf_start=conf_start,
                conf_end=conf_end,
                left_pct=left,
                width_pct=width,
                status=status,
                dates_presumed=dates_presumed,
            )
        )

    today_pct = (today - range_start).days / total_days * 100
    return bars, _month_markers(range_start, range_end, total_days), today_pct
