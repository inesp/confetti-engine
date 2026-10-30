from datetime import date

from confetti.models import (
    Booker,
    Booking,
    BookingStatus,
    Conference,
    Cost,
    Talk,
    TalkEntry,
    TalkStatus,
    Travel,
    YearEntry,
)
from confetti.views.fun_facts import FunFact, build_fun_facts


def _conf(
    name: str, city: str, country: str, years: dict[int, YearEntry], attendees: int | None = None
) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city=city,
        country=country,
        website="https://example.com",
        years=years,
        attendees=attendees,
    )


def _year(
    *talks: tuple[str, TalkStatus],
    start: date | None = None,
    invited: bool = False,
    travel: Travel | None = None,
    cost: Cost | None = None,
    durations: dict[str, int] | None = None,
) -> YearEntry:
    return YearEntry(
        conference_start=start,
        invited=invited,
        travel=travel,
        cost=cost,
        talks=[
            TalkEntry(
                talk=talk_id, status=status, title=f"Title {talk_id}", talk_duration=(durations or {}).get(talk_id, 0)
            )
            for talk_id, status in talks
        ],
    )


TALKS = [Talk(id="pancakes", title="Pancakes"), Talk(id="kites", title="Kites"), Talk(id="dragons", title="Dragons")]
TODAY = date(2025, 9, 20)


def test_build_fun_facts_from_full_history():
    conferences = [
        _conf(
            "Waffle Conf",
            "Ghent",
            "Belgium",
            {
                2024: _year(
                    ("pancakes", TalkStatus.accepted),
                    ("dragons", TalkStatus.sidelined),
                    start=date(2024, 3, 10),
                    durations={"pancakes": 40},
                ),
                2025: _year(
                    ("kites", TalkStatus.accepted),
                    start=date(2025, 9, 9),
                    invited=True,
                    travel=Travel(hotel=Booking(by=Booker.organizer, status=BookingStatus.done, cost=200)),
                    cost=Cost(extra=100),
                ),
            },
        ),
        _conf(
            "Fjord Days",
            "Bergen",
            "Norway",
            {
                2024: _year(("kites", TalkStatus.rejected)),
                2025: _year(
                    ("pancakes", TalkStatus.accepted),
                    ("kites", TalkStatus.accepted),
                    start=date(2025, 9, 25),
                    invited=True,
                    cost=Cost(extra=50, promised=50, covered=50),
                    durations={"kites": 30},
                ),
            },
            attendees=1200,
        ),
        _conf(
            "Nope Summit",
            "Oslo",
            "Norway",
            {
                2025: _year(("kites", TalkStatus.rejected), ("dragons", TalkStatus.rejected)),
                2026: _year(("pancakes", TalkStatus.submitted)),
            },
            attendees=9000,
        ),
    ]

    result = build_fun_facts(conferences, TALKS, TODAY)

    assert result == [
        FunFact("🌍", "2 countries", "4 stages in 2 cities", "rose"),
        FunFact("📮", "6 conferences", "submitted to, and 3 said yes", "amber"),
        FunFact("⏳", "1 abstract", "still out there, waiting for 1 conference to answer", "sky"),
        FunFact("📚", "2 different talks", "made it onto a stage", "violet"),
        FunFact("🧳", "Pancakes", "your most-travelled talk: 2 stages and counting", "emerald"),
        FunFact("🐣", "Dragons", "0 for 2, still believing", "orange"),
        FunFact("💌", "Invited twice", "Waffle Conf and Fjord Days asked you to submit", "rose"),
        FunFact("🔁", "Waffle Conf", "the only conference that had you back", "amber"),
        FunFact("🌱", "Fjord Days", "said no in 2024, yes in 2025", "sky"),
        FunFact("✌️", "Fjord Days", "took two of your talks in 2025", "violet"),
        FunFact("📅", "2025", "your busiest year: 3 stages", "emerald"),
        FunFact("🌀", "September 2025", "Waffle Conf and Fjord Days, all in one month", "orange"),
        FunFact("🍂", "September", "your favourite month: 3 stages, all years together", "rose"),
        FunFact("👥", "1,200 people", "your biggest crowd, Fjord Days", "amber"),
        FunFact("⏱️", "40 minutes", "of you, talking, on a stage", "sky"),
        FunFact("🎤", "Ghent", "your first stage, Waffle Conf, March 2024", "violet"),
        FunFact("✈️", "Bergen", "your next stage, Fjord Days, in 5 days", "emerald"),
        FunFact("🎟️", "1 trip", "where the organizers did the booking", "orange"),
        FunFact("💸", "100€ out of pocket", "and 1 trip cost you nothing", "rose"),
    ]


def test_build_fun_facts_drops_facts_without_data():
    conferences = [
        _conf("Waffle Conf", "Ghent", "Belgium", {2025: _year(("pancakes", TalkStatus.accepted))}),
        _conf("Fjord Days", "Bergen", "Norway", {2025: _year(("pancakes", TalkStatus.accepted))}),
    ]

    result = build_fun_facts(conferences, TALKS, TODAY)

    assert result == [
        FunFact("🌍", "2 countries", "2 stages in 2 cities", "rose"),
        FunFact("📮", "2 conferences", "submitted to, and 2 said yes", "amber"),
        FunFact("🧳", "Pancakes", "your most-travelled talk: 2 stages and counting", "sky"),
    ]


def test_build_fun_facts_with_no_stages_is_empty():
    conferences = [_conf("Nope Summit", "Oslo", "Norway", {2025: _year(("kites", TalkStatus.rejected))})]

    result = build_fun_facts(conferences, TALKS, TODAY)

    assert result == []
