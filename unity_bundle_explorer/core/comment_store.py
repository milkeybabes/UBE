from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


COMMENT_FORMAT = "UBE comments"
COMMENT_FORMAT_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_filename(value: str) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "bundle"))
    text = text.strip(" ._") or "bundle"
    return text[:160]


def application_root() -> Path:
    """Return the folder beside the running UBE application/source tree."""
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
    except Exception:
        pass
    # .../unity_bundle_explorer/core/comment_store.py -> application root
    return Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class CommentLoadResult:
    count: int = 0
    path: Path | None = None
    matched_existing: bool = False
    message: str = ""


class BundleCommentStore:
    """Small, human-readable JSON sidecar store for UBE asset comments.

    A Unity PathID is only local to its owning SerializedFile, so the in-memory
    key is (source_name, path_id).  The JSON is additionally bound to the exact
    source bundle/file SHA256, preventing a same-number PathID in another bundle
    from receiving the wrong annotation.
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else application_root()
        self.comments_dir = self.root / "UBE_Comments"
        self.bundle_index: Any = None
        self.file_path: Path | None = None
        self.comments: dict[tuple[str, int], dict[str, Any]] = {}
        self.load_message = ""
        self.loaded_existing = False
        self._loaded_raw: dict[str, Any] | None = None

    def reset(self) -> None:
        self.bundle_index = None
        self.file_path = None
        self.comments = {}
        self.load_message = ""
        self.loaded_existing = False
        self._loaded_raw = None

    @staticmethod
    def record_key(rec: Any) -> tuple[str, int]:
        source_name = str(getattr(rec, "source_name", "") or "")
        if not source_name:
            source_file = getattr(rec, "source_file", None)
            try:
                source_name = Path(source_file).name if source_file else ""
            except Exception:
                source_name = str(source_file or "")
        return source_name, int(getattr(rec, "path_id", 0) or 0)

    def _bundle_sha256(self) -> str:
        return str(getattr(self.bundle_index, "sha256", "") or "")

    def _bundle_name(self) -> str:
        try:
            return Path(getattr(self.bundle_index, "path", "")).name
        except Exception:
            return str(getattr(self.bundle_index, "path", "") or "bundle")

    def _preferred_path(self) -> Path:
        digest = self._bundle_sha256()[:12] or "nohash"
        return self.comments_dir / f"{_safe_filename(self._bundle_name())}.{digest}.ube-comments.json"

    @staticmethod
    def _json_bundle_hash(data: dict[str, Any]) -> str:
        bundle = data.get("bundle", {}) if isinstance(data, dict) else {}
        return str(bundle.get("sha256", "") or "") if isinstance(bundle, dict) else ""

    def _find_existing_file(self) -> Path | None:
        preferred = self._preferred_path()
        if preferred.exists():
            return preferred
        if not self.comments_dir.exists():
            return None
        wanted = self._bundle_sha256().lower()
        if not wanted:
            return None
        # A shared/renamed JSON is still detected by its embedded bundle hash.
        for candidate in sorted(self.comments_dir.glob("*.ube-comments.json")):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                continue
            if self._json_bundle_hash(data).lower() == wanted:
                return candidate
        return None

    def load_for_bundle(self, bundle_index: Any) -> CommentLoadResult:
        self.reset()
        self.bundle_index = bundle_index
        self.file_path = self._preferred_path()
        existing = self._find_existing_file()
        if existing is None:
            self.load_message = "No existing comment JSON; it will be created when the first comment is saved."
            return CommentLoadResult(0, self.file_path, False, self.load_message)

        self.file_path = existing
        try:
            data = json.loads(existing.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top-level JSON value is not an object")
            embedded_hash = self._json_bundle_hash(data)
            if embedded_hash and embedded_hash.lower() != self._bundle_sha256().lower():
                raise ValueError("bundle SHA256 does not match the currently opened source")
            rows = data.get("comments", [])
            if not isinstance(rows, list):
                raise ValueError("comments must be a JSON list")
            loaded: dict[tuple[str, int], dict[str, Any]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    source_name = str(row.get("source_name", "") or "")
                    path_id = int(row.get("path_id", 0) or 0)
                except Exception:
                    continue
                text = str(row.get("comment", "") or "")
                if not text.strip():
                    continue
                clean = dict(row)
                clean["source_name"] = source_name
                clean["path_id"] = path_id
                clean["comment"] = text
                loaded[(source_name, path_id)] = clean
            self.comments = loaded
            self._loaded_raw = data
            self.loaded_existing = True
            self.load_message = f"Loaded {len(loaded)} comment(s) from {existing.name}."
            return CommentLoadResult(len(loaded), existing, True, self.load_message)
        except Exception as exc:
            self.comments = {}
            self.loaded_existing = False
            self.load_message = f"Could not read {existing.name}: {exc}"
            return CommentLoadResult(0, existing, False, self.load_message)

    def get(self, rec: Any) -> str:
        row = self.comments.get(self.record_key(rec), {})
        return str(row.get("comment", "") or "")

    def has(self, rec: Any) -> bool:
        return bool(self.get(rec).strip())

    def set(self, rec: Any, text: str) -> None:
        key = self.record_key(rec)
        clean_text = str(text or "").strip()
        if not clean_text:
            self.comments.pop(key, None)
            return
        old = self.comments.get(key, {})
        self.comments[key] = {
            "source_name": key[0],
            "path_id": key[1],
            "asset_type": str(getattr(rec, "type_name", "") or old.get("asset_type", "")),
            "asset_name": str(getattr(rec, "name", "") or old.get("asset_name", "")),
            "comment": clean_text,
            "updated_utc": _utc_now(),
        }

    def count(self) -> int:
        return len(self.comments)

    def _document(self) -> dict[str, Any]:
        idx = self.bundle_index
        header = getattr(idx, "header", None)
        rows = list(self.comments.values())
        rows.sort(key=lambda r: (
            str(r.get("source_name", "")).lower(),
            str(r.get("asset_type", "")).lower(),
            str(r.get("asset_name", "")).lower(),
            int(r.get("path_id", 0) or 0),
        ))
        return {
            "format": COMMENT_FORMAT,
            "format_version": COMMENT_FORMAT_VERSION,
            "bundle": {
                "name": self._bundle_name(),
                "sha256": self._bundle_sha256(),
                "source_kind": str(getattr(header, "source_kind", "") or ""),
                "unity_version": str(
                    getattr(header, "unity_revision", "")
                    or getattr(header, "unity_version", "")
                    or ""
                ),
            },
            "updated_utc": _utc_now(),
            "comments": rows,
        }

    def save(self) -> Path:
        if self.bundle_index is None:
            raise RuntimeError("No bundle is currently attached to the comment store")
        if self.file_path is None:
            self.file_path = self._preferred_path()
        self.comments_dir.mkdir(parents=True, exist_ok=True)
        target = self.file_path
        # If an unreadable file was discovered, preserve it before replacing it.
        if target.exists() and not self.loaded_existing and self.load_message.startswith("Could not read"):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = target.with_suffix(target.suffix + f".broken-{stamp}")
            try:
                target.replace(backup)
            except Exception:
                pass
        payload = json.dumps(self._document(), ensure_ascii=False, indent=2) + "\n"
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(target)
        self.loaded_existing = True
        self.load_message = f"Saved {len(self.comments)} comment(s) to {target.name}."
        return target
