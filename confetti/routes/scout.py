import logging
import threading
from datetime import date

import werkzeug

from flask import Blueprint
from flask import Response
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from confetti.constants import SCOUT_LOG
from confetti.scouting.claude_runner import prev_log_path
from confetti.scouting.claude_runner import stop as stop_scouting
from confetti.scouting.confs import get_confs_to_scout
from confetti.scouting.scout_agent import scout_conferences

logger = logging.getLogger(__name__)

scout_bp = Blueprint("scout", __name__)

_scout_state: dict = {
    "status": "idle",
    "results": [],
    "skipped": [],
    "targets": [],
    "total": 0,
}
_lock = threading.Lock()


@scout_bp.route("/scout")
def index() -> str:
    to_scout, skipped = get_confs_to_scout()
    with _lock:
        _scout_state["preloaded"] = to_scout
        _scout_state["skipped"] = skipped
    return render_template(
        "scout.html",
        title="Scout",
        subtitle="Check conferences for updated dates",
        to_scout=to_scout,
        skipped=skipped,
        current_year=date.today().year,
        today=date.today(),
    )


@scout_bp.route("/scout/start", methods=["POST"])
def start() -> werkzeug.Response:
    with _lock:
        if _scout_state["status"] == "running":
            return redirect(url_for("scout.index"))

        _scout_state["status"] = "running"
        _scout_state["results"] = []
        _scout_state["skipped"] = []
        _scout_state["targets"] = []
        _scout_state["total"] = 0

    thread = threading.Thread(target=_run_all, daemon=True)
    thread.start()

    return redirect(url_for("scout.index"))


@scout_bp.route("/scout/stop", methods=["POST"])
def stop() -> werkzeug.Response:
    stop_scouting()
    with _lock:
        _scout_state["status"] = "stopped"
    return redirect(url_for("scout.index"))


@scout_bp.route("/scout/status")
def status() -> Response:
    with _lock:
        response = {
            "status": _scout_state["status"],
            "total": _scout_state["total"],
            "completed": len(_scout_state["results"]),
            "targets": _scout_state.get("targets", []),
            "results": [r.to_dict() for r in _scout_state["results"]],
            "skipped": [s.to_dict() for s in _scout_state["skipped"]],
        }
        if _scout_state.get("error"):
            response["error"] = _scout_state["error"]
        return jsonify(response)


@scout_bp.route("/scout/log")
def log() -> Response:
    log_file = prev_log_path(SCOUT_LOG) if request.args.get("prev") else SCOUT_LOG
    lines = log_file.read_text().splitlines()[-50:] if log_file.exists() else []
    return jsonify({"lines": lines, "has_prev": prev_log_path(SCOUT_LOG).exists()})


def _run_all() -> None:
    with _lock:
        confs_to_scout = _scout_state.get("preloaded", [])

    if not confs_to_scout:
        confs_to_scout, confs_to_skip = get_confs_to_scout()
        with _lock:
            _scout_state["skipped"] = confs_to_skip

    with _lock:
        _scout_state["targets"] = [c.name for c in confs_to_scout]
        _scout_state["total"] = len(confs_to_scout)

    if not confs_to_scout:
        with _lock:
            _scout_state["status"] = "done"
        return

    try:
        results = scout_conferences(confs_to_scout)
    except Exception as e:
        logger.exception("Scouting failed")
        with _lock:
            _scout_state["results"] = []
            _scout_state["status"] = "error"
            _scout_state["error"] = str(e)
        return

    with _lock:
        _scout_state["results"] = results
        _scout_state["status"] = "done"
