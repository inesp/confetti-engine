from flask import Blueprint, redirect, request, session, url_for
from werkzeug.wrappers import Response

from confetti import google
from confetti.yaml.yaml_parser import load_and_validate_conferences

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.route("/auth")
def start_auth() -> Response | tuple[str, int]:
    if not google.get_auth_status().needs_auth:
        return redirect(url_for("home.index"))

    redirect_uri = url_for("calendar.oauth_callback", _external=True)
    flow = google.start_oauth_flow(redirect_uri)

    authorization_url, state = flow.authorization_url(  # type: ignore[no-untyped-call]
        access_type="offline",
        prompt="consent",
    )

    session["google_oauth_state"] = state
    session["google_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)


@calendar_bp.route("/oauth/callback")
def oauth_callback() -> Response | tuple[str, int]:
    if "error" in request.args:
        error = request.args.get("error")
        return f"OAuth error: {error}", 400

    redirect_uri = url_for("calendar.oauth_callback", _external=True)
    flow = google.start_oauth_flow(redirect_uri)
    flow.code_verifier = session.pop("google_code_verifier", None)

    flow.fetch_token(authorization_response=request.url)  # type: ignore[no-untyped-call]

    credentials = flow.credentials
    google.save_oauth_token(credentials)

    return redirect(url_for("home.index"))


@calendar_bp.route("/select-calendar", methods=["POST"])
def select_calendar():
    calendar_id = request.form.get("calendar_id", "")
    if calendar_id:
        calendars = google.fetch_calendars()
        calendar_name = next((c.name for c in calendars if c.calendar_id == calendar_id), "")
        google.save_selected_calendar(calendar_id, calendar_name)
    return redirect(url_for("home.index"))


@calendar_bp.route("/sync", methods=["POST"])
def sync():
    if not google.get_auth_status().is_authenticated:
        return redirect(url_for("home.index"))

    conferences, _ = load_and_validate_conferences()
    sync_result = google.sync_accepted_conferences(conferences)

    session["sync_result"] = {
        "created": sync_result.created,
        "updated": sync_result.updated,
        "errors": sync_result.errors,
    }
    return redirect(url_for("home.index"))
