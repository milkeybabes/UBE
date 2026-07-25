from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .unityfs_header import UnityFSHeader, read_unityfs_header
from ..utils.hash_utils import sha256_file


@dataclass(slots=True)
class AssetRecord:
    name: str
    type_name: str
    path_id: int
    object: Any = None
    # v1.8p: source file that owns this PathID.  For UnityFS bundles this is
    # the bundle path; for SerializedFile mode this is the .assets/globalgamemanagers file.
    source_file: Path | None = None
    # Name of the internal Unity SerializedFile that owns the object, e.g.
    # level0 / resources.assets / sharedassets0.assets.  UnityFS bundles can
    # contain several SerializedFiles, and PathIDs are only unique inside each
    # one, so this is needed for exact PPtr resolution.
    source_name: str = ""
    # v2.0u: sibling streamed-data files discovered beside the opened Unity
    # file.  Every record shares the same tuple, so this adds negligible memory
    # while allowing exporters to resolve AudioClip/Texture streamed payloads
    # even when only the main data.unity3d/.assets file was selected.
    companion_resource_paths: tuple[Path, ...] = ()


@dataclass(slots=True)
class BundleIndex:
    path: Path
    header: UnityFSHeader
    sha256: str
    objects_by_type: dict[str, list[AssetRecord]] = field(default_factory=dict)
    record_by_path_id: dict[int, AssetRecord] = field(default_factory=dict)
    # v1.8zd: exact map for UnityFS bundles with multiple internal SerializedFiles.
    # Key is (internal SerializedFile name, PathID).
    record_by_source_path_id: dict[tuple[str, int], AssetRecord] = field(default_factory=dict)
    # Filled by the UI when a project/folder is available.  These are sibling
    # bundle records used only for resolving external PPtr references in
    # inspectors/relationship links.
    external_record_by_path_id: dict[int, AssetRecord] = field(default_factory=dict)
    # Complete loaded sibling records grouped by type.  The older flat PathID
    # map is still used for quick PPtr lookup, but it necessarily drops records
    # when two SerializedFiles reuse the same PathID.  Animation hierarchy/hash
    # resolution needs every Transform and GameObject, so keep the full lists as
    # lightweight references to the already-loaded sibling BundleIndexes.
    external_records_by_type: dict[str, list[AssetRecord]] = field(default_factory=dict)
    external_bundle_by_path_id: dict[int, Path] = field(default_factory=dict)
    external_bundle_count: int = 0
    external_object_count: int = 0
    external_error: str = ""
    # Raw sibling resource stores such as sharedassets3.resource or .resS.
    # These are support files rather than Unity object databases, so they are
    # not shown as assets in the tree.
    companion_resource_paths: tuple[Path, ...] = ()
    error: str = ""
    safe_open_state: str = ""
    safe_open_detail: str = ""

    @property
    def object_count(self) -> int:
        return sum(len(v) for v in self.objects_by_type.values())


def discover_companion_resources(path: str | Path) -> tuple[Path, ...]:
    """Return streamed-resource files stored beside a Unity data file.

    Unity player-data folders commonly separate small serialized metadata from
    large payloads.  Selecting ``data.unity3d`` alone should therefore still
    make sibling ``*.resource`` and ``*.resS`` stores available to exporters.
    The files remain opaque support data and are not parsed as standalone
    Unity bundles.
    """
    source = Path(path)
    folder = source.parent
    try:
        children = list(folder.iterdir())
    except Exception:
        return ()

    resources: list[Path] = []
    for child in children:
        try:
            if not child.is_file() or child == source:
                continue
            lower_name = child.name.lower()
            if lower_name.endswith(".resource") or lower_name.endswith(".ress"):
                resources.append(child.resolve())
        except Exception:
            continue
    resources.sort(key=lambda value: value.name.lower())
    return tuple(resources)


def load_bundle(path: str | Path, include_objects: bool = True, progress_callback=None) -> BundleIndex:
    p = Path(path)

    def report(message: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(str(message))
        except Exception:
            pass

    report(f"Reading Unity header — {p.name}")
    header = read_unityfs_header(p)
    report(f"Checking bundle identity — {p.name}")

    def hash_progress(done: int, total: int) -> None:
        if total > 0:
            report(f"Checking bundle identity — {done / total * 100.0:.0f}%")
        else:
            report(f"Checking bundle identity — {done:,} bytes")

    companion_resources = discover_companion_resources(p)
    idx = BundleIndex(
        path=p,
        header=header,
        sha256=sha256_file(p, progress_callback=hash_progress),
        companion_resource_paths=companion_resources,
    )
    if companion_resources:
        report(
            f"Found {len(companion_resources):,} sibling streamed resource "
            f"file{'s' if len(companion_resources) != 1 else ''}"
        )

    if not include_objects:
        return idx

    try:
        import UnityPy  # type: ignore
    except Exception as e:
        idx.error = f"UnityPy not installed or failed to import: {e}"
        return idx

    try:
        # UnityPy can load both UnityFS AssetBundles and Unity SerializedFile
        # sources (.assets/globalgamemanagers/sharedassets/resources).  UBE keeps
        # the old function name for compatibility but the source header tells the
        # UI which kind of Unity file was opened.
        report(f"Opening Unity object database — {p.name}")
        env = UnityPy.load(str(p))
        objects = env.objects
        try:
            object_total = len(objects)
        except Exception:
            object_total = 0
        for object_number, obj in enumerate(objects, start=1):
            if object_number == 1 or object_number % 250 == 0:
                if object_total:
                    report(f"Decoding Unity objects — {object_number:,} / {object_total:,}")
                else:
                    report(f"Decoding Unity objects — {object_number:,}")
            type_name = getattr(obj.type, "name", str(obj.type))
            name = ""
            try:
                data = obj.read()
                name = getattr(data, "name", "") or getattr(data, "m_Name", "") or ""
                if not name and type_name == "Shader":
                    parsed = getattr(data, "m_ParsedForm", None) or getattr(data, "parsed_form", None)
                    name = getattr(parsed, "m_Name", "") or getattr(parsed, "name", "") or ""
            except Exception:
                data = None
            source_name = ""
            try:
                source_name = str(getattr(getattr(obj, "assets_file", None), "name", "") or "")
            except Exception:
                source_name = ""
            if not source_name:
                try:
                    source_name = p.name
                except Exception:
                    source_name = str(p)
            rec = AssetRecord(
                name=name or f"{type_name}_{obj.path_id}",
                type_name=type_name,
                path_id=obj.path_id,
                object=obj,
                source_file=p,
                source_name=source_name,
                companion_resource_paths=companion_resources,
            )
            idx.objects_by_type.setdefault(type_name, []).append(rec)
            # Legacy path-id map is kept for UI/path lookup, but PathIDs can
            # collide between internal files.  Do not overwrite a more useful
            # named record with an anonymous collision unless no entry exists.
            if rec.path_id not in idx.record_by_path_id or (rec.name and not idx.record_by_path_id[rec.path_id].name):
                idx.record_by_path_id[rec.path_id] = rec
            idx.record_by_source_path_id[(source_name, rec.path_id)] = rec
        report(f"Decoded {idx.object_count:,} Unity objects — {p.name}")
    except Exception as e:
        idx.error = f"UnityPy failed to load bundle: {e}"

    return idx
