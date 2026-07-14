from confetti.models import Conference, Cost, YearEntry
from confetti.views.conf_stats import reimbursements_owed


def _conf(name: str, cost: Cost | None) -> Conference:
    return Conference(
        filename="test.yaml",
        name=name,
        city="Test",
        country="Netherlands",
        website="https://example.com",
        years={2026: YearEntry(cost=cost)},
    )


def test_owed_is_promised_minus_covered():
    cost = Cost(flight=300, promised=600, covered=200)
    owed, total = reimbursements_owed([_conf("ConfA", cost)])
    result = ([(item.name, item.year, item.amount) for item in owed], total)
    assert result == ([("ConfA", 2026, 400)], 400.0)


def test_fully_covered_not_owed():
    result = reimbursements_owed([_conf("ConfA", Cost(promised=600, covered=600))])
    assert result == ([], 0.0)


def test_no_promise_not_owed():
    result = reimbursements_owed([_conf("ConfA", Cost(flight=300, covered=200))])
    assert result == ([], 0.0)


def test_total_sums_multiple_owed():
    confs = [
        _conf("ConfA", Cost(promised=600, covered=0)),
        _conf("ConfB", Cost(promised=500, covered=0)),
    ]
    owed, total = reimbursements_owed(confs)
    result = ([(item.name, item.amount) for item in owed], total)
    assert result == ([("ConfA", 600), ("ConfB", 500)], 1100.0)
