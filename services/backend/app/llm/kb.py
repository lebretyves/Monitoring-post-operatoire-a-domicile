from __future__ import annotations

from pathlib import Path


class LocalKnowledgeBase:
    def __init__(self, root: Path) -> None:
        self.root = root

    def get_excerpt(self, topic: str) -> str | None:
        if not self.root.exists():
            return None

        topic_files = {
            "terrain_guidance": "postop-terrain-context-guidance.md",
            "terrain_sources": "postop-terrain-context-sources.md",
        }
        candidate = self.root / topic_files.get(topic, "postop-home-monitoring-signs.md")
        content = self._read_file(candidate)
        if not content:
            return None

        max_chars = 500
        if topic == "clinical_package":
            max_chars = 700
        elif topic == "prioritization":
            max_chars = 300
        elif topic == "scenario_review":
            max_chars = 500
        elif topic == "summary":
            max_chars = 400
        elif topic == "terrain_guidance":
            max_chars = 1400
        elif topic == "terrain_sources":
            max_chars = 1100
        return content[:max_chars].strip() if content.strip() else None

    @staticmethod
    def _read_file(path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None
