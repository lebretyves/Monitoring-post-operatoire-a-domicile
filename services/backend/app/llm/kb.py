from __future__ import annotations

from pathlib import Path


class LocalKnowledgeBase:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_excerpt(self, topic: str) -> str | None:
        if not self.root.exists():
            return None

        candidate = self.root / "postop-home-monitoring-signs.md"
        if not candidate.exists():
            return None

        try:
            content = candidate.read_text(encoding="utf-8")
        except OSError:
            return None

        max_chars = 900
        if topic == "clinical_package":
            max_chars = 1200
        elif topic == "prioritization":
            max_chars = 700
        elif topic == "scenario_review":
            max_chars = 800
        elif topic == "summary":
            max_chars = 900
        return content[:max_chars].strip() if content.strip() else None
