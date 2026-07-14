#!/usr/bin/env python
"""Generate talks/talk_stats.md from conference YAML data."""

from confetti.views.talk_stats import save_talk_stats
from confetti.yaml.yaml_parser import load_and_validate_conferences, load_talks


def main() -> None:
    conferences, _ = load_and_validate_conferences()
    talks = load_talks()
    save_talk_stats(conferences, talks)
    print("Wrote talks/talk_stats.md")


if __name__ == "__main__":
    main()
