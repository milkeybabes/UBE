from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from .bundle_reader import AssetRecord

INDEX_FILENAME = ".ube_pathid_index.json"
INDEX_VERSION = 1


@dataclass(slots=True)
class PathIdIndexEntry:
    path_id: int
    type_name: str
    name: str
    bundle_path: Path


@dataclass(slots=True)
class PathIdIndex:
    root: Path
    entries_by_path_id: dict[int, list[PathIdIndexEntry]]
    bundle_count: int = 0
    object_count: int = 0
    generated_at: str = ""
    error: str = ""


def index_path(folder: str | Path) -> Path:
    return Path(folder) / INDEX_FILENAME


def load_pathid_index(folder: str | Path) -> PathIdIndex | None:
    """Load the optional project-wide PathID index.

    The important design point is that this reads one JSON file only. It does
    not open or scan every Unity bundle while the user is clicking around in the
    UI.  If the file is missing, callers should fall back to course-local
    resolution only.
    """
    root = Path(folder)
    p = index_path(root)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return PathIdIndex(root=root, entries_by_path_id={}, error=f"Could not read {p.name}: {e}")

    entries_by_pid: dict[int, list[PathIdIndexEntry]] = {}
    for item in raw.get("records", []):
        try:
            pid = int(item.get("path_id"))
            rel_bundle = str(item.get("bundle", ""))
            if not rel_bundle:
                continue
            entry = PathIdIndexEntry(
                path_id=pid,
                type_name=str(item.get("type", "Unknown") or "Unknown"),
                name=str(item.get("name", "") or f"PathID {pid}"),
                bundle_path=(root / rel_bundle),
            )
        except Exception:
            continue
        entries_by_pid.setdefault(entry.path_id, []).append(entry)

    return PathIdIndex(
        root=root,
        entries_by_path_id=entries_by_pid,
        bundle_count=int(raw.get("bundle_count", 0) or 0),
        object_count=int(raw.get("object_count", len(raw.get("records", []))) or 0),
        generated_at=str(raw.get("generated_at", "") or ""),
    )


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return a.absolute() == b.absolute()


def _score_entry(entry: PathIdIndexEntry, current_path: Path, related_paths: list[Path]) -> int:
    # Lower is better.  Course-local/reference siblings beat unrelated global
    # matches, but all matches are still far cheaper than loading the whole game.
    if _same_path(entry.bundle_path, current_path):
        return 9999
    for rp in related_paths:
        if _same_path(entry.bundle_path, Path(rp)):
            return 0
    if entry.bundle_path.parent == current_path.parent:
        return 10
    return 50


def make_external_maps_from_index(
    pathid_index: PathIdIndex,
    current_path: str | Path,
    related_paths: list[Path] | None = None,
    existing_path_ids: set[int] | None = None,
) -> tuple[dict[int, AssetRecord], dict[int, Path]]:
    """Create lightweight external lookup maps from the JSON index.

    The AssetRecord objects are metadata-only; object=None.  They are used to
    display names/types and clickable links.  When the user clicks the link, UBE
    opens the owning bundle normally and selects the real asset.
    """
    current = Path(current_path)
    related = list(related_paths or [])
    existing = existing_path_ids or set()
    records: dict[int, AssetRecord] = {}
    bundles: dict[int, Path] = {}

    for pid, entries in pathid_index.entries_by_path_id.items():
        if pid in existing:
            continue
        best = None
        best_score = 9999
        for entry in entries:
            score = _score_entry(entry, current, related)
            if score < best_score:
                best = entry
                best_score = score
        if best is None or best_score >= 9999:
            continue
        records[pid] = AssetRecord(
            name=best.name or f"{best.type_name}_{pid}",
            type_name=best.type_name or "Unknown",
            path_id=pid,
            object=None,
        )
        bundles[pid] = best.bundle_path

    return records, bundles



def _json_line_value(line: str):
    """Parse one pretty-printed JSON value line from UBE's PathID index."""
    _, value = line.split(":", 1)
    value = value.strip()
    if value.endswith(","):
        value = value[:-1]
    return json.loads(value)


def lookup_pathid_index_records(folder: str | Path, path_id: int, max_results: int = 8) -> list[PathIdIndexEntry]:
    """Streaming lookup for one PathID without loading the full index into RAM.

    The full Walkabout index can contain millions of records.  The UI must never
    json.load() that file while opening/clicking assets.  This helper scans the
    text file line-by-line and materialises only matching records.
    """
    root = Path(folder)
    p = index_path(root)
    if not p.exists():
        return []

    matches: list[PathIdIndexEntry] = []
    target_text = f'"path_id": {int(path_id)}'
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                if target_text not in line:
                    continue
                try:
                    found_pid = int(_json_line_value(line))
                except Exception:
                    continue
                if found_pid != int(path_id):
                    continue

                item = {"path_id": found_pid, "type": "Unknown", "name": f"PathID {found_pid}", "bundle": ""}
                for subline in fh:
                    stripped = subline.strip()
                    if stripped.startswith('"type"'):
                        item["type"] = str(_json_line_value(subline) or "Unknown")
                    elif stripped.startswith('"name"'):
                        item["name"] = str(_json_line_value(subline) or item["name"])
                    elif stripped.startswith('"bundle"'):
                        item["bundle"] = str(_json_line_value(subline) or "")
                    elif stripped.startswith("}"):
                        break

                rel = str(item.get("bundle", ""))
                if rel:
                    matches.append(PathIdIndexEntry(
                        path_id=found_pid,
                        type_name=str(item.get("type", "Unknown") or "Unknown"),
                        name=str(item.get("name", "") or f"PathID {found_pid}"),
                        bundle_path=root / rel,
                    ))
                    if len(matches) >= max(1, max_results):
                        break
    except Exception:
        return matches
    return matches
