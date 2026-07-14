from dataclasses import dataclass
from datetime import date
from enum import IntEnum, StrEnum, auto

from confetti.models import Conference
from confetti.models import TalkStatus
from confetti.models import YearEntry


class Urgency(IntEnum):
    past = 0
    waiting_for_them = 1  # I submitted / accepted / waiting for CFP to open
    waiting_for_me = 2  # CFP is open, I need to act


class KanbanColumn(StrEnum):
    waiting = auto()
    cfp_open = auto()
    submitted = auto()
    accepted = auto()
    past = auto()


@dataclass
class ConferenceTimeline:
    conf: Conference
    action: str
    action_date: date | None
    urgency: Urgency
    kanban_column: KanbanColumn
    conf_start: date | None = None
    conf_end: date | None = None
    talk_year: int | None = None
    skipped: bool = False


def build_timeline(conferences: list[Conference]) -> list[ConferenceTimeline]:
    today = date.today()

    timeline: list[ConferenceTimeline] = []
    for conf in conferences:
        item = _classify(conf, today)
        timeline.append(item)

    timeline.sort(
        key=lambda x: (
            -x.urgency,
            x.action_date.isoformat() if x.action_date else "9999-99-99",
        )
    )
    return timeline


def _classify(conf: Conference, today: date) -> ConferenceTimeline:
    if conf.skip:
        return ConferenceTimeline(
            conf=conf,
            action="Skipped",
            action_date=None,
            urgency=Urgency.past,
            kanban_column=KanbanColumn.past,
            skipped=True,
        )

    ne = conf.next_event

    # This year's edition skipped: keep it visible (grayed on the timeline) but out of action lists.
    edition_entry = conf.years.get(ne.edition_year) if ne.edition_year else None
    if edition_entry and edition_entry.skip:
        return ConferenceTimeline(
            conf=conf,
            action="Skipped this year",
            action_date=None,
            urgency=Urgency.past,
            kanban_column=KanbanColumn.past,
            conf_start=ne.conference_start,
            conf_end=ne.conference_end,
            skipped=True,
        )

    # Find relevant year entry for talk status
    year_entry, talk_year = _get_relevant_year_entry(conf, today)
    status = year_entry.status if year_entry else None

    # For talk-status branches, use dates from the year entry that has the talks,
    # not from next_event (which points to the next upcoming edition).
    if status and year_entry:
        ye_cs = year_entry.conference_start
        ye_ce = year_entry.conference_end

        # Accepted — future conference
        if status == TalkStatus.accepted:
            if ye_cs and ye_cs > today:
                days = (ye_cs - today).days
                return ConferenceTimeline(
                    conf=conf,
                    action=f"Conference in {days} days",
                    action_date=ye_cs,
                    urgency=Urgency.waiting_for_them,
                    kanban_column=KanbanColumn.accepted,
                    conf_start=ye_cs,
                    conf_end=ye_ce,
                    talk_year=talk_year,
                )
            return ConferenceTimeline(
                conf=conf,
                action="Accepted (conference passed)",
                action_date=ye_cs,
                urgency=Urgency.past,
                kanban_column=KanbanColumn.past,
                conf_start=ye_cs,
                conf_end=ye_ce,
                talk_year=talk_year,
            )

        # Submitted / waitlisted — waiting for their decision
        if status in (TalkStatus.submitted, TalkStatus.waitlisted):
            cfp_close = year_entry.cfp_close
            action = "Waitlisted" if status == TalkStatus.waitlisted else "Submitted, waiting to hear back"
            if ye_cs and ye_cs > today:
                days = (ye_cs - today).days
                action += f" (conference in {days} days)"
            elif cfp_close:
                action += f" (CFP closed {cfp_close.strftime('%d. %b')})"
            return ConferenceTimeline(
                conf=conf,
                action=action,
                action_date=ye_cs,
                urgency=Urgency.waiting_for_them,
                kanban_column=KanbanColumn.submitted,
                conf_start=ye_cs,
                conf_end=ye_ce,
                talk_year=talk_year,
            )

        # Rejected/withdrawn — move to past
        if status in (TalkStatus.rejected, TalkStatus.withdrawn):
            return ConferenceTimeline(
                conf=conf,
                action=f"{status.capitalize()}" + (f" (conf {ye_cs.strftime('%d. %b')})" if ye_cs else ""),
                action_date=ye_cs,
                urgency=Urgency.past,
                kanban_column=KanbanColumn.past,
                conf_start=ye_cs,
                conf_end=ye_ce,
                talk_year=talk_year,
            )

    cs = ne.conference_start
    ce = ne.conference_end
    cfp_open = ne.cfp_open
    cfp_close = ne.cfp_close
    conf_start = ne.conference_start

    # Conference already happened (only check factual dates)
    if conf_start and ne.conference_start_is_factual and conf_start < today:
        return ConferenceTimeline(
            conf=conf,
            action="Conference passed",
            action_date=conf_start,
            urgency=Urgency.past,
            kanban_column=KanbanColumn.past,
            conf_start=cs,
            conf_end=ce,
        )

    # CFP is open now — they're waiting for me to submit
    if cfp_open and cfp_close and cfp_open <= today <= cfp_close:
        days = (cfp_close - today).days
        action = f"CFP closes in {days} days!" if days > 0 else "CFP closes today!"
        if conf_start:
            action = f"{action} Conf start: {conf_start.strftime('%d. %b')}"
        return ConferenceTimeline(
            conf=conf,
            action=action,
            action_date=cfp_close,
            urgency=Urgency.waiting_for_me,
            kanban_column=KanbanColumn.cfp_open,
            conf_start=cs,
            conf_end=ce,
        )

    # CFP already closed, not submitted
    if cfp_close and cfp_close < today:
        return ConferenceTimeline(
            conf=conf,
            action=f"CFP closed ({cfp_close.strftime('%d. %b')})",
            action_date=conf_start or cfp_close,
            urgency=Urgency.past,
            kanban_column=KanbanColumn.past,
            conf_start=cs,
            conf_end=ce,
        )

    # CFP not yet open
    if cfp_open and cfp_open > today:
        days = (cfp_open - today).days
        presumably = "presumably " if not ne.cfp_open_is_factual else ""
        prefix = "~" if not ne.cfp_open_is_factual else ""
        return ConferenceTimeline(
            conf=conf,
            action=f"CFP {presumably}opens in {prefix}{days} days{'!' if days <= 7 else ''}",
            action_date=cfp_open,
            urgency=Urgency.waiting_for_them,
            kanban_column=KanbanColumn.waiting,
            conf_start=cs,
            conf_end=ce,
        )

    # Only conference date known
    if conf_start and conf_start > today:
        presumably = "presumably " if not ne.conference_start_is_factual else ""
        prefix = "~" if not ne.conference_start_is_factual else ""
        days = (conf_start - today).days
        return ConferenceTimeline(
            conf=conf,
            action=f"Conference {presumably}in {prefix}{days} days",
            action_date=conf_start,
            urgency=Urgency.waiting_for_them,
            kanban_column=KanbanColumn.waiting,
            conf_start=cs,
            conf_end=ce,
        )

    # No dates at all
    return ConferenceTimeline(
        conf=conf,
        action="No dates known",
        action_date=None,
        urgency=Urgency.past,
        kanban_column=KanbanColumn.waiting,
    )


def _get_relevant_year_entry(conf: Conference, today: date) -> tuple["YearEntry | None", int | None]:
    """Find the year entry most relevant to today (this year, or next year if this year's conf passed)."""
    current_year = today.year
    this_year = conf.years.get(current_year)
    next_year = conf.years.get(current_year + 1)

    if this_year:
        if this_year.conference_start and this_year.conference_start < today:
            return next_year, current_year + 1 if next_year else None
        return this_year, current_year
    return next_year, current_year + 1 if next_year else None


def best_year(conf: Conference) -> int:
    """The next relevant edition year.

    Prefers next_event so the detail page (and its per-edition skip button) always
    agree with the timeline about which edition is next. Otherwise a conference
    whose next edition is only known from presumed dates (e.g. an empty current-year
    entry) shows one year on the timeline and a different year on the skip button.
    Falls back to a simple this-year-or-next guess when there are no dates to place
    the next edition at all.
    """
    edition = conf.next_event.edition_year
    if edition is not None:
        return edition

    today = date.today()
    current_year = today.year
    this_year = conf.years.get(current_year)
    if this_year and (not this_year.conference_start or this_year.conference_start >= today):
        return current_year
    return current_year + 1


def build_detail_nav(conferences: list[Conference], current_name: str) -> tuple[list[str], str | None, str | None]:
    """Return (all_confs_dropdown, prev_name, next_name)."""
    today = date.today()

    # Prev/next: non-rejected, future conferences with talks for their best year
    def _is_nav_candidate(conf: Conference) -> bool:
        year = best_year(conf)
        year_entry = conf.years.get(year)
        if year_entry is None or not year_entry.talks:
            return False
        if year_entry.status in (TalkStatus.rejected, TalkStatus.withdrawn):
            return False
        if year_entry.conference_start and year_entry.conference_start < today:
            return False
        return True

    def _conf_date(conf: Conference) -> date:
        year_entry = conf.years.get(best_year(conf))
        if year_entry and year_entry.conference_start:
            return year_entry.conference_start
        return date.max

    nav_confs = sorted([c for c in conferences if _is_nav_candidate(c)], key=_conf_date)
    nav_names = [c.name for c in nav_confs]
    prev_name = None
    next_name = None
    if current_name in nav_names:
        idx = nav_names.index(current_name)
        if idx > 0:
            prev_name = nav_names[idx - 1]
        if idx < len(nav_names) - 1:
            next_name = nav_names[idx + 1]

    # Dropdown: ALL conference names, alphabetical
    all_names = sorted(c.name for c in conferences)

    return all_names, prev_name, next_name
