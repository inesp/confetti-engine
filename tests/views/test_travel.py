from datetime import date

from confetti.models import (
    Booker,
    Booking,
    BookingStatus,
    Conference,
    TalkEntry,
    TalkStatus,
    Travel,
    YearEntry,
)
from confetti.views.travel import TravelNag, travel_nags

TODAY = date(2026, 10, 4)


def _conf(
    travel: Travel | None,
    conference_start: date = date(2026, 11, 12),
    talk_status: TalkStatus = TalkStatus.accepted,
) -> Conference:
    return Conference(
        filename="test.yaml",
        name="Fauxcon",
        city="Faux City",
        country="Netherlands",
        website="https://example.com",
        years={
            2026: YearEntry(
                conference_start=conference_start,
                talks=[TalkEntry(talk="estimation", status=talk_status)],
                travel=travel,
            )
        },
    )


def _done() -> Booking:
    return Booking(status=BookingStatus.done)


def test_missing_travel_nags_to_book_both():
    result = travel_nags([_conf(None)], TODAY)
    assert result == [
        TravelNag("Fauxcon", 2026, "flight", "Book the flight", date(2026, 11, 12)),
        TravelNag("Fauxcon", 2026, "hotel", "Book the hotel", date(2026, 11, 12)),
    ]


def test_todo_far_away_stays_quiet():
    result = travel_nags([_conf(None, conference_start=date(2027, 3, 1))], TODAY)
    assert result == []


def test_not_accepted_stays_quiet():
    result = travel_nags([_conf(None, talk_status=TalkStatus.submitted)], TODAY)
    assert result == []


def test_past_conference_stays_quiet():
    result = travel_nags([_conf(None, conference_start=date(2026, 10, 1))], TODAY)
    assert result == []


def test_done_stays_quiet():
    result = travel_nags([_conf(Travel(flight=_done(), hotel=_done()))], TODAY)
    assert result == []


def test_organizer_todo_is_my_move():
    flight = Booking(by=Booker.organizer, status=BookingStatus.todo, note="send travel details")
    result = travel_nags([_conf(Travel(flight=flight, hotel=_done()))], TODAY)
    assert result == [
        TravelNag(
            "Fauxcon",
            2026,
            "flight",
            "Your move on the flight, the organizers book it",
            date(2026, 11, 12),
            "send travel details",
        )
    ]


def test_waiting_before_ping_date_stays_quiet():
    flight = Booking(by=Booker.organizer, status=BookingStatus.waiting, ping_on=date(2026, 10, 8))
    result = travel_nags([_conf(Travel(flight=flight, hotel=_done()))], TODAY)
    assert result == []


def test_waiting_on_ping_date_nags_to_ping():
    flight = Booking(by=Booker.organizer, status=BookingStatus.waiting, ping_on=TODAY)
    result = travel_nags([_conf(Travel(flight=flight, hotel=_done()))], TODAY)
    assert result == [
        TravelNag("Fauxcon", 2026, "flight", "Ping the organizers about the flight", date(2026, 11, 12)),
    ]


def test_ping_date_nags_even_when_conference_is_far():
    flight = Booking(by=Booker.organizer, status=BookingStatus.waiting, ping_on=TODAY)
    conf = _conf(Travel(flight=flight, hotel=_done()), conference_start=date(2027, 3, 1))
    result = travel_nags([conf], TODAY)
    assert result == [
        TravelNag("Fauxcon", 2026, "flight", "Ping the organizers about the flight", date(2027, 3, 1)),
    ]


def test_waiting_without_ping_date_nags():
    flight = Booking(by=Booker.organizer, status=BookingStatus.waiting)
    result = travel_nags([_conf(Travel(flight=flight, hotel=_done()))], TODAY)
    assert result == [
        TravelNag("Fauxcon", 2026, "flight", "Waiting on the flight with no ping date", date(2026, 11, 12)),
    ]
