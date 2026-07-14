import os
from datetime import timedelta
from pathlib import Path

# Where the data lives: conferences/, talks/, credentials, and logs all hang off this.
# Defaults to the repo root, so the bundled sample data works out of the box. Set
# CONFETTI_DATA_DIR to run the app against your own conference directory instead.
_env_data_dir = os.environ.get("CONFETTI_DATA_DIR")
DATA_DIR = Path(_env_data_dir).expanduser() if _env_data_dir else Path(__file__).parent.parent
PROJECT_ROOT = DATA_DIR  # backwards-compatible alias

CONFERENCES_DIR = PROJECT_ROOT / "conferences"
SKIPPED_FILE = CONFERENCES_DIR / "skipped.yaml"
SCOUT_LOG = PROJECT_ROOT / "scout_debug.log"
DISCOVER_LOG = PROJECT_ROOT / "discover_debug.log"
TALKS_DIR = PROJECT_ROOT / "talks"
TALKS_FILE = TALKS_DIR / "talks.yml"
TALK_STATS_FILE = TALKS_DIR / "talk_stats.md"
GOOGLE_CREDENTIALS_FILE = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN_FILE = PROJECT_ROOT / "google_token.json"
GOOGLE_CALENDAR_CONFIG_FILE = PROJECT_ROOT / "google_calendar_config.json"
# IANA timezone used for calendar events created by the sync.
CALENDAR_TIMEZONE = os.environ.get("CONFETTI_TIMEZONE", "Europe/Amsterdam")
SCOUT_TIMEOUT = timedelta(minutes=5)
DISCOVER_TIMEOUT = timedelta(minutes=10)

# Scouting/discovery run on a cheap model and a hard dollar ceiling to protect the
# session usage window. Bump the model to "sonnet" if extraction quality drops.
SCOUT_MODEL = "haiku"
DISCOVER_MODEL = "haiku"
# Scout confs in small batches so one run's context can't balloon across many pages.
SCOUT_CHUNK_SIZE = 4
SCOUT_MAX_BUDGET_USD = 0.5
DISCOVER_MAX_BUDGET_USD = 1.0
BEFORE_CFP_OPEN = timedelta(days=2)
BEFORE_CONFERENCE_SCOUT = timedelta(days=180)
CFP_ESTIMATED_DURATION = timedelta(days=60)
CFP_BEFORE_CONFERENCE = timedelta(days=180)
