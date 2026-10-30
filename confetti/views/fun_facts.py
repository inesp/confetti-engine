from collections import Counter
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from confetti.models import Booker
from confetti.models import Conference
from confetti.models import Talk
from confetti.models import TalkStatus
from confetti.models import YearEntry

TILE_COLORS = ("rose", "amber", "sky", "violet", "emerald", "orange")


@dataclass(frozen=True)
class FunFact:
    emoji: str
    big: str
    aside: str
    color: str = ""


@dataclass(frozen=True)
class Stage:
    """One accepted talk at one conference edition."""

    conference: Conference
    year: int
    talk_id: str
    conference_start: date | None


@dataclass(frozen=True)
class FactInput:
    conferences: list[Conference]
    talks: list[Talk]
    today: date


def _year_entries(conferences: list[Conference]) -> Iterator[tuple[Conference, int, YearEntry]]:
    for conference in conferences:
        for year, year_entry in conference.years.items():
            if year_entry is not None:
                yield conference, year, year_entry


def _stages(conferences: list[Conference]) -> list[Stage]:
    return [
        Stage(conference, year, talk.talk, year_entry.conference_start)
        for conference, year, year_entry in _year_entries(conferences)
        for talk in year_entry.talks
        if talk.status == TalkStatus.accepted
    ]


def _has_accepted_talk(year_entry: YearEntry) -> bool:
    return any(talk.status == TalkStatus.accepted for talk in year_entry.talks)


def _join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _countries_fact(facts_input: FactInput) -> FunFact | None:
    stages = _stages(facts_input.conferences)
    if not stages:
        return None
    countries = {stage.conference.country for stage in stages}
    cities = {(stage.conference.city, stage.conference.country) for stage in stages}
    country_word = "country" if len(countries) == 1 else "countries"
    city_word = "city" if len(cities) == 1 else "cities"
    return FunFact(
        "🌍", f"{len(countries)} {country_word}", f"{_plural(len(stages), 'stage')} in {len(cities)} {city_word}"
    )


def _submissions_fact(facts_input: FactInput) -> FunFact | None:
    """Counts conference editions, not abstracts: three talks sent to one CFP are one submission."""
    submitted_to = [year_entry for _, _, year_entry in _year_entries(facts_input.conferences) if year_entry.talks]
    said_yes = [year_entry for year_entry in submitted_to if _has_accepted_talk(year_entry)]
    if not said_yes:
        return None
    return FunFact("📮", _plural(len(submitted_to), "conference"), f"submitted to, and {len(said_yes)} said yes")


def _different_talks_fact(facts_input: FactInput) -> FunFact | None:
    talk_ids = {stage.talk_id for stage in _stages(facts_input.conferences)}
    if len(talk_ids) < 2:
        return None
    return FunFact("📚", f"{len(talk_ids)} different talks", "made it onto a stage")


def _most_travelled_talk_fact(facts_input: FactInput) -> FunFact | None:
    stage_counts = Counter(stage.talk_id for stage in _stages(facts_input.conferences))
    if not stage_counts:
        return None
    talk_id, count = stage_counts.most_common(1)[0]
    if count < 2:
        return None
    titles = {talk.id: talk.title for talk in facts_input.talks}
    return FunFact("🧳", titles.get(talk_id, talk_id), f"your most-travelled talk: {count} stages and counting")


def _invited_fact(facts_input: FactInput) -> FunFact | None:
    inviters = [
        conference.name for conference, _, year_entry in _year_entries(facts_input.conferences) if year_entry.invited
    ]
    if not inviters:
        return None
    times = "once" if len(inviters) == 1 else "twice" if len(inviters) == 2 else f"{len(inviters)} times"
    return FunFact("💌", f"Invited {times}", f"{_join_names(inviters)} asked you to submit")


def _had_you_back_fact(facts_input: FactInput) -> FunFact | None:
    years_on_stage: dict[str, set[int]] = {}
    for stage in _stages(facts_input.conferences):
        years_on_stage.setdefault(stage.conference.name, set()).add(stage.year)
    returning = [name for name, years in years_on_stage.items() if len(years) > 1]
    if not returning:
        return None
    if len(returning) == 1:
        return FunFact("🔁", returning[0], "the only conference that had you back")
    return FunFact("🔁", f"{len(returning)} conferences", f"{_join_names(returning)} had you back")


def _busiest_year_fact(facts_input: FactInput) -> FunFact | None:
    stages_per_year = Counter(stage.year for stage in _stages(facts_input.conferences))
    if len(stages_per_year) < 2:
        return None
    year, count = stages_per_year.most_common(1)[0]
    return FunFact("📅", str(year), f"your busiest year: {count} stages")


def _busiest_month_fact(facts_input: FactInput) -> FunFact | None:
    names_per_month: dict[tuple[int, int], list[str]] = {}
    for stage in _stages(facts_input.conferences):
        if stage.conference_start:
            year_month = (stage.conference_start.year, stage.conference_start.month)
            names = names_per_month.setdefault(year_month, [])
            if stage.conference.name not in names:
                names.append(stage.conference.name)
    if not names_per_month:
        return None
    (year, month), names = max(names_per_month.items(), key=lambda item: len(item[1]))
    if len(names) < 2:
        return None
    return FunFact("🌀", date(year, month, 1).strftime("%B %Y"), f"{_join_names(names)}, all in one month")


def _biggest_audience_fact(facts_input: FactInput) -> FunFact | None:
    sized = [stage.conference for stage in _stages(facts_input.conferences) if stage.conference.attendees]
    if not sized:
        return None
    biggest = max(sized, key=lambda conference: conference.attendees or 0)
    return FunFact("👥", f"{biggest.attendees:,} people", f"your biggest crowd, {biggest.name}")


def _first_stage_fact(facts_input: FactInput) -> FunFact | None:
    dated_stages = [stage for stage in _stages(facts_input.conferences) if stage.conference_start]
    if not dated_stages:
        return None
    first = min(dated_stages, key=lambda stage: stage.conference_start or date.max)
    when = first.conference_start.strftime("%B %Y") if first.conference_start else ""
    return FunFact("🎤", first.conference.city, f"your first stage, {first.conference.name}, {when}")


def _next_stage_fact(facts_input: FactInput) -> FunFact | None:
    upcoming = [
        stage
        for stage in _stages(facts_input.conferences)
        if stage.conference_start and stage.conference_start >= facts_input.today
    ]
    if not upcoming:
        return None
    upcoming_stage = min(upcoming, key=lambda stage: stage.conference_start or date.max)
    days = (upcoming_stage.conference_start - facts_input.today).days if upcoming_stage.conference_start else 0
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    return FunFact("✈️", upcoming_stage.conference.city, f"your next stage, {upcoming_stage.conference.name}, {when}")


def _organizers_booked_fact(facts_input: FactInput) -> FunFact | None:
    trips = [
        conference.name
        for conference, _, year_entry in _year_entries(facts_input.conferences)
        if year_entry.travel
        and any(
            booking and booking.by == Booker.organizer
            for booking in (year_entry.travel.flight, year_entry.travel.hotel)
        )
    ]
    if not trips:
        return None
    return FunFact("🎟️", _plural(len(trips), "trip"), "where the organizers did the booking")


def _still_waiting_fact(facts_input: FactInput) -> FunFact | None:
    waiting = [
        (conference.name, year)
        for conference, year, year_entry in _year_entries(facts_input.conferences)
        for talk in year_entry.talks
        if talk.status == TalkStatus.submitted
    ]
    if not waiting:
        return None
    return FunFact(
        "⏳",
        _plural(len(waiting), "abstract"),
        f"still out there, waiting for {_plural(len(set(waiting)), 'conference')} to answer",
    )


def _underdog_fact(facts_input: FactInput) -> FunFact | None:
    accepted: Counter[str] = Counter()
    turned_down: Counter[str] = Counter()
    for _, _, year_entry in _year_entries(facts_input.conferences):
        for talk in year_entry.talks:
            if talk.status == TalkStatus.accepted:
                accepted[talk.talk] += 1
            elif talk.status in (TalkStatus.rejected, TalkStatus.sidelined):
                turned_down[talk.talk] += 1
    underdogs = [(talk_id, count) for talk_id, count in turned_down.most_common() if not accepted[talk_id]]
    if not underdogs or underdogs[0][1] < 2:
        return None
    talk_id, count = underdogs[0]
    titles = {talk.id: talk.title for talk in facts_input.talks}
    return FunFact("🐣", titles.get(talk_id, talk_id), f"0 for {count}, still believing")


def _comeback_fact(facts_input: FactInput) -> FunFact | None:
    comebacks: list[tuple[int, int, str]] = []
    for conference in facts_input.conferences:
        no_year: int | None = None
        for year in sorted(conference.years):
            year_entry = conference.years[year]
            if year_entry is None or not year_entry.talks:
                continue
            if not _has_accepted_talk(year_entry):
                no_year = year
            elif no_year is not None:
                comebacks.append((year, no_year, conference.name))
                break
    if not comebacks:
        return None
    yes_year, no_year, name = max(comebacks)
    return FunFact("🌱", name, f"said no in {no_year}, yes in {yes_year}")


def _two_at_once_fact(facts_input: FactInput) -> FunFact | None:
    doubles = [
        (conference.name, year)
        for conference, year, year_entry in _year_entries(facts_input.conferences)
        if sum(talk.status == TalkStatus.accepted for talk in year_entry.talks) > 1
    ]
    if not doubles:
        return None
    name, year = doubles[0]
    return FunFact("✌️", name, f"took two of your talks in {year}")


def _favourite_month_fact(facts_input: FactInput) -> FunFact | None:
    stages_per_month = Counter(
        stage.conference_start.month for stage in _stages(facts_input.conferences) if stage.conference_start
    )
    if not stages_per_month:
        return None
    month, count = stages_per_month.most_common(1)[0]
    if count < 2:
        return None
    return FunFact(
        "🍂", date(2000, month, 1).strftime("%B"), f"your favourite month: {count} stages, all years together"
    )


def _minutes_on_stage_fact(facts_input: FactInput) -> FunFact | None:
    minutes = sum(
        talk.talk_duration
        for _, _, year_entry in _year_entries(facts_input.conferences)
        if year_entry.conference_start and year_entry.conference_start <= facts_input.today
        for talk in year_entry.talks
        if talk.status == TalkStatus.accepted
    )
    if not minutes:
        return None
    return FunFact("⏱️", f"{minutes:,} minutes", "of you, talking, on a stage")


def _out_of_pocket_fact(facts_input: FactInput) -> FunFact | None:
    trips = [
        money
        for _, _, year_entry in _year_entries(facts_input.conferences)
        if _has_accepted_talk(year_entry) and (money := year_entry.money) and money.total
    ]
    if not trips:
        return None
    paid = sum(trip.out_of_pocket for trip in trips)
    free_trips = len([trip for trip in trips if not trip.out_of_pocket])
    if free_trips:
        aside = f"and {_plural(free_trips, 'trip')} cost you nothing"
    else:
        aside = f"across {_plural(len(trips), 'trip')}"
    return FunFact("💸", f"{round(paid):,}€ out of pocket", aside)


FACT_BUILDERS: list[Callable[[FactInput], FunFact | None]] = [
    _countries_fact,
    _submissions_fact,
    _still_waiting_fact,
    _different_talks_fact,
    _most_travelled_talk_fact,
    _underdog_fact,
    _invited_fact,
    _had_you_back_fact,
    _comeback_fact,
    _two_at_once_fact,
    _busiest_year_fact,
    _busiest_month_fact,
    _favourite_month_fact,
    _biggest_audience_fact,
    _minutes_on_stage_fact,
    _first_stage_fact,
    _next_stage_fact,
    _organizers_booked_fact,
    _out_of_pocket_fact,
]


def build_fun_facts(conferences: list[Conference], talks: list[Talk], today: date) -> list[FunFact]:
    """Facts that have something to say; a fact without data quietly drops out."""
    facts_input = FactInput(conferences, talks, today)
    facts = [fact for builder in FACT_BUILDERS if (fact := builder(facts_input))]
    return [
        FunFact(fact.emoji, fact.big, fact.aside, TILE_COLORS[index % len(TILE_COLORS)])
        for index, fact in enumerate(facts)
    ]
