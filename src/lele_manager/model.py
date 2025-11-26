from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

@dataclass
class Lesson:
    id: str
    created_at: datetime
    source: str
    topic: str
    importance: int
    text: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "source": self.source,
            "topic": self.topic,
            "importance": int(self.importance),
            "text": self.text,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Lesson:
        created_at = datetime.fromisoformat(data["created_at"])
        tags = data.get("tags") or []
        return cls(
            id=str(data["id"]),
            created_at=created_at,
            source=str(data.get("source", "")),
            topic=str(data.get("topic", "")),
            importance=int(data.get("importance", 0)),
            text=str(data.get("text", "")),
            tags=list(tags),
        )

    @classmethod
    def new(
        cls,
        *,
        source: str,
        topic: str,
        importance: int,
        text: str,
        tags: List[str] | None = None,
    ) -> Lesson:
        from uuid import uuid4

        if tags is None:
            tags = []

        return cls(
            id=str(uuid4()),
            created_at=datetime.now(timezone.utc),
            source=source,
            topic=topic,
            importance=importance,
            text=text,
            tags=tags,
        )
