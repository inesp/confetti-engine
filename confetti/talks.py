from dataclasses import dataclass

from confetti.constants import TALKS_DIR


@dataclass
class TalkDescription:
    talk_id: str
    title: str
    description: str


def load_talk_descriptions() -> list[TalkDescription]:
    """Load talk titles and descriptions from markdown files in talks/.

    Each talk is a file named after its ID (e.g. talks/estimation.md).
    """
    talks = []
    if not TALKS_DIR.exists():
        return []

    for md_file in sorted(TALKS_DIR.glob("*.md")):
        if md_file.name in ("README.md", "videos.md"):
            continue
        try:
            content = md_file.read_text()
        except OSError:
            continue

        title = None
        desc_lines: list[str] = []
        in_desc = False
        for line in content.strip().split("\n"):
            if line.startswith("# Titles") and not title:
                continue
            if line.startswith("### Public") or line.startswith("### Not public"):
                continue
            if line.startswith("- ") and not title:
                title = line[2:].strip()
                continue
            if line.startswith("# Description"):
                in_desc = True
                continue
            if in_desc and line.strip():
                desc_lines.append(line.strip())
                if len(desc_lines) >= 3:
                    break

        if title:
            talks.append(TalkDescription(talk_id=md_file.stem, title=title, description=" ".join(desc_lines)))

    return talks
