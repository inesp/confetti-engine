from datetime import date

from flask import Blueprint
from flask import render_template

from confetti.views.fun_facts import build_fun_facts
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.yaml.yaml_parser import load_talks

fun_facts_bp = Blueprint("fun_facts", __name__)


@fun_facts_bp.route("/fun-facts")
def index() -> str:
    conferences, _ = load_and_validate_conferences()
    facts = build_fun_facts(conferences, load_talks(), date.today())
    return render_template(
        "fun_facts.html", title="Fun facts", subtitle="Things that happened along the way", facts=facts
    )
