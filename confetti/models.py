from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import auto
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from confetti.constants import CFP_BEFORE_CONFERENCE
from confetti.constants import CFP_ESTIMATED_DURATION
from confetti.constants import CONFERENCES_DIR
from confetti.date_utils import parse_month_day


class Budget(StrEnum):
    full = "full"
    partial = "partial"
    ask = "ask"
    none = "none"


class Difficulty(StrEnum):
    easy = auto()
    moderate = auto()
    hard = auto()
    longshot = auto()


class Presumed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conference_start: str | None = None  # "02-15", "12-31"
    conference_end: str | None = None

    def build_conference_start(self, year: int) -> date | None:
        if self.conference_start is None:
            return None
        return date(year, *parse_month_day(self.conference_start))

    def build_conference_end(self, year: int) -> date | None:
        if self.conference_end is None:
            return None
        return date(year, *parse_month_day(self.conference_end))


class TalkStatus(StrEnum):
    submitted = auto()
    accepted = auto()
    rejected = auto()
    sidelined = auto()
    waitlisted = auto()
    withdrawn = auto()


class TalkEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    talk: str  # talk ID from talks/talks.yml
    status: TalkStatus = TalkStatus.submitted
    title: str = ""
    talk_start: datetime | None = None
    talk_duration: int = 0
    schedule_notes: str = ""

    @property
    def talk_end(self) -> datetime | None:
        if self.talk_start and self.talk_duration:
            return self.talk_start + timedelta(minutes=self.talk_duration)
        return None


class Talk(BaseModel):
    """A talk definition from talks/talks.yml."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    link: str | None = None


COUNTRY_CODES = {
    "Austria": "AT",
    "Belgium": "BE",
    "Czech Republic": "CZ",
    "France": "FR",
    "Germany": "DE",
    "Hungary": "HU",
    "Italy": "IT",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Netherlands": "NL",
    "Norway": "NO",
    "Poland": "PL",
    "Serbia": "RS",
    "Spain": "ES",
    "Sweden": "SE",
    "Switzerland": "CH",
    "UK": "GB",
}


class Cost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flight: float | None = None
    hotel: float | None = None
    extra: float | None = None
    promised: float | None = None
    covered: float | None = None

    @property
    def total(self) -> float:
        return round((self.flight or 0) + (self.hotel or 0) + (self.extra or 0), 2)

    @property
    def effective_covered(self) -> float:
        return min(self.covered or 0, self.total)

    @property
    def owed(self) -> float:
        """What they promised but haven't covered yet."""
        return round(max((self.promised or 0) - (self.covered or 0), 0), 2)


@dataclass
class HistorySummary:
    applied: list[int]
    accepted: list[int]
    notes: list[str]


@dataclass
class NextEvent:
    """The next upcoming event for a conference: either CFP opening or the conference itself."""

    conference_start: date | None = None
    conference_start_is_factual: bool = False
    conference_end: date | None = None

    cfp_open: date | None = None
    cfp_open_is_factual: bool = False
    cfp_close: date | None = None
    cfp_close_is_factual: bool = False
    cfp_is_a_guess: bool = False

    edition_year: int | None = None
    notify: str | None = None


class YearEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cfp_open: date | None = None
    cfp_close: date | None = None
    notify: str | None = None
    conference_start: date | None = None
    conference_end: date | None = None
    talks: list[TalkEntry] = Field(default_factory=list)
    cost: Cost | None = None
    vacation_days: int = 0
    skip: bool = False

    @property
    def status(self) -> TalkStatus | None:
        if not self.talks:
            return None
        statuses = [t.status for t in self.talks]
        if any(s == TalkStatus.accepted for s in statuses):
            return TalkStatus.accepted
        if any(s is None or s == TalkStatus.submitted for s in statuses):
            return TalkStatus.submitted
        if any(s == TalkStatus.waitlisted for s in statuses):
            return TalkStatus.waitlisted
        if all(s == TalkStatus.withdrawn for s in statuses):
            return TalkStatus.withdrawn
        return TalkStatus.rejected


class Cfp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None
    site: str | None
    formats: str | None
    notes: str | None
    presumed_open: str | None
    presumed_close: str | None

    def build_cfp_open(self, year: int) -> date | None:
        if self.presumed_open is None:
            return None
        return date(year, *parse_month_day(self.presumed_open))

    def build_cfp_close(self, year: int) -> date | None:
        if self.presumed_close is None:
            return None
        return date(year, *parse_month_day(self.presumed_close))


class Conference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str

    name: str
    city: str
    country: str
    address: str | None = None
    website: str
    years: dict[int, YearEntry | None] = Field(default_factory=dict)

    cfp: Cfp | None = None
    presumed: Presumed = Field(default_factory=Presumed)
    budget: Budget | None = None
    difficulty: Difficulty | None = None
    topic_fit: str | None = None
    lang: str | None = None
    notes: str | None = None
    skip: bool = False
    favorite: bool = False

    @property
    def history(self) -> "HistorySummary | None":
        """Summary of application history by year."""
        applied: list[int] = []
        accepted: list[int] = []
        notes: list[str] = []
        for year, entry in sorted(self.years.items()):
            if entry is None or not entry.talks:
                continue
            applied.append(year)
            if entry.status == TalkStatus.accepted:
                accepted.append(year)
            elif entry.status in (TalkStatus.withdrawn, TalkStatus.waitlisted):
                notes.append(f"{entry.status} {year}")
        if not applied:
            return None
        return HistorySummary(applied=applied, accepted=accepted, notes=notes)

    @property
    def filepath(self) -> Path:
        return CONFERENCES_DIR / self.filename

    @property
    def country_code(self) -> str:
        return COUNTRY_CODES.get(self.country, self.country[:2].upper())

    @property
    def next_event(self) -> NextEvent:
        today = date.today()
        event = NextEvent()
        edition_year = self._resolve_next_edition(today, event)
        event.edition_year = edition_year
        self._resolve_next_cfp(today, event, edition_year)
        return event

    def _resolve_next_edition(self, today: date, event: NextEvent) -> int | None:
        this_year = self.years.get(today.year)
        next_year = self.years.get(today.year + 1)

        if this_year and this_year.conference_start and this_year.conference_start >= today:
            event.conference_start = this_year.conference_start
            event.conference_end = this_year.conference_end
            event.conference_start_is_factual = True
            return today.year

        if next_year and next_year.conference_start and next_year.conference_start >= today:
            event.conference_start = next_year.conference_start
            event.conference_end = next_year.conference_end
            event.conference_start_is_factual = True
            return today.year + 1

        presumed = self.presumed.build_conference_start(today.year)
        if presumed and presumed > today:
            event.conference_start = presumed
            event.conference_end = self.presumed.build_conference_end(today.year)
            return today.year

        presumed_next = self.presumed.build_conference_start(today.year + 1)
        if presumed_next:
            event.conference_start = presumed_next
            event.conference_end = self.presumed.build_conference_end(today.year + 1)
            return today.year + 1

        return None

    def _resolve_next_cfp(self, today: date, event: NextEvent, edition_year: int | None) -> None:
        if edition_year is None:
            return

        # 1. Factual cfp_open from year entry
        entry = self.years.get(edition_year)
        if entry:
            event.notify = entry.notify
            if entry.cfp_open:
                event.cfp_open = entry.cfp_open
                event.cfp_close = entry.cfp_close
                event.cfp_open_is_factual = True
                event.cfp_close_is_factual = entry.cfp_close is not None
                return
            # 2. Guess from factual cfp_close
            if entry.cfp_close:
                event.cfp_open = entry.cfp_close - CFP_ESTIMATED_DURATION
                event.cfp_close = entry.cfp_close
                event.cfp_close_is_factual = True
                event.cfp_is_a_guess = True
                return

        # 3. Presumed CFP patterns
        if self.cfp:
            presumed_open = self.cfp.build_cfp_open(edition_year)
            presumed_close = self.cfp.build_cfp_close(edition_year)
            # CFP must open before the conference; if it falls after, it belongs to the prior year
            if presumed_open and event.conference_start and presumed_open >= event.conference_start:
                # Check if close crosses year boundary by comparing month/day patterns
                # e.g. open="10-01" close="01-31" means Oct->Jan (crosses year)
                # e.g. open="10-01" close="12-15" means Oct->Dec (same year)
                close_crosses_year = presumed_close is not None and presumed_close.month < presumed_open.month
                presumed_open = self.cfp.build_cfp_open(edition_year - 1)
                if presumed_close and not close_crosses_year:
                    presumed_close = self.cfp.build_cfp_close(edition_year - 1)
            if presumed_open:
                event.cfp_open = presumed_open
                event.cfp_close = presumed_close
                return
            # 4. Guess from presumed cfp_close only
            if presumed_close and event.conference_start and presumed_close >= event.conference_start:
                presumed_close = self.cfp.build_cfp_close(edition_year - 1)
            if presumed_close:
                event.cfp_open = presumed_close - CFP_ESTIMATED_DURATION
                event.cfp_close = presumed_close
                event.cfp_is_a_guess = True
                return

        # 5. Derive from conference start: cfp_open = conf_start - 180 days
        if event.conference_start:
            event.cfp_open = event.conference_start - CFP_BEFORE_CONFERENCE
            event.cfp_is_a_guess = True
