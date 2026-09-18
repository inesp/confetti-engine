import pytest

from confetti.models import Conference


def _conf(attendees: int | None) -> Conference:
    return Conference(
        filename="test.yaml",
        name="Conf",
        city="Test",
        country="Netherlands",
        website="https://example.com",
        attendees=attendees,
    )


@pytest.mark.parametrize(
    ("attendees", "expected"),
    [(None, None), (150, 1), (399, 1), (400, 2), (999, 2), (1000, 3), (2499, 3), (2500, 4), (8000, 4)],
)
def test_size_step_buckets_attendees(attendees, expected):
    result = _conf(attendees).size_step
    assert result == expected

