import pytest
from flask import render_template_string

from confetti.app import create_app
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


def test_size_icon_draws_one_person_per_step():
    with create_app().app_context():
        result = render_template_string(
            '{% from "components/difficulty.html" import size_icon %}{{ size_icon(conf) }}', conf=_conf(1200)
        )
    assert result.count("<circle") == 3


def test_size_icon_shows_attendees_on_hover():
    with create_app().app_context():
        result = render_template_string(
            '{% from "components/difficulty.html" import size_icon %}{{ size_icon(conf) }}', conf=_conf(1200)
        )
    assert ">1,200 attendees</span>" in result


def test_size_icon_renders_nothing_when_size_unknown():
    with create_app().app_context():
        result = render_template_string(
            '{% from "components/difficulty.html" import size_icon %}{{ size_icon(conf) }}', conf=_conf(None)
        )
    assert result.strip() == ""


def test_conf_popup_shows_question_mark_when_size_unknown():
    app = create_app()
    with app.test_request_context():
        html = render_template_string(
            '{% from "components/conf_tooltip.html" import conf_tooltip %}{{ conf_tooltip(conf) }}', conf=_conf(None)
        )
    result = " ".join(html.split())
    assert '<div class="text-gray-400">👥 Size</div> <div class="text-gray-400">?</div>' in result
