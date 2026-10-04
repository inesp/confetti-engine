from dataclasses import dataclass
from datetime import date

from confetti.constants import TRAVEL_NAG_WINDOW
from confetti.models import Booker
from confetti.models import Booking
from confetti.models import BookingStatus
from confetti.models import Conference
from confetti.models import TalkStatus


@dataclass
class TravelNag:
    name: str
    year: int
    item: str  # "flight" or "hotel"
    message: str
    conference_start: date
    note: str = ""


def _nag_message(item: str, booking: Booking, today: date, in_window: bool) -> str | None:
    """What I have to do about this booking today, or None when it's not my move."""
    if booking.status == BookingStatus.done:
        return None
    if booking.status == BookingStatus.todo:
        if not in_window:
            return None
        if booking.by == Booker.organizer:
            return f"Your move on the {item}, the organizers book it"
        return f"Book the {item}"
    if booking.ping_on is None:
        return f"Waiting on the {item} with no ping date"
    if booking.ping_on > today:
        return None
    if booking.by == Booker.organizer:
        return f"Ping the organizers about the {item}"
    return f"Follow up on the {item}"


def travel_nags(conferences: list[Conference], today: date) -> list[TravelNag]:
    """Flights and hotels for accepted, upcoming conferences where the next move is mine, soonest first.

    A "todo" only nags once the conference is TRAVEL_NAG_WINDOW away. A "waiting" nags on its ping_on
    date, however far the conference is, or right away when no ping date was set.
    """
    nags: list[TravelNag] = []

    for conf in conferences:
        if conf.skip:
            continue
        for year, entry in (conf.years or {}).items():
            if entry is None or entry.skip or entry.status != TalkStatus.accepted:
                continue
            if entry.conference_start is None or entry.conference_start < today:
                continue
            in_window = entry.conference_start - today <= TRAVEL_NAG_WINDOW
            for item, booking in entry.bookings.items():
                message = _nag_message(item, booking, today, in_window)
                if message is None:
                    continue
                nags.append(
                    TravelNag(
                        name=conf.name,
                        year=year,
                        item=item,
                        message=message,
                        conference_start=entry.conference_start,
                        note=booking.note,
                    )
                )

    nags.sort(key=lambda nag: nag.conference_start)
    return nags
