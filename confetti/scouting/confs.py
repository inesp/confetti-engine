from dataclasses import dataclass
from datetime import date
from enum import IntEnum

from confetti.constants import BEFORE_CFP_OPEN
from confetti.constants import BEFORE_CONFERENCE_SCOUT
from confetti.date_utils import format_date
from confetti.models import Conference
from confetti.yaml.yaml_parser import load_and_validate_conferences


class SkipReason(IntEnum):
    skipped = 0
    too_early = 2
    all_dates_known = 3
    not_enough_data = 4


@dataclass
class ScoutResult:
    conf: Conference
    outcome: str
    reason: SkipReason | None = None
    next_action_at: date | None = None
    found_dates: dict | None = None
    raw_response: str | None = None

    @property
    def sort_key(self) -> str:
        return self.next_action_at.isoformat() if self.next_action_at else "9999-99-99"

    def to_dict(self) -> dict:
        return {
            "conf": self.conf.model_dump(),
            "outcome": self.outcome,
            "reason": self.reason.name if self.reason else None,
            "next_action_at": self.next_action_at.isoformat() if self.next_action_at else None,
            "found_dates": self.found_dates,
            "raw_response": self.raw_response,
        }


def get_confs_to_scout() -> tuple[list[Conference], list[ScoutResult]]:
    """Load conferences and filter to those worth scouting now."""
    conferences, errors = load_and_validate_conferences()
    if not conferences:
        return [], []

    return _filter_conferences(conferences)


def _filter_conferences(
    conferences: list[Conference],
) -> tuple[list[Conference], list[ScoutResult]]:
    """Filter conferences to only those worth scouting right now.
    We will try to get the dates of CFP and the dates of the conference.
    """
    today = date.today()

    to_scout: list[Conference] = []
    skipped: list[ScoutResult] = []

    for conf in conferences:
        if conf.skip:
            skipped.append(
                ScoutResult(
                    conf=conf,
                    outcome="Skipped",
                    reason=SkipReason.skipped,
                )
            )
            continue

        next_event = conf.next_event

        if next_event.conference_start_is_factual and next_event.cfp_open_is_factual:
            assert next_event.conference_start is not None
            assert next_event.cfp_open is not None
            skipped.append(
                ScoutResult(
                    conf=conf,
                    outcome=f"All dates known. Conference starts at {format_date(next_event.conference_start)}. "
                    f"CFP opens at {format_date(next_event.cfp_open)}",
                    reason=SkipReason.all_dates_known,
                    next_action_at=next_event.cfp_open or next_event.conference_start,
                )
            )
            continue

        if next_event.cfp_close_is_factual:
            assert next_event.cfp_close is not None
            skipped.append(
                ScoutResult(
                    conf=conf,
                    outcome=f"CFP close date already known: {format_date(next_event.cfp_close)}",
                    reason=SkipReason.all_dates_known,
                    next_action_at=next_event.cfp_close,
                )
            )
            continue

        # CFP already closed (presumed) — nothing to scout until next edition
        if next_event.cfp_close and not next_event.cfp_open_is_factual and next_event.cfp_close < today:
            skipped.append(
                ScoutResult(
                    conf=conf,
                    outcome=f"CFP presumably closed {format_date(next_event.cfp_close)}",
                    reason=SkipReason.too_early,
                    next_action_at=next_event.conference_start,
                )
            )
            continue

        # We don't have the actual CFP open date, but we do know it should open at some point in the next X days
        if next_event.cfp_open and not next_event.cfp_open_is_factual:
            if next_event.cfp_open < today + BEFORE_CFP_OPEN:
                to_scout.append(conf)
            else:
                presumably = " " if next_event.conference_start_is_factual else " presumably"
                skipped.append(
                    ScoutResult(
                        conf=conf,
                        outcome=f"Too early. CFP presumably opens {format_date(next_event.cfp_open)}. "
                        f"Conf{presumably} starts at {format_date(next_event.conference_start) if next_event.conference_start else "?"},",
                        reason=SkipReason.too_early,
                        next_action_at=next_event.cfp_open,
                    )
                )
            continue

        # No CFP date at all, but we know when the conference is — scout if it's approaching
        if next_event.conference_start:
            scout_threshold = next_event.conference_start - BEFORE_CONFERENCE_SCOUT
            if today >= scout_threshold:
                to_scout.append(conf)
            else:
                skipped.append(
                    ScoutResult(
                        conf=conf,
                        outcome=f"Too early. Conference presumably at {format_date(next_event.conference_start)}, will scout closer to that date",
                        reason=SkipReason.too_early,
                        next_action_at=scout_threshold,
                    )
                )
            continue

        skipped.append(
            ScoutResult(
                conf=conf,
                outcome="We don't have enough data. Figure out last year's conference dates "
                "and store them to `years` or to `presumed`.",
                reason=SkipReason.not_enough_data,
            )
        )

    skipped.sort(key=lambda s: s.sort_key)
    return to_scout, skipped
