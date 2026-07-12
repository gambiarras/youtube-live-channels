from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Channel:
    id: str
    name: str
    source_url: str
    logo: str
    group: str
    source_type: str
    resolution: str = "best"
    stream_url: str | None = None
    status: str = "pending"
    error: str | None = None
    resolved_at: str | None = None
    expires_at: str | None = None
    ttl_seconds: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_resolution: str = "best") -> "Channel":
        return cls(
            id=data["id"],
            name=data["name"],
            source_url=data.get("source_url", data.get("url", "")),
            logo=data.get("logo", ""),
            group=data.get("group", "general"),
            source_type=data.get("source_type", "unknown"),
            resolution=data.get("resolution", default_resolution),
            stream_url=data.get("stream_url"),
            status=data.get("status", "pending"),
            error=data.get("error"),
            resolved_at=data.get("resolved_at"),
            expires_at=data.get("expires_at"),
            ttl_seconds=data.get("ttl_seconds"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
