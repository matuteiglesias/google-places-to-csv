from __future__ import annotations
import csv, json, re, time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "slugify", "now_stamp", "write_csv", "write_json",
    "_get", "_as_json", "_join",
]

# _slug_re = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in [' ', '-', '_', '/', ',', '.', ':']:
            out.append('-')
    slug = ''.join(out)
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    return slug or 'query'



def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def write_csv(rows: List[Dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")  # empty but created
        return
    # deterministic column order: union of keys across rows, sorted with common ones front
    common = ["id","resource_name","display_name","formatted_address","lat","lng",
              "primary_type","types","rating","user_ratings_total","phone","website"]
    cols = []
    seen = set()
    for c in common:
        if any(c in r for r in rows):
            cols.append(c); seen.add(c)
    for r in rows:
        for k in r.keys():
            if k not in seen:
                cols.append(k); seen.add(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

# legacy
# def write_csv(rows: List[Dict], path: str) -> None:
#     if not rows:
#         with open(path, "w", newline="", encoding="utf-8") as f:
#             f.write("")
#         return
#     keys = sorted({k for r in rows for k in r.keys()})
#     with open(path, "w", newline="", encoding="utf-8") as f:
#         w = csv.DictWriter(f, fieldnames=keys)
#         w.writeheader()
#         for r in rows:
#             w.writerow(r)


def write_json(obj: Any, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# def write_json(obj, path: str) -> None:
#     with open(path, "w", encoding="utf-8") as f:
#         json.dump(obj, f, ensure_ascii=False, indent=2)


# --- helpers ---------------------------------------------------------------


def _get(d: Dict[str, Any], path: str) -> Any:
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur

def _as_json(val: Any) -> Optional[str]:
    if val is None:
        return None
    try:
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return str(val)

def _join(items: Iterable[Any] | None, sep: str = ",") -> Optional[str]:
    if not items:
        return None
    def norm(x: Any) -> str:
        if isinstance(x, (dict, list)):
            return _as_json(x) or ""
        return str(x)
    return sep.join(norm(x) for x in items)
