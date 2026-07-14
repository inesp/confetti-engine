import logging
import threading

import werkzeug

from flask import Blueprint
from flask import Response
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from confetti.models import Conference
from confetti.constants import DISCOVER_LOG
from confetti.scouting.claude_runner import prev_log_path
from confetti.scouting.claude_runner import stop as stop_discovering
from confetti.scouting.discover_agent import DiscoverResult
from confetti.scouting.discover_agent import discover_conferences
from confetti.yaml.skipped import add_skipped
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.yaml.yaml_updater import add_conference

logger = logging.getLogger(__name__)

discover_bp = Blueprint("discover", __name__)

_discover_state: dict = {
    "status": "idle",
    "results": [],
}
_lock = threading.Lock()


@discover_bp.route("/discover")
def index() -> str:
    return render_template(
        "discover.html",
        title="Discover",
        subtitle="Find new conferences to speak at",
    )


@discover_bp.route("/discover/start", methods=["POST"])
def start() -> werkzeug.Response:
    with _lock:
        if _discover_state["status"] == "running":
            return redirect(url_for("discover.index"))

        _discover_state["status"] = "running"
        _discover_state["results"] = []

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return redirect(url_for("discover.index"))


@discover_bp.route("/discover/stop", methods=["POST"])
def stop() -> werkzeug.Response:
    stop_discovering()
    with _lock:
        _discover_state["status"] = "stopped"
    return redirect(url_for("discover.index"))


@discover_bp.route("/discover/status")
def status() -> Response:
    with _lock:
        return jsonify(
            {
                "status": _discover_state["status"],
                "results": [r.to_dict() for r in _discover_state["results"]],
            }
        )


@discover_bp.route("/discover/log")
def log() -> Response:
    log_file = prev_log_path(DISCOVER_LOG) if request.args.get("prev") else DISCOVER_LOG
    lines = log_file.read_text().splitlines()[-50:] if log_file.exists() else []
    return jsonify({"lines": lines, "has_prev": prev_log_path(DISCOVER_LOG).exists()})


@discover_bp.route("/discover/save", methods=["POST"])
def save() -> Response | tuple[Response, int]:
    """Save a discovered conference to a YAML file."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    filename = data.get("filename", "discovered.yaml")
    if not filename.endswith(".yaml"):
        filename += ".yaml"

    conf = Conference(
        filename=filename,
        name=data["name"],
        city=data.get("city", ""),
        country=data.get("country", ""),
        website=data.get("website", ""),
        budget=data.get("budget") if data.get("budget") in ("full", "partial", "none") else None,
        difficulty=(
            data.get("difficulty_for_me")
            if data.get("difficulty_for_me") in ("easy", "moderate", "hard", "longshot")
            else None
        ),
        topic_fit=data.get("topic_fit"),
        notes=data.get("notes"),
    )

    add_conference(conf)
    return jsonify({"ok": True, "filename": filename})


@discover_bp.route("/discover/skip", methods=["POST"])
def skip() -> Response | tuple[Response, int]:
    """Skip a conference so it won't be suggested again."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "No name"}), 400

    add_skipped(data["name"])
    return jsonify({"ok": True})


def _run() -> None:
    try:
        conferences, _ = load_and_validate_conferences()
        results = discover_conferences(conferences)
    except Exception as e:
        logger.exception("Discover failed")
        results = [DiscoverResult(name="Error", city="", country="", website="", why=str(e)[:500])]

    with _lock:
        _discover_state["results"] = results
        _discover_state["status"] = "done"
