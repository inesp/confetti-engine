import logging
import os
from datetime import date

from flask import Flask
from flask import render_template

from confetti.routes.calendar import calendar_bp
from confetti.routes.conferences import conferences_bp
from confetti.routes.discover import discover_bp
from confetti.routes.home import home_bp
from confetti.yaml.yaml_parser import load_and_validate_conferences
from confetti.routes.past import past_bp
from confetti.routes.scout import scout_bp

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s %(message)s",
)


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "confetti-dev-key")

    app.register_blueprint(home_bp)
    app.register_blueprint(conferences_bp)
    app.register_blueprint(past_bp)
    app.register_blueprint(scout_bp)
    app.register_blueprint(discover_bp)
    app.register_blueprint(calendar_bp)

    @app.context_processor
    def inject_validation_errors():
        _, errors = load_and_validate_conferences()
        return {"has_validation_errors": len(errors) > 0, "today": date.today()}

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template("error.html", title="Not Found", error_message="Page not found."), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        logger.error(f"Server error: {error}")
        return (
            render_template(
                "error.html",
                title="Server Error",
                error_message="An unexpected error occurred.",
            ),
            500,
        )

    return app


app = create_app()
