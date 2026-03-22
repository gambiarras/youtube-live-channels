import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from live_stream_catalog.models import Channel


def load_channels_file(path: Path, default_resolution: str = "best") -> list[Channel]:
    if not path.exists():
        return []

    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Channel.from_dict(item, default_resolution=default_resolution) for item in raw]


def write_json_atomic(path: Path, payload: list[dict] | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=path.parent) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        temp_path = Path(tmp.name)

    temp_path.replace(path)