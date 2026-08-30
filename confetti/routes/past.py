from datetime import date

from flask import Blueprint
from flask import render_template

from confetti.views.conf_stats import SubmissionTally
from confetti.views.conf_stats import build_conf_summaries
from confetti.views.conf_stats import build_submissions
from confetti.views.conf_stats import submissions_by_year
from confetti.views.talk_stats import build_talk_stats
from confetti.views.timeline import build_dot_timeline
from confetti.views.timeline import build_past_conferences
from confetti.views.timeline import build_year_summaries
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.yaml.yaml_parser import load_talks

past_bp = Blueprint("past", __name__)


@past_bp.route("/past")
def index() -> str:
    conferences, _ = load_and_validate_conferences()
    talks = load_talks()

    past_conferences = build_past_conferences(conferences)
    talk_stats = build_talk_stats(conferences, talks)
    submissions = build_submissions(conferences)
    conf_summaries = build_conf_summaries(submissions)
    submission_years = submissions_by_year(submissions)
    submissions_total = SubmissionTally(submissions)

    years: dict[int, list] = {}
    for pc in past_conferences:
        years.setdefault(pc.year, []).append(pc)

    year_summaries = build_year_summaries(years)
    year_dots = {year: build_dot_timeline(confs) for year, confs in years.items()}

    return render_template(
        "past.html",
        title="Past",
        subtitle="Conferences I've been at",
        years=years,
        year_summaries=year_summaries,
        year_dots=year_dots,
        talk_stats=talk_stats,
        conf_summaries=conf_summaries,
        submission_years=submission_years,
        submissions_total=submissions_total,
        today=date.today(),
    )
