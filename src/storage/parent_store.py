from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple


def load_parents(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_parents(path: Path, parents: Dict[str, str]) -> None:
    path.write_text(
        json.dumps(parents, ensure_ascii=False),
        encoding="utf-8",
    )


def merge_parents(current: Dict[str, str], new_parents: Dict[str, str]) -> Dict[str, str]:
    merged = dict(current or {})
    merged.update(dict(new_parents or {}))
    return merged


def get_parent(parents: Dict[str, str], parent_id: str) -> Optional[str]:
    return (parents or {}).get(parent_id)


def delete_parents_for_rcept(parents: Dict[str, str], rcept_no: str) -> Tuple[Dict[str, str], int]:
    prefix = f"{rcept_no}::"
    before = len(parents or {})
    filtered = {key: value for key, value in dict(parents or {}).items() if not key.startswith(prefix)}
    return filtered, before - len(filtered)
