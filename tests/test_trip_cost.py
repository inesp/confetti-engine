from datetime import date

from confetti.models import (
    Booker,
    Booking,
    BookingStatus,
    Conference,
    Cost,
    RefusedPayment,
    Travel,
    TripCost,
    YearEntry,
)


def test_summaries_for_hover_box():
    bookings = [
        Booking(),
        Booking(by=Booker.organizer),
        Booking(status=BookingStatus.waiting),
        Booking(by=Booker.organizer, status=BookingStatus.waiting, ping_on=date(2026, 10, 8)),
        Booking(status=BookingStatus.done),
        Booking(by=Booker.organizer, status=BookingStatus.done),
    ]
    result = [booking.summary for booking in bookings]
    assert result == [
        "to book",
        "organizers book, your move",
        "waiting",
        "organizers book, waiting, ping 08. Oct",
        "booked",
        "booked by organizers",
    ]


def test_money_adds_booking_prices_to_extra():
    entry = YearEntry(
        travel=Travel(flight=Booking(cost=210.4), hotel=Booking(cost=330.75)),
        cost=Cost(extra=20, promised=200, covered=200),
    )
    result = entry.money
    assert result == TripCost(flight=210.4, hotel=330.75, extra=20, cash_promised=200, cash_covered=200)


def test_money_is_none_without_any_numbers():
    result = YearEntry(travel=Travel(flight=Booking(by=Booker.organizer))).money
    assert result is None


def _fauxcon() -> YearEntry:
    return YearEntry(
        travel=Travel(
            flight=Booking(status=BookingStatus.done, cost=300),
            hotel=Booking(by=Booker.organizer, status=BookingStatus.done, cost=700),
        ),
        cost=Cost(promised=250, covered=0),
    )


def test_organizer_booking_counts_as_promised_and_covered():
    money = _fauxcon().money
    assert money is not None
    result = (money.total, money.promised, money.covered, money.owed, money.out_of_pocket)
    assert result == (1000, 950, 700, 250, 300)


def test_pending_organizer_booking_is_not_my_money():
    entry = YearEntry(travel=Travel(hotel=Booking(by=Booker.organizer, status=BookingStatus.waiting, cost=120)))
    money = entry.money
    assert money is not None
    result = (money.promised, money.covered, money.owed, money.out_of_pocket, money.organizer_booking)
    assert result == (120, 120, 0, 0, 120)


def _i_book_they_pay_back(paid: float | None) -> YearEntry:
    return YearEntry(
        travel=Travel(flight=Booking(status=BookingStatus.done, cost=310)),
        cost=Cost(promised=310, covered=paid),
    )


def test_payback_not_landed_is_my_money_and_owed():
    money = _i_book_they_pay_back(paid=None).money
    assert money is not None
    result = (money.total, money.out_of_pocket, money.owed, money.out_of_pocket_after_promised)
    assert result == (310, 310, 310, 0)


def test_payback_landed_clears_out_of_pocket():
    money = _i_book_they_pay_back(paid=310).money
    assert money is not None
    result = (money.total, money.out_of_pocket, money.owed)
    assert result == (310, 0, 0)


def test_refused_cash_is_not_owed_and_not_promised():
    entry = YearEntry(
        travel=Travel(flight=Booking(status=BookingStatus.done, cost=300)),
        cost=Cost(promised=300, covered=0, refused=True, note="never replied"),
    )
    money = entry.money
    assert money is not None
    result = (money.promised, money.owed, money.out_of_pocket_after_promised)
    assert result == (0, 0, 300)


def test_conference_remembers_refused_payments():
    conf = Conference(
        filename="test.yaml", name="Conf", city="Test", country="Netherlands", website="https://example.com"
    )
    conf.years[2025] = YearEntry(cost=Cost(promised=600, covered=100, refused=True, note="never replied"))
    result = conf.refused_payments
    assert result == [RefusedPayment(year=2025, amount=500, note="never replied")]
