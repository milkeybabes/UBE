from __future__ import annotations

from collections import defaultdict
from typing import Any

from .relationship import AssetRelationship


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _pair_key_value(item: Any) -> tuple[Any, Any]:
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1]
    for a, b in (("key", "value"), ("first", "second"), ("Key", "Value")):
        if hasattr(item, a) and hasattr(item, b):
            return getattr(item, a), getattr(item, b)
    return None, item


def _pptr_path_id(pptr: Any) -> int | None:
    if pptr is None:
        return None
    for name in ("path_id", "pathID", "m_PathID", "PathID"):
        value = _get(pptr, name, default=None)
        if value is not None:
            try:
                return int(value)
            except Exception:
                return None
    return None


def _pptr_file_id(pptr: Any) -> int | None:
    if pptr is None:
        return None
    for name in ("file_id", "fileID", "m_FileID", "FileID"):
        value = _get(pptr, name, default=None)
        if value is not None:
            try:
                return int(value)
            except Exception:
                return None
    return None


def _record_source_name(record: Any) -> str:
    try:
        return str(getattr(record, "source_name", "") or "")
    except Exception:
        return ""


def _record_key(record: Any) -> tuple[str, int]:
    return (_record_source_name(record), int(getattr(record, "path_id", 0) or 0))


def _source_key_from_unity_obj(obj: Any, path_id: int) -> tuple[str, int] | None:
    try:
        af = getattr(obj, "assets_file", None)
        name = str(getattr(af, "name", "") or "")
        if name:
            return (name, int(path_id))
    except Exception:
        pass
    return None


def _pptr_source_key(pptr: Any) -> tuple[str, int] | None:
    """Resolve a PPtr to (internal SerializedFile name, PathID) when UnityPy can deref it."""
    pid = _pptr_path_id(pptr)
    if pid in (None, 0):
        return None
    try:
        target_obj = pptr.deref()
        key = _source_key_from_unity_obj(target_obj, int(pid))
        if key is not None:
            return key
    except Exception:
        pass
    return None


def _resolve_pptr_record(bundle_index: Any | None, pptr: Any) -> tuple[Any | None, str | None]:
    """Return (AssetRecord, external_bundle) for a PPtr using source-aware resolution."""
    if bundle_index is None or pptr is None:
        return None, None
    pid = _pptr_path_id(pptr)
    if pid in (None, 0):
        return None, None

    key = _pptr_source_key(pptr)
    if key is not None:
        rec = getattr(bundle_index, "record_by_source_path_id", {}).get(key)
        if rec is not None:
            return rec, None

    # Fallback for single-file bundles or objects where UnityPy cannot deref.
    rec = getattr(bundle_index, "record_by_path_id", {}).get(int(pid))
    if rec is not None:
        return rec, None

    rec = getattr(bundle_index, "external_record_by_path_id", {}).get(int(pid))
    if rec is not None:
        ext = getattr(bundle_index, "external_bundle_by_path_id", {}).get(int(pid))
        return rec, str(ext) if ext is not None else None
    return None, None


def _is_pptr(value: Any) -> bool:
    return _pptr_path_id(value) is not None and any(
        _get(value, n, default=None) is not None
        for n in ("file_id", "fileID", "m_FileID", "FileID", "path_id", "pathID", "m_PathID", "PathID")
    )


def _field_items(obj: Any) -> list[tuple[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        return [(str(k), v) for k, v in obj.items()]
    out: list[tuple[str, Any]] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        out.append((name, value))
    return out


def _collect_pptrs(obj: Any, prefix: str = "", *, max_depth: int = 5, limit: int = 120, _seen: set[int] | None = None) -> list[tuple[str, Any]]:
    if obj is None or limit <= 0:
        return []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return []
    _seen.add(oid)

    if _is_pptr(obj):
        pid = _pptr_path_id(obj)
        if pid not in (None, 0):
            return [(prefix or "reference", obj)]
        return []

    if max_depth <= 0 or isinstance(obj, (str, bytes, bytearray, int, float, bool)):
        return []

    rows: list[tuple[str, Any]] = []
    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj[:64]):
            rows.extend(_collect_pptrs(item, f"{prefix}[{i}]" if prefix else f"[{i}]", max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
            if len(rows) >= limit:
                break
        return rows[:limit]

    for name, value in _field_items(obj):
        if name in ("object", "assets_file"):
            continue
        child = f"{prefix}.{name}" if prefix else name
        rows.extend(_collect_pptrs(value, child, max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
        if len(rows) >= limit:
            break
    return rows[:limit]


class AssetGraph:
    """Small, lazy graph of relationships between UBE assets.

    The graph is intentionally incremental:
    * Material -> Texture/Shader relationships are resolved when a material is inspected.
    * Mesh -> Material relationships are inferred lazily from MeshFilter + Renderer pairs.

    The UI only asks references()/used_by(); it does not need to know Unity internals.
    """

    def __init__(self) -> None:
        # v1.8ze: key relationships by (internal SerializedFile name, PathID)
        # rather than plain PathID. UnityFS files can contain level0, resources.assets,
        # sharedassets0.assets etc., all with overlapping PathIDs.
        self._outgoing: dict[tuple[str, int], list[AssetRelationship]] = defaultdict(list)
        self._incoming: dict[tuple[str, int], list[AssetRelationship]] = defaultdict(list)
        self._resolved_records: set[tuple[str, int]] = set()
        self._all_materials_indexed: bool = False
        self._render_links_indexed: bool = False
        self._all_audio_sources_indexed: bool = False

    def clear(self) -> None:
        self._outgoing.clear()
        self._incoming.clear()
        self._resolved_records.clear()
        self._all_materials_indexed = False
        self._render_links_indexed = False
        self._all_audio_sources_indexed = False

    def _rel_source_key(self, rel: AssetRelationship) -> tuple[str, int]:
        return (str(getattr(rel, "source_source_name", "") or ""), int(rel.source_path_id or 0))

    def _rel_target_key(self, rel: AssetRelationship) -> tuple[str, int] | None:
        if rel.target_path_id is None:
            return None
        return (str(getattr(rel, "target_source_name", "") or ""), int(rel.target_path_id or 0))

    def add(self, rel: AssetRelationship) -> None:
        # Keep it simple but avoid exact duplicates when records are inspected repeatedly.
        skey = self._rel_source_key(rel)
        existing = self._outgoing.get(skey, [])
        if rel in existing:
            return
        self._outgoing[skey].append(rel)
        tkey = self._rel_target_key(rel)
        if tkey is not None:
            self._incoming[tkey].append(rel)

    def references(self, record: Any, bundle_index: Any | None = None) -> list[AssetRelationship]:
        self.ensure_resolved(record, bundle_index)
        return list(self._outgoing.get(_record_key(record), []))

    def used_by(self, record: Any, bundle_index: Any | None = None) -> list[AssetRelationship]:
        # For reverse lookups, index the relationship families that can point to this asset.
        if bundle_index is not None:
            if record.type_name in ("Texture2D", "Shader") and not self._all_materials_indexed:
                self.index_all_materials(bundle_index)
            if record.type_name in ("Material", "Mesh") and not self._render_links_indexed:
                self.index_render_links(bundle_index)
            if record.type_name in ("AudioClip", "AudioMixerGroupController") and not self._all_audio_sources_indexed:
                self.index_all_audio_sources(bundle_index)
        return list(self._incoming.get(_record_key(record), []))

    def ensure_resolved(self, record: Any, bundle_index: Any | None = None) -> None:
        if record is None:
            return
        if record.type_name == "Mesh" and bundle_index is not None and not self._render_links_indexed:
            self.index_render_links(bundle_index)
        if record.type_name in ("GameObject", "Transform", "MeshRenderer", "SkinnedMeshRenderer", "MeshFilter") and bundle_index is not None and not self._render_links_indexed:
            self.index_render_links(bundle_index)
        rkey = _record_key(record)
        if rkey in self._resolved_records:
            return
        if record.type_name == "Material":
            self._resolve_material(record, bundle_index)
        elif record.type_name == "AudioSource":
            self._resolve_audio_source(record, bundle_index)
        elif record.type_name in (
            "AudioMixerController", "AudioMixerGroupController",
            "AudioMixerSnapshotController", "AudioMixerEffectController",
        ):
            self._resolve_audio_mixer_asset(record, bundle_index)
        elif record.type_name == "MonoBehaviour":
            self._resolve_mono_behaviour(record, bundle_index)
        self._resolved_records.add(rkey)

    def index_all_materials(self, bundle_index: Any) -> None:
        for rec in getattr(bundle_index, "objects_by_type", {}).get("Material", []):
            self.ensure_resolved(rec, bundle_index)
        self._all_materials_indexed = True

    def index_all_audio_sources(self, bundle_index: Any) -> None:
        """Index AudioSource -> AudioClip links for reverse AudioClip lookups."""
        records = getattr(bundle_index, "objects_by_type", {}).get("AudioSource", [])
        for rec in records:
            self.ensure_resolved(rec, bundle_index)
        self._all_audio_sources_indexed = True

    def _resolve_audio_source(self, record: Any, bundle_index: Any | None = None) -> None:
        try:
            data = record.object.read()
        except Exception:
            return
        self._add_pptr_relationship(
            record,
            _get(data, "m_GameObject", "gameObject", "game_object", default=None),
            "Object",
            bundle_index,
            expected_type="GameObject",
        )
        self._add_pptr_relationship(
            record,
            _get(data, "m_audioClip", "m_AudioClip", "audioClip", "audio_clip", "m_Clip", "clip", default=None),
            "Audio Clip",
            bundle_index,
            expected_type="AudioClip",
        )
        self._add_pptr_relationship(
            record,
            _get(
                data,
                "m_OutputAudioMixerGroup", "OutputAudioMixerGroup", "outputAudioMixerGroup",
                "output_audio_mixer_group", default=None,
            ),
            "Output Mixer Group",
            bundle_index,
            expected_type="AudioMixerGroupController",
        )

    def _resolve_audio_mixer_asset(self, record: Any, bundle_index: Any | None = None) -> None:
        """Expose mixer/group/snapshot/effect wiring without assuming one Unity layout.

        Unity has changed AudioMixer typetrees across releases, so field-path labels
        are preserved and every non-null PPtr is resolved lazily. This catches group
        hierarchy, controller ownership, snapshots, effects and send targets.
        """
        try:
            data = record.object.read()
        except Exception:
            return

        # Prefer short educational labels for the common fields.
        common_fields = (
            ("Owning Mixer", ("m_AudioMixer", "audioMixer", "m_Controller", "controller")),
            ("Master / Output Group", ("m_OutputGroup", "outputGroup", "m_MasterGroup", "masterGroup")),
            ("Parent Group", ("m_Parent", "parent", "m_ParentGroup", "parentGroup")),
            ("Start Snapshot", ("m_StartSnapshot", "startSnapshot", "m_CurrentSnapshot", "currentSnapshot")),
            ("Owning Group", ("m_Group", "group", "m_Owner", "owner")),
            ("Send Target", ("m_SendTarget", "sendTarget", "m_Target", "target")),
        )
        seen: set[tuple[int | None, int | None]] = set()
        for label, names in common_fields:
            pptr = _get(data, *names, default=None)
            pid = _pptr_path_id(pptr)
            if pid in (None, 0):
                continue
            seen.add((_pptr_file_id(pptr), pid))
            self._add_pptr_relationship(record, pptr, label, bundle_index, expected_type="Audio Mixer Asset")

        # Then capture version-specific arrays and nested PPtrs using their real field path.
        for field_path, pptr in _collect_pptrs(data, max_depth=6, limit=160):
            pid = _pptr_path_id(pptr)
            key = (_pptr_file_id(pptr), pid)
            if pid in (None, 0) or key in seen:
                continue
            seen.add(key)
            label = field_path.replace("m_", "").replace(".", " / ") or "Mixer reference"
            self._add_pptr_relationship(record, pptr, label, bundle_index, expected_type="Audio Mixer Asset")

    def index_render_links(self, bundle_index: Any) -> None:
        """Infer Mesh -> Material links from MeshFilter + MeshRenderer components.

        Unity does not usually store material slots on the Mesh asset itself. A normal
        rendered object is assembled from:

            GameObject -> MeshFilter -> Mesh
            GameObject -> MeshRenderer -> Materials[]

        So we pair MeshFilter and MeshRenderer components that share the same GameObject.
        SkinnedMeshRenderer usually stores both mesh and materials directly, so that path
        is handled as well.
        """
        if self._render_links_indexed:
            return

        records_by_type = getattr(bundle_index, "objects_by_type", {})
        mesh_by_gameobject: dict[tuple[str, int], tuple[Any, Any, Any]] = {}

        # GameObject -> Component relationships. This is the backbone of the
        # educational Object Inspector: a Unity object is mostly a named holder
        # for components such as Transform, MeshFilter and MeshRenderer.
        for go_rec in records_by_type.get("GameObject", []):
            try:
                data = go_rec.object.read()
            except Exception:
                continue
            components = _as_list(_get(data, "m_Components", "m_Component", default=None))
            for slot, item in enumerate(components):
                comp = _get(item, "component", "m_Component", default=item)
                self._add_pptr_relationship(go_rec, comp, f"Component {slot}", bundle_index, expected_type="Component")

        # Transform hierarchy relationships. These make parent/child objects easy
        # to browse without pretending UBE is a complete scene editor.
        for tr_rec in records_by_type.get("Transform", []):
            try:
                data = tr_rec.object.read()
            except Exception:
                continue
            self._add_pptr_relationship(tr_rec, _get(data, "m_GameObject", "game_object", default=None), "Object", bundle_index, expected_type="GameObject")
            self._add_pptr_relationship(tr_rec, _get(data, "m_Father", "father", default=None), "Parent Transform", bundle_index, expected_type="Transform")
            for slot, child in enumerate(_as_list(_get(data, "m_Children", "children", default=None))):
                self._add_pptr_relationship(tr_rec, child, f"Child Transform {slot}", bundle_index, expected_type="Transform")

        for mf_rec in records_by_type.get("MeshFilter", []):
            try:
                data = mf_rec.object.read()
            except Exception:
                continue
            go = _get(data, "m_GameObject", "game_object", default=None)
            mesh = _get(data, "m_Mesh", "mesh", default=None)
            go_rec, _ = _resolve_pptr_record(bundle_index, go)
            mesh_rec, _ = _resolve_pptr_record(bundle_index, mesh)
            self._add_pptr_relationship(mf_rec, go, "Object", bundle_index, expected_type="GameObject")
            if go_rec is None or mesh_rec is None:
                continue
            mesh_by_gameobject[_record_key(go_rec)] = (mesh, mf_rec, mesh_rec)
            self._add_pptr_relationship(mf_rec, mesh, "Mesh", bundle_index, expected_type="Mesh")

        for mr_rec in records_by_type.get("MeshRenderer", []):
            try:
                data = mr_rec.object.read()
            except Exception:
                continue
            go = _get(data, "m_GameObject", "game_object", default=None)
            go_rec, _ = _resolve_pptr_record(bundle_index, go)
            materials = _as_list(_get(data, "m_Materials", "materials", default=None))
            self._add_pptr_relationship(mr_rec, go, "Object", bundle_index, expected_type="GameObject")
            if not materials:
                continue

            # Renderer -> Material is a direct component relationship.
            for slot, mat in enumerate(materials):
                self._add_pptr_relationship(mr_rec, mat, f"Material Slot {slot}", bundle_index, expected_type="Material")

            # Mesh -> Material is inferred through the sibling MeshFilter on the exact same GameObject.
            pair = mesh_by_gameobject.get(_record_key(go_rec)) if go_rec is not None else None
            if pair is None:
                continue
            _mesh_pptr, _mesh_filter_rec, mesh_rec = pair
            for slot, mat in enumerate(materials):
                self._add_pptr_relationship(mesh_rec, mat, f"Material Slot {slot}", bundle_index, expected_type="Material")

        # Skinned renderers often include both mesh and materials directly.
        for smr_rec in records_by_type.get("SkinnedMeshRenderer", []):
            try:
                data = smr_rec.object.read()
            except Exception:
                continue
            go = _get(data, "m_GameObject", "game_object", default=None)
            mesh = _get(data, "m_Mesh", "mesh", default=None)
            materials = _as_list(_get(data, "m_Materials", "materials", default=None))
            self._add_pptr_relationship(smr_rec, go, "Object", bundle_index, expected_type="GameObject")
            self._add_pptr_relationship(smr_rec, mesh, "Mesh", bundle_index, expected_type="Mesh")
            mesh_rec, _ = _resolve_pptr_record(bundle_index, mesh)
            for slot, mat in enumerate(materials):
                self._add_pptr_relationship(smr_rec, mat, f"Material Slot {slot}", bundle_index, expected_type="Material")
                if mesh_rec is not None:
                    self._add_pptr_relationship(mesh_rec, mat, f"Material Slot {slot}", bundle_index, expected_type="Material")
            self._add_pptr_relationship(smr_rec, _get(data, "m_RootBone", "root_bone", default=None), "Root Bone", bundle_index, expected_type="Transform")
            for slot, bone in enumerate(_as_list(_get(data, "m_Bones", "bones", default=None))[:24]):
                self._add_pptr_relationship(smr_rec, bone, f"Bone {slot}", bundle_index, expected_type="Transform")

        self._render_links_indexed = True

    def _resolve_material(self, record: Any, bundle_index: Any | None = None) -> None:
        try:
            data = record.object.read()
        except Exception:
            return

        shader = _get(data, "m_Shader", "shader", default=None)
        if shader is not None:
            self._add_pptr_relationship(record, shader, "Shader", bundle_index, expected_type="Shader")

        saved = _get(data, "m_SavedProperties", "saved_properties", default=None)
        if saved is None:
            return

        tex_envs = _as_list(_get(saved, "m_TexEnvs", "tex_envs", default=None))
        for item in tex_envs:
            key, value = _pair_key_value(item)
            texture = _get(value, "m_Texture", "texture", default=value)
            relation = str(key) if key is not None else "Texture"
            self._add_pptr_relationship(record, texture, relation, bundle_index, expected_type="Texture2D")

    def _resolve_mono_behaviour(self, record: Any, bundle_index: Any | None = None) -> None:
        """Best-effort relationship scan for custom script components.

        MonoBehaviour fields are game-specific, so this does not try to know the
        schema.  It simply scans the exposed object/typetree for PPtr references
        and adds them as clickable relationships in the inspector.
        """
        data = None
        try:
            data = record.object.read_typetree()
        except Exception:
            try:
                data = record.object.read()
            except Exception:
                data = None
        if data is None:
            return
        seen: set[tuple[str, int | None]] = set()
        for path, pptr in _collect_pptrs(data):
            pid = _pptr_path_id(pptr)
            key = (path, pid)
            if key in seen:
                continue
            seen.add(key)
            expected = "Asset"
            low = path.lower()
            if "gameobject" in low:
                expected = "GameObject"
            elif "script" in low:
                expected = "MonoScript"
            elif "transform" in low:
                expected = "Transform"
            elif "material" in low:
                expected = "Material"
            elif "texture" in low or "sprite" in low:
                expected = "Texture2D"
            elif "audio" in low:
                expected = "AudioClip"
            elif "mesh" in low:
                expected = "Mesh"
            self._add_pptr_relationship(record, pptr, path, bundle_index, expected_type=expected)

    def _add_pptr_relationship(
        self,
        source: Any,
        pptr: Any,
        relation: str,
        bundle_index: Any | None,
        expected_type: str = "",
    ) -> None:
        if source is None or pptr is None:
            return
        path_id = _pptr_path_id(pptr)
        file_id = _pptr_file_id(pptr)
        target_record = None
        external_bundle = None
        if path_id is not None and bundle_index is not None:
            target_record, external_bundle = _resolve_pptr_record(bundle_index, pptr)

        # PathID 0 is Unity's normal "empty slot" value. Do not pollute the graph with it.
        if path_id in (None, 0) and target_record is None:
            return

        if target_record is not None:
            target_name = target_record.name
            target_type = target_record.type_name
            resolved = True
        else:
            target_name = f"PathID {path_id}" if path_id is not None else "None"
            target_type = expected_type or "Unknown"
            resolved = False

        self.add(
            AssetRelationship(
                source_path_id=source.path_id,
                source_name=source.name,
                source_type=source.type_name,
                target_path_id=path_id,
                target_name=target_name,
                target_type=target_type,
                relationship=relation,
                file_id=file_id,
                resolved=resolved,
                external_bundle=external_bundle,
                source_source_name=_record_source_name(source),
                target_source_name=_record_source_name(target_record) if target_record is not None else "",
            )
        )
