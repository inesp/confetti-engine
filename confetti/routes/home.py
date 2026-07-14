from flask import Blueprint
from flask import render_template
from flask import session

from confetti.google import SyncResult
from confetti.google import fetch_calendars
from confetti.google import get_auth_status
from confetti.google import get_selected_calendar_id
from pathlib import Path

from confetti.google.auth import TokenRefreshError
from confetti.talks import load_talk_descriptions
from confetti.views.conf_stats import reimbursements_owed
from confetti.yaml.yaml_parser import ConfError
from confetti.yaml.yaml_parser import ErrorLevel
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.yaml.yaml_parser import load_talks

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def index():
    conferences, errors = load_and_validate_conferences()
    owed, owed_total = reimbursements_owed(conferences)
    talks = load_talks()
    talk_descriptions = load_talk_descriptions()

    desc_ids = {desc.talk_id for desc in talk_descriptions}
    missing = [talk.id for talk in talks if talk.id not in desc_ids]
    if missing:
        errors.append(
            ConfError(
                file="talks/",
                conference="-",
                errors=[
                    f"Missing description file in talks/ for: {', '.join(missing)}. Each talk needs a file named after its ID (e.g. talks/{missing[0]}.md)"
                ],
                level=ErrorLevel.warning,
            )
        )

    calendar_status = get_auth_status()
    token_error = False
    token_error_file = None
    calendars = []
    if calendar_status.is_authenticated:
        try:
            calendars = fetch_calendars()
        except TokenRefreshError as e:
            token_error = True
            token_error_file = Path(e.token_path).name
    selected_calendar_id = get_selected_calendar_id()

    sync_result_data = session.pop("sync_result", None)
    sync_result = SyncResult(**sync_result_data) if sync_result_data else None

    return render_template(
        "home.html",
        title="Confetti",
        subtitle="Conference CFP tracker",
        conferences=conferences,
        owed=owed,
        owed_total=owed_total,
        validation_errors=errors,
        talks=talks,
        talk_descriptions=talk_descriptions,
        calendar_status=calendar_status,
        calendars=calendars,
        selected_calendar_id=selected_calendar_id,
        sync_result=sync_result,
        token_error=token_error,
        token_error_file=token_error_file,
    )
