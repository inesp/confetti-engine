import logging

import yaml

from confetti.constants import SKIPPED_FILE

logger = logging.getLogger(__name__)


def load_skipped() -> list[str]:
    """Load the list of skipped conference names from skipped.yaml."""
    if not SKIPPED_FILE.exists():
        return []
    try:
        data = yaml.safe_load(SKIPPED_FILE.read_text())
    except yaml.YAMLError as e:
        logger.warning("Failed to parse skipped.yaml: %s", e)
        return []
    if isinstance(data, list):
        return [str(name) for name in data]
    if data is None:
        return []
    logger.warning("skipped.yaml should contain a list, got %s", type(data).__name__)
    return []


def add_skipped(name: str) -> None:
    """Append a conference name to skipped.yaml."""
    skipped = load_skipped()
    if name not in skipped:
        skipped.append(name)
    SKIPPED_FILE.write_text(yaml.dump(skipped, default_flow_style=False, allow_unicode=True))
