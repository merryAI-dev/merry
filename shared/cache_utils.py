import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional


def compute_file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_cache_dir(namespace: str, user_id: str) -> Path:
    base = Path("temp") / "cache" / namespace / user_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def remove_cache_file(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def clear_cache_dir(namespace: str, user_id: str) -> int:
    cache_dir = Path("temp") / "cache" / namespace / user_id
    if not cache_dir.exists():
        return 0
    count = 0
    for item in cache_dir.glob("*.json"):
        try:
            item.unlink()
            count += 1
        except Exception:
            continue
    return count
