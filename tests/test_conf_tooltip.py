from confetti.app import create_app


def _render_clipped(text: str) -> str:
    app = create_app()
    template = app.jinja_env.from_string(
        '{% from "components/conf_tooltip.html" import clipped_text %}'
        '{{ clipped_text(text, "/conferences/Example#notes", limit=20) | trim }}'
    )
    return template.render(text=text)


def test_clipped_text_short_text_is_unchanged():
    result = _render_clipped("Short note.")
    assert result == "Short note."


def test_clipped_text_long_text_is_cut_at_a_word_and_links_to_details():
    result = _render_clipped("Travel and hotel covered, speaker dinner on Tuesday.")
    assert result == (
        'Travel and hotel… <a href="/conferences/Example#notes" '
        'class="text-blue-500 hover:underline whitespace-nowrap">more &rarr;</a>'
    )
