from datetime import date
from datetime import datetime

import werkzeug

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from confetti.conference_view import KanbanColumn
from confetti.conference_view import Urgency
from confetti.conference_view import best_year
from confetti.conference_view import build_detail_nav
from confetti.conference_view import build_timeline
from confetti.constants import BEFORE_CFP_OPEN
from confetti.models import TalkStatus
from confetti.views.timeline import build_cfp_gantt
from confetti.views.timeline import build_gantt
from confetti.views.timeline import build_yearly_dot_timeline
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.views.talk_stats import save_talk_stats
from confetti.yaml.yaml_parser import load_talks
from confetti.yaml.yaml_updater import update_cfp_url
from confetti.yaml.yaml_updater import update_cfp_window
from confetti.yaml.yaml_updater import update_difficulty
from confetti.yaml.yaml_updater import update_favorite
from confetti.yaml.yaml_updater import update_cost
from confetti.yaml.yaml_updater import update_skip
from confetti.yaml.yaml_updater import update_year_skip
from confetti.yaml.yaml_updater import add_talk
from confetti.yaml.yaml_updater import update_talk_status
from confetti.yaml.yaml_updater import update_talk_time
from confetti.yaml.yaml_updater import update_talk_title
from confetti.yaml.yaml_updater import update_vacation_days

conferences_bp = Blueprint("conferences", __name__)


@conferences_bp.route("/conferences")
def index() -> str:
    conferences, errors = load_and_validate_conferences()
    timeline = build_timeline(conferences)

    today = date.today()

    kanban = {
        "waiting": [
            t
            for t in timeline
            if t.kanban_column == KanbanColumn.waiting and t.action_date and t.action_date <= today + BEFORE_CFP_OPEN
        ],
        "cfp_open": [t for t in timeline if t.kanban_column == KanbanColumn.cfp_open],
        "submitted": [t for t in timeline if t.kanban_column == KanbanColumn.submitted],
        "accepted": [
            t for t in timeline if t.kanban_column == KanbanColumn.accepted and t.conf_start and t.conf_start > today
        ],
        "past": [t for t in timeline if t.kanban_column == KanbanColumn.past],
        "skipped": [t for t in timeline if t.conf.skip],
    }

    # Action needed: they're waiting for me, or CFP opens very soon
    action_possible = [t for t in timeline if t.urgency == Urgency.waiting_for_me and not t.skipped]
    action_possible.sort(key=lambda t: t.action_date.isoformat() if t.action_date else "9999")

    # Coming up: I'm waiting for them (submitted, CFP not open yet, accepted future)
    # CFP-closed conferences go at the end
    coming_up = [t for t in timeline if t.urgency == Urgency.waiting_for_them and not t.skipped]
    coming_up.sort(key=lambda t: t.action_date.isoformat() if t.action_date else "9999")
    cfp_closed = [t for t in timeline if t.urgency == Urgency.past and not t.skipped]
    cfp_closed.sort(key=lambda t: t.action_date.isoformat() if t.action_date else "9999")
    coming_up.extend(cfp_closed)

    gantt_bars, gantt_months = build_gantt(timeline, today)
    cfp_bars, cfp_months = build_cfp_gantt(timeline, today)
    yearly_dots, yearly_months = build_yearly_dot_timeline(conferences, today.year)

    return render_template(
        "conferences.html",
        title="Conferences",
        subtitle="What's next",
        kanban=kanban,
        action_possible=action_possible,
        coming_up=coming_up,
        current_year=today.year,
        today=today,
        gantt_bars=gantt_bars,
        gantt_months=gantt_months,
        cfp_bars=cfp_bars,
        cfp_months=cfp_months,
        yearly_dots=yearly_dots,
        yearly_months=yearly_months,
        talk_statuses=list(TalkStatus),
    )


@conferences_bp.route("/conferences/update-status", methods=["POST"])
def update_status() -> werkzeug.Response:
    conf_name = request.form["conf_name"]
    talk_id = request.form["talk_id"]
    status = request.form["status"]
    year = int(request.form["year"])

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_talk_status(conf, year, talk_id, status)
        conferences, _ = load_and_validate_conferences()
        save_talk_stats(conferences, load_talks())

    if request.form.get("from_page") == "detail":
        return redirect(url_for("conferences.detail", conf_name=conf_name))
    return redirect(url_for("conferences.index"))


@conferences_bp.route("/conferences/<conf_name>/update-talk-title", methods=["POST"])
def update_talk_title_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])
    talk_id = request.form["talk_id"]
    title = request.form.get("title", "").strip()

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_talk_title(conf, year, talk_id, title)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/add-talk", methods=["POST"])
def add_talk_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])
    talk_id = request.form.get("talk_id", "").strip()
    title = request.form.get("title", "").strip()

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf and talk_id:
        add_talk(conf, year, talk_id, title)
        conferences, _ = load_and_validate_conferences()
        save_talk_stats(conferences, load_talks())

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>")
def detail(conf_name: str) -> str | werkzeug.Response:
    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if not conf:
        return redirect(url_for("conferences.index"))

    from datetime import date

    year = best_year(conf)
    year_entry = conf.years.get(year)
    today = date.today()

    all_confs, prev_conf, next_conf = build_detail_nav(conferences, conf.name)

    return render_template(
        "conference_detail.html",
        title=f"{conf.name} {year}",
        conf=conf,
        year=year,
        today=today,
        year_entry=year_entry,
        talk_statuses=list(TalkStatus),
        all_talks=load_talks(),
        prev_conf=prev_conf,
        next_conf=next_conf,
        all_confs=all_confs,
    )


@conferences_bp.route("/conferences/<conf_name>/update-favorite", methods=["POST"])
def update_favorite_route(conf_name: str) -> werkzeug.Response:
    favorite = request.form.get("favorite") == "true"

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_favorite(conf, favorite)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-difficulty", methods=["POST"])
def update_difficulty_route(conf_name: str) -> werkzeug.Response:
    difficulty = request.form.get("difficulty", "").strip()
    if difficulty not in ("hard", "longshot"):
        difficulty = ""

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_difficulty(conf, difficulty or None)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-cfp-url", methods=["POST"])
def update_cfp_url_route(conf_name: str) -> werkzeug.Response:
    url = request.form.get("cfp_url", "").strip()

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_cfp_url(conf, url)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-cfp-window", methods=["POST"])
def update_cfp_window_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])

    def _parse_date(field: str) -> date | None:
        raw = request.form.get(field, "").strip()
        return date.fromisoformat(raw) if raw else None

    cfp_open = _parse_date("cfp_open")
    cfp_close = _parse_date("cfp_close")

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_cfp_window(conf, year, cfp_open, cfp_close)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-year-skip", methods=["POST"])
def update_year_skip_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])
    skip = request.form.get("skip") == "true"

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_year_skip(conf, year, skip)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-skip", methods=["POST"])
def update_skip_route(conf_name: str) -> werkzeug.Response:
    skip = request.form.get("skip") == "true"

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_skip(conf, skip)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-vacation-days", methods=["POST"])
def update_vacation_days_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])
    days = int(request.form["vacation_days"])

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_vacation_days(conf, year, days)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-cost", methods=["POST"])
def update_cost_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])

    def _parse_float(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        return float(value)

    flight = _parse_float(request.form.get("flight", ""))
    hotel = _parse_float(request.form.get("hotel", ""))
    extra = _parse_float(request.form.get("extra", ""))
    promised = _parse_float(request.form.get("promised", ""))
    covered = _parse_float(request.form.get("covered", ""))

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_cost(conf, year, flight, hotel, extra, promised, covered)

    return redirect(url_for("conferences.detail", conf_name=conf_name))


@conferences_bp.route("/conferences/<conf_name>/update-talk-time", methods=["POST"])
def update_talk_time_route(conf_name: str) -> werkzeug.Response:
    year = int(request.form["year"])
    talk_id = request.form["talk_id"]

    talk_date = request.form.get("talk_date", "").strip()
    talk_time = request.form.get("talk_time", "").strip()
    talk_start: datetime | None = None
    if talk_date and talk_time:
        talk_start = datetime.fromisoformat(f"{talk_date}T{talk_time}")
    talk_duration = int(request.form.get("talk_duration", "0") or "0")
    schedule_notes = request.form.get("schedule_notes", "").strip()

    conferences, _ = load_and_validate_conferences()
    conf = next((c for c in conferences if c.name == conf_name), None)
    if conf:
        update_talk_time(conf, year, talk_id, talk_start, talk_duration, schedule_notes)

    return redirect(url_for("conferences.detail", conf_name=conf_name))
