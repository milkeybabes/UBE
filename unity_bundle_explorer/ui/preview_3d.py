from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any


class Preview3DWidgetBase:
    pass


try:
    from PySide6.QtCore import Qt, QPoint, QRect, QSettings
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
except Exception:
    QOpenGLWidget = None


def preview_help_html() -> str:
    """Compact scrollable HTML help for the 3D preview."""
    def rows(items):
        return "".join(
            f"<tr><td class='key'>{k}</td><td>{v}</td></tr>"
            for k, v in items
        )

    return f"""
<html>
<head>
<style>
body {{
  background: #181a1f;
  color: #f2f2f2;
  font-family: Segoe UI, Arial, sans-serif;
  font-size: 10.5pt;
}}
h1 {{
  font-size: 18pt;
  margin: 0 0 8px 0;
  color: #ffffff;
}}
h2 {{
  font-size: 12.5pt;
  margin: 18px 0 6px 0;
  color: #8fd0ff;
  border-bottom: 1px solid #3a3f4b;
  padding-bottom: 3px;
}}
p {{
  margin: 4px 0 8px 0;
  color: #c9d0dc;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 6px;
}}
td {{
  padding: 3px 6px;
  vertical-align: top;
}}
td.key {{
  width: 180px;
  white-space: nowrap;
  color: #ffd36a;
  font-family: Consolas, Cascadia Mono, monospace;
}}
.note {{
  color: #9aa6b8;
  font-size: 9.5pt;
}}
.badge {{
  display: inline-block;
  color: #111;
  background: #8fd0ff;
  border-radius: 8px;
  padding: 2px 7px;
  font-weight: bold;
}}
</style>
</head>
<body>
<h1><span class='badge'>i</span>&nbsp;&nbsp;3D Preview Help</h1>
<p>This panel is scrollable. These controls apply when the 3D preview is active or focused.</p>

<h2>Mouse</h2>
<table>
{rows([
    ("Left drag", "Orbit / tumble"),
    ("Shift + left drag", "Draw a box and isolate the render elements touched by it"),
    ("Ctrl + left drag", "Draw a box and hide the render elements touched by it"),
    ("Right drag", "Rotate one selected axis"),
    ("Shift + right drag", "Snap corrective rotation to 15° steps"),
    ("Middle drag", "Pan"),
    ("Mouse wheel", "Zoom"),
    ("Ctrl + wheel", "Adjust FOV / lens"),
])}
</table>

<h2>Views</h2>
<table>
{rows([
    ("0", "Isometric / reset"),
    ("1", "Top"),
    ("2", "Bottom"),
    ("3", "Front"),
    ("4", "Back"),
    ("5", "Left"),
    ("6", "Right"),
])}
</table>

<h2>Axis / fine rotation</h2>
<table>
{rows([
    ("X / Y / Z", "Choose right-drag axis"),
    ("Q / E", "Roll Z -15° / +15°"),
    ("A", "Toggle bottom-left XYZ axis indicator"),
    ("C", "Toggle close-clip mode"),
])}
</table>

<h2>Ground / up basis</h2>
<table>
{rows([
    ("Ctrl + X / Y / Z", "Treat +X / +Y / +Z as up"),
    ("Ctrl + Shift + X / Y / Z", "Treat -X / -Y / -Z as up"),
])}
</table>
<p class='note'>Preview and OBJ/GLB export use the same chosen basis.</p>

<h2>UV / texture debug</h2>
<table>
{rows([
    ("U", "Toggle UV channel for atlas meshes"),
    ("M", "Toggle UV domain / remap mode"),
    ("W", "Toggle texture wrap: auto / clamp / repeat"),
    ("T", "Toggle texture tint / neutral material"),
    ("B", "Cycle displayed texture: base / normal / emission / metal"),
    ("N", "Show normal/bump texture on UV0 for alignment debugging"),
])}
</table>

<h2>Lighting / helper view</h2>
<table>
{rows([
    ("L", "Toggle lit + bump / normal-map preview"),
    ("[ / ]", "Lower / raise bump height / strength"),
    ("G", "Flip normal-map green/Y channel"),
    ("F", "Toggle flat/helper view for navmesh/collision surfaces"),
])}
</table>

<h2>Group / assembly preview</h2>
<table>
{rows([
    ("P", "Toggle group debug palette / real child materials"),
    ("V", "Cycle hidden child in group/assembly preview"),
    ("Shift + V", "Show all group children and clear box visibility filters"),
    ("I", "Solo/isolate one child in group preview"),
    ("Shift + I", "Show all group children and clear box visibility filters"),
    ("O", "Toggle child origin/pivot markers"),
    ("Shift + O", "Toggle zero child-origin offsets debug mode"),
])}
</table>

<h2>Special previews</h2>
<table>
{rows([
    ("Camera", "CAD-style frustum / view volume"),
    ("Light", "Symbolic light influence shape"),
    ("ReflectionProbe", "Cubemap capture / blend volume"),
    ("LODGroup", "Level-of-detail thresholds / renderer cost"),
    ("ParticleSystem", "Symbolic emitter shape / particle cloud"),
    ("BoxCollider", "Scaled wireframe collider box"),
    ("Sphere/Capsule/MeshCollider", "Collision shape preview"),
    ("RectTransform", "Approximate UI layout rectangle"),
    ("Shader/Material", "Symbolic shader intent card"),
    ("SpriteMask", "Linked sprite mask shape"),
    ("Font", "Sample text card"),
    ("Avatar", "Symbolic rig mapping card"),
    ("Transform groups", "Renderable child assembly when possible"),
])}
</table>

<h2>Viewer</h2>
<table>
{rows([
    ("Space", "Play / pause the active AnimationClip"),
    ("` / ~ / F11", "Toggle preview focus"),
    ("Tab", "Toggle preview focus while 3D preview is active"),
    ("H", "Show this help"),
])}
</table>

<p class='note'>UBE is an inspector, not a full Unity runtime renderer. Some previews are intentionally symbolic or diagnostic.</p>
</body>
</html>
"""


def show_preview_help_dialog(parent=None):
    """Scrollable 3D preview help dialog shared by MainWindow and Preview3DWidget."""
    try:
        dlg = QDialog(parent)
        dlg.setWindowTitle("3D Preview Help")
        dlg.resize(760, 680)
        dlg.setMinimumSize(620, 480)

        layout = QVBoxLayout(dlg)
        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(False)
        browser.setHtml(preview_help_html())
        try:
            browser.setStyleSheet("QTextBrowser { background: #181a1f; border: 1px solid #343945; }")
        except Exception:
            pass

        buttons = QDialogButtonBox(QDialogButtonBox.Close, dlg)
        buttons.rejected.connect(dlg.reject)

        layout.addWidget(browser, 1)
        layout.addWidget(buttons)
        dlg.exec()
    except Exception:
        # Last-resort fallback in case QTextBrowser/QDialog fails in a minimal Qt build.
        QMessageBox.information(parent, "3D Preview Help", "3D Preview Help\\n\\nUse H for help, mouse to orbit/pan/zoom, and number keys 0-6 for preset views.")


if QOpenGLWidget is not None:

    class Preview3DWidget(QOpenGLWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(320)
            # Allow the 3D preview itself to receive keyboard shortcuts
            # after the user clicks in the viewer.
            try:
                self.setFocusPolicy(Qt.StrongFocus)
            except Exception:
                pass

            self.vertices: list[tuple[float, float, float]] = []
            self.normals: list[tuple[float, float, float]] = []
            self.uvs: list[tuple[float, float]] = []
            # face item = (vertex index, uv index or None, normal index or None)
            self.faces: list[tuple[tuple[int, int | None, int | None], tuple[int, int | None, int | None], tuple[int, int | None, int | None]]] = []
            # Optional per-face colour used by assembled GameObject/group previews.
            # Normal single-mesh previews leave this empty and use material/texture as before.
            self.face_colors: list[tuple[float, float, float]] = []
            # Group/assembly preview child visibility debugging.
            # face_child_indices maps each face to a renderable child part, so V can
            # hide one child at a time while arrowing through transforms/assemblies.
            self.face_child_indices: list[int] = []
            # Multi-select preview can combine a few independently selected
            # objects/meshes.  Unlike the older transform-group preview, this mode
            # keeps a per-face texture index so each selected object may keep its
            # own base texture where the exporter exposes one.
            self.face_texture_indices: list[int | None] = []
            self.multi_texture_images: list[dict[str, Any]] = []
            self.multi_texture_ids: list[int | None] = []
            self.group_child_names: list[str] = []
            self.group_hidden_child_index: int | None = None
            self.group_solo_child_index: int | None = None
            # v2.4e: viewport rectangle visibility filters.  Shift+left drag
            # isolates every render element touched by the box; Ctrl+left drag
            # cumulatively hides touched elements.  The selected child indices
            # are also mapped back to source animation items for Animated GLB.
            self.group_box_hidden_child_indices: set[int] = set()
            self.group_box_solo_child_indices: set[int] | None = None
            self.box_select_active = False
            self.box_select_mode = ""
            self.box_select_start = QPoint()
            self.box_select_end = QPoint()
            self.visibility_filter_changed_callback = None
            self.group_child_origins: list[tuple[float, float, float]] = []
            self.group_child_origin_labels: list[str] = []
            # v2.2: cached source vertices for lightweight Transform animation.
            # Group previews normally bake child matrices into one combined mesh.
            # Keeping each child's untransformed OBJ vertices lets the timeline
            # update only matrices in memory instead of re-exporting every frame.
            self.group_dynamic_parts: list[dict[str, Any]] = []
            self.frame_center_offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
            self.group_origin_markers_enabled = False
            # Debug mode for transform-only group preview. Some Unity bundles store
            # mesh vertices already in a shared/group coordinate space, while the
            # child Transform still carries an offset. Shift+O lets the user test
            # the hypothesis by temporarily ignoring each child origin translation
            # while preserving the child mesh shape/orientation.
            self.group_zero_origin_offsets_enabled = False
            self._last_group_preview_args: dict[str, Any] | None = None
            # Generic parent/group previews historically used a per-child debug
            # palette because it makes hierarchy and transform problems obvious.
            # P toggles a material-aware assembly that gives each child its own
            # exported base texture/material colour.  Remember the preference so
            # users inspecting scene assemblies do not need to re-toggle it for
            # every parent.
            try:
                stored_group_materials = QSettings("UBE", "UnityBundleExplorer").value(
                    "group_real_materials", False
                )
                if isinstance(stored_group_materials, bool):
                    self.group_real_materials_enabled = stored_group_materials
                else:
                    self.group_real_materials_enabled = str(stored_group_materials).strip().lower() in (
                        "1", "true", "yes", "on"
                    )
            except Exception:
                self.group_real_materials_enabled = False
            # LOD parent preview is material-aware: when a parent owns an LODGroup,
            # UBE previews one child LOD at a time using that child's own renderer
            # material/texture context.  This avoids the transform-group fallback
            # colouring LOD0/1/2 with debug palette colours.
            self._last_lod_preview_args: dict[str, Any] | None = None
            self.lod_child_records: list[Any] = []
            self.lod_child_names: list[str] = []
            self.lod_child_index: int = 0

            self.mesh_name = ""
            self.message = "Select a Mesh to preview"
            self.view_name = "Isometric"

            self.distance = 4.0
            self.mesh_max_dim = 1.0
            # The viewer is often used on VR/game-scene chunks where the user
            # wants to inspect very close-up details.  Keep the near clip dynamic
            # instead of a fixed 0.01 so close views do not slice the mesh.
            self.close_clip_enabled = True
            self.fov_degrees = 45.0
            self.rot_x = 25.0
            self.rot_y = -35.0
            self.rot_z = 0.0
            self.view_name = "Isometric"
            self.right_drag_axis = "z"
            self.pan_x = 0.0
            self.pan_y = 0.0

            self.last_pos = QPoint()
            self.has_gl = False

            # Start raw object/group previews with no baked model rotation.
            # Earlier builds defaulted to -90 / 180 to make some OBJ-style mesh previews
            # look convenient, but that can give a false first impression when debugging
            # Unity transforms and grouped scene assemblies.
            self.model_rot_x = 0.0
            self.model_rot_y = 0.0
            self.model_rot_z = 0.0
            # Ground/up-axis basis used by both preview and export.
            # This is deliberately a simple session setting, not saved in QSettings:
            # Unity files from different games/tools can arrive with different
            # authored up axes, so the user can quickly try +X/-X/+Y/-Y/+Z/-Z.
            self.ground_up_axis = "+Y"

            # Small camera-oriented XYZ triad in the lower-left corner.  It is
            # intentionally a screen overlay rather than scene geometry, so it
            # never changes model bounds, clipping, export, or selection.
            try:
                stored_axis = QSettings("UBE", "UnityBundleExplorer").value("preview_axis_indicator", True)
                if isinstance(stored_axis, bool):
                    self.axis_indicator_enabled = stored_axis
                else:
                    self.axis_indicator_enabled = str(stored_axis).strip().lower() not in ("0", "false", "no", "off", "")
            except Exception:
                self.axis_indicator_enabled = True

            self.material_color: tuple[float, float, float] | None = None
            # By default textured previews are not multiplied by Unity _BaseColor/_Color.
            # That tint is often right for simple URP materials, but Shader Graph atlases
            # such as GolfBallShader use colour properties for other purposes and the
            # old preview made every ball look red.  Press T to toggle tinting back on.
            self.texture_tint_enabled = False

            # Texture preview data is loaded while the temp export folder exists,
            # then uploaded to OpenGL on the next paintGL() call.
            self.texture_path: Path | None = None
            self.texture_bytes: bytes | None = None
            self.texture_width = 0
            self.texture_height = 0
            self.texture_id: int | None = None
            # Palette/swatch lookup textures must use exact texel sampling.
            # Linear filtering blends neighbouring colour cells and can turn a
            # block-colour asset into a washed, nearly uniform colour.
            self.palette_lookup_texture_enabled = False

            # Real lit+bump preview resources. The normal map is loaded
            # alongside the displayed/base texture so OpenGL can show the golf
            # balls much closer to the in-game material without exporting GLB.
            self.normal_texture_path: Path | None = None
            self.normal_texture_bytes: bytes | None = None
            self.normal_texture_width = 0
            self.normal_texture_height = 0
            self.normal_texture_id: int | None = None
            self.bump_uvs: list[tuple[float, float]] = []

            self.lit_bump_enabled = False
            self.bump_strength = 2.0
            self.normal_green_flip = False
            # Flat/helper preview is intentionally texture-free.  It is useful for
            # NavMesh/Collision/DoNotWarp helper meshes where the assigned material
            # may only be a debug/default shader ingredient and the shape matters more
            # than the sampled atlas texture.
            self.helper_preview_enabled = False
            self.bump_shader_program: int | None = None
            self.bump_shader_error = ""
            self._bump_shader_locations: dict[str, int] = {}

            # Debug texture source for atlas/material investigation.
            # base = normal preview texture from OBJ/MTL map_Kd, normal = bump/normal map
            # displayed as colour so the UV placement can be inspected without exporting.
            self.texture_source_mode = "base"
            self._last_preview_texture_label = "Base"

            # Preview UV-channel selector.  This is useful for Shader Graph / atlas
            # materials where UV1 can choose a tile while UV0 is the normal unwrap.
            self.uv_channel = 0
            self.uv_channels_available: list[int] = []
            # Manual UV-domain override for fringe shader cases.
            # Auto = normal behaviour plus known heuristics.  The manual modes
            # are useful when a shader remaps authored UVs before sampling.
            self.uv_domain_mode = "auto"
            # Preview texture sampler wrap mode.  Unity materials often rely on
            # texture repeat when UVs go outside 0..1, especially custom shaders
            # and compact 256px character textures.  The old preview forced
            # clamp-to-edge, which smeared edge pixels on such meshes.
            self.uv_wrap_mode = "auto"  # auto / clamp / repeat
            self._raw_uvs: list[tuple[float, float]] = []
            self._last_texture_path_for_uv_domain: Path | None = None
            self._last_uv_domain_effective = "raw"
            self._last_uv_domain_note = ""
            self._last_uv_wrap_effective = "clamp"
            self._last_uv_wrap_note = ""
            self._last_record = None
            self._last_bundle_index = None
            self._last_asset_graph = None
            self._last_export_mode = "mesh"
            self._last_source_context_label = ""

        # =====================================================
        # LOAD MESH
        # =====================================================
        def load_mesh_record(self, rec, bundle_index=None, asset_graph=None):
            self._load_record_via_export(rec, bundle_index, asset_graph, export_mode="mesh")

        def load_object_record(self, rec, bundle_index=None, asset_graph=None):
            """Preview an Object/component using its own renderer material slots.

            This is important because the same Mesh can be reused by many scene
            objects with different Materials or per-object texture choices.
            """
            self._load_record_via_export(rec, bundle_index, asset_graph, export_mode="object")

        def _load_record_via_export(self, rec, bundle_index=None, asset_graph=None, export_mode: str = "mesh"):
            self._last_record = rec
            self._last_bundle_index = bundle_index
            self._last_asset_graph = asset_graph
            self._last_export_mode = export_mode
            self.mesh_name = getattr(rec, "name", "Mesh")
            self.message = f"Loading {self.mesh_name}..."
            self.update()

            try:
                from ..exporters.mesh_exporter import export_mesh_record, export_object_record

                self._clear_texture()
                self.material_color = None

                with tempfile.TemporaryDirectory(prefix="ube_preview_") as tmp:
                    if export_mode == "object":
                        result = export_object_record(rec, tmp, bundle_index, asset_graph, uv_channel=self.uv_channel)
                    else:
                        result = export_mesh_record(rec, tmp, bundle_index, asset_graph, uv_channel=self.uv_channel)

                    if not getattr(result, "ok", False) or not getattr(result, "path", None):
                        self.vertices = []
                        self.normals = []
                        self.uvs = []
                        self.faces = []
                        self.material_color = None
                        self.message = f"Preview unavailable\n{getattr(result, 'message', 'Mesh export failed')}"
                        self.update()
                        return

                    obj_path = Path(result.path)
                    meta_path = Path(getattr(result, "json_path", "") or "")

                    self._load_obj(obj_path)
                    self._read_preview_uv_metadata(meta_path)
                    self.material_color = self._extract_material_color(rec, asset_graph, bundle_index)

                    base_texture_path = self._find_base_texture_path(
                        obj_path,
                        Path(getattr(result, "mtl_path", "") or "") if getattr(result, "mtl_path", None) else None,
                    )
                    texture_path = self._choose_preview_texture_path(meta_path, base_texture_path)
                    self._last_texture_path_for_uv_domain = texture_path
                    self._apply_uv_domain_mode(texture_path)
                    if texture_path is not None:
                        self._load_texture_image(texture_path)

                    # Keep the normal/bump texture and its UV0 coordinates loaded
                    # even when the visible/base texture is using UV1.  This is
                    # what the golf balls need: base atlas on UV1, normal dimples
                    # on UV0.
                    self._load_normal_texture_for_lit_preview(meta_path)
                    self._load_bump_uv0_for_lit_preview(rec, bundle_index, asset_graph, export_mode, tmp)

                self._frame_mesh()
                self.message = ""
                source_label = self._preview_texture_source_label()
                wrap_label = self._uv_wrap_status_short()
                context_label = getattr(self, "_last_source_context_label", "") or ""
                prefix_parts = []
                if self.uv_channels_available:
                    prefix_parts.append(f"UV{self.uv_channel}")
                prefix_parts.append(source_label)
                prefix_parts.append(wrap_label)
                if context_label:
                    prefix_parts.append(context_label)
                self.view_name = " | ".join(prefix_parts + [self.view_name])
                self.update()

            except Exception as e:
                self.vertices = []
                self.normals = []
                self.uvs = []
                self.faces = []
                self.face_colors = []
                self.face_child_indices = []
                self.group_child_names = []
                self.group_hidden_child_index = None
                self.group_solo_child_index = None
                self.group_box_hidden_child_indices = set()
                self.group_box_solo_child_indices = None
                self.group_child_origins = []
                self.group_child_origin_labels = []
                self.group_dynamic_parts = []
                self.material_color = None
                self._clear_texture()
                self.message = f"3D preview failed:\n{e}"
                self.update()

        def _read_preview_uv_metadata(self, json_path: Path | None) -> None:
            """Read export metadata so the viewer knows which UV channels exist."""
            self.uv_channels_available = []
            self._last_source_context_label = ""
            self.palette_lookup_texture_enabled = False
            if json_path is None or not str(json_path) or not json_path.exists():
                return
            try:
                import json
                meta = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
                source = meta.get("source_object") or {}
                ctx = source.get("context") or {}
                if ctx.get("mode") == "semantic_material":
                    mats = ", ".join(ctx.get("materials") or [])
                    self._last_source_context_label = f"Material context: {mats or source.get('name', '')}"
                elif source.get("name"):
                    self._last_source_context_label = f"Renderer context: {source.get('name')}"
                mesh_meta = meta.get("mesh") or {}
                self.palette_lookup_texture_enabled = bool(mesh_meta.get("palette_lookup_uv"))
                auto_uv = mesh_meta.get("uv_channel_auto_selected") or None
                if auto_uv:
                    try:
                        self.uv_channel = int(mesh_meta.get("uv_channel_exported", auto_uv.get("effective_channel", 0)) or 0)
                        reason = str(auto_uv.get("reason", "") or "")
                        if reason:
                            self._last_source_context_label = (
                                f"{self._last_source_context_label}; " if self._last_source_context_label else ""
                            ) + f"Auto UV{self.uv_channel}: recovered character colour"
                    except Exception:
                        pass
                channels = (mesh_meta.get("uv_channels") or {})
                found = []
                for name in channels.keys():
                    try:
                        if str(name).upper().startswith("UV"):
                            found.append(int(str(name)[2:]))
                    except Exception:
                        pass
                self.uv_channels_available = sorted(set(found))
            except Exception:
                self.uv_channels_available = []
                self.palette_lookup_texture_enabled = False

        def _palette_lookup_export_info(self, json_path: Path | None) -> dict:
            """Return palette lookup metadata for one temporary OBJ export."""
            if json_path is None or not str(json_path) or not json_path.exists():
                return {}
            try:
                import json
                meta = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
                mesh_meta = meta.get("mesh") or {}
                lookup = mesh_meta.get("palette_lookup_uv") or None
                if not lookup:
                    return {}
                return {
                    "active": True,
                    "channel": int(lookup.get("channel", 0) or 0),
                    "texture": str((mesh_meta.get("inferred_palette_texture") or {}).get("texture") or ""),
                }
            except Exception:
                return {}

        def _load_palette_sampling_image(self, texture_path: Path | None):
            """Load an RGBA image for exact nearest-texel palette sampling."""
            if texture_path is None:
                return None
            try:
                from PIL import Image
                with Image.open(texture_path) as src:
                    return src.convert("RGBA").copy()
            except Exception:
                return None

        def _sample_palette_face_colour(self, image, uvs, tri):
            """Sample a palette texture at a triangle's authored UV points.

            Palette meshes intentionally repeat one or two UV points across many
            vertices.  Sampling the exported PNG with nearest filtering avoids
            GPU linear filtering between adjacent swatch cells and preserves the
            saturated flat colours used by block-style games.
            """
            if image is None or not uvs or not tri:
                return None
            try:
                width, height = image.size
                pixels = image.load()
            except Exception:
                return None
            if width <= 0 or height <= 0:
                return None

            samples = []
            for _vi, ti, _ni in tri:
                if ti is None or ti < 0 or ti >= len(uvs):
                    continue
                try:
                    u, v = float(uvs[ti][0]), float(uvs[ti][1])
                    if not (math.isfinite(u) and math.isfinite(v)):
                        continue
                    # Palette lookup textures are clamp-sampled.  PIL rows are
                    # top-to-bottom, while Unity/OpenGL UV V=0 addresses bottom.
                    u = max(0.0, min(1.0, u))
                    v = max(0.0, min(1.0, v))
                    x = max(0, min(width - 1, int(round(u * (width - 1)))))
                    y = max(0, min(height - 1, int(round((1.0 - v) * (height - 1)))))
                    r, g, b, a = pixels[x, y]
                    if int(a) <= 0:
                        continue
                    samples.append((int(r), int(g), int(b)))
                except Exception:
                    continue
            if not samples:
                return None
            # Most palette triangles repeat exactly one texel.  Averaging only
            # matters for the rare face whose vertices deliberately use two
            # lookup points and remains closer to Unity's interpolation.
            count = float(len(samples))
            return (
                sum(row[0] for row in samples) / (255.0 * count),
                sum(row[1] for row in samples) / (255.0 * count),
                sum(row[2] for row in samples) / (255.0 * count),
            )

        def _preview_texture_source_label(self) -> str:
            labels = {
                "base": "Base texture",
                "normal": "Normal/bump texture",
                "emission": "Emission texture",
                "metal": "Metal/mask texture",
            }
            return labels.get(str(getattr(self, "texture_source_mode", "base") or "base"), "Base texture")

        def _texture_file_from_metadata(self, json_path: Path | None, mode: str) -> tuple[Path | None, str]:
            """Find an exported texture file from OBJ metadata for preview/debug.

            The normal map is deliberately displayed as plain colour here. That lets
            us test UV channel, V flip and domain modes in the UBE viewer even though
            the fixed-pipeline preview does not render real tangent-space bump mapping.
            """
            if json_path is None or not str(json_path) or not json_path.exists():
                return None, ""
            try:
                import json
                meta = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                return None, ""

            root = json_path.parent.parent
            rows = meta.get("textures") or []
            if not rows:
                return None, ""

            def path_for(row):
                fn = str(row.get("file") or "")
                if not fn:
                    return None
                p = Path(fn)
                if not p.is_absolute():
                    p = root / p
                return p if p.exists() else None

            def row_text(row) -> str:
                return " ".join([
                    str(row.get("usage", "") or ""),
                    str(row.get("name", "") or ""),
                    str(row.get("relation", "") or ""),
                ]).lower().replace("_", "")

            mode = str(mode or "base").lower()
            if mode == "normal":
                tokens = ("normal", "bump", "nrm")
            elif mode == "emission":
                tokens = ("emission", "emiss", "glow")
            elif mode == "metal":
                tokens = ("metal", "metalness", "mask", "smooth", "rough")
            else:
                tokens = ("base", "albedo", "diffuse", "color", "colour")

            for row in rows:
                usage = str(row.get("usage", "") or "").lower()
                if mode == "metal":
                    usage_match = usage in ("metal", "metalness", "mask", "smoothness")
                else:
                    usage_match = usage == mode
                if usage_match:
                    p = path_for(row)
                    if p is not None:
                        return p, str(row.get("name") or row.get("relation") or mode)

            for row in rows:
                txt = row_text(row)
                if any(tok in txt for tok in tokens):
                    p = path_for(row)
                    if p is not None:
                        return p, str(row.get("name") or row.get("relation") or mode)

            if mode == "base":
                p = path_for(rows[0])
                if p is not None:
                    return p, str(rows[0].get("name") or rows[0].get("relation") or "base")
            return None, ""

        def _choose_preview_texture_path(self, json_path: Path | None, base_texture_path: Path | None) -> Path | None:
            mode = str(getattr(self, "texture_source_mode", "base") or "base").lower()
            if mode == "base":
                self._last_preview_texture_label = "Base"
                return base_texture_path

            p, label = self._texture_file_from_metadata(json_path, mode)
            if p is not None:
                self._last_preview_texture_label = label or self._preview_texture_source_label()
                return p

            self._last_preview_texture_label = "Base fallback"
            return base_texture_path

        def _reload_current_preview(self) -> None:
            if self._last_record is not None:
                self._load_record_via_export(
                    self._last_record,
                    self._last_bundle_index,
                    self._last_asset_graph,
                    self._last_export_mode,
                )

        def toggle_texture_source_mode(self) -> str:
            """Cycle which exported texture is shown on the model."""
            modes = ["base", "normal", "emission", "metal"]
            cur = str(getattr(self, "texture_source_mode", "base") or "base").lower()
            try:
                idx = modes.index(cur)
            except ValueError:
                idx = 0
            self.texture_source_mode = modes[(idx + 1) % len(modes)]
            if self.texture_source_mode == "normal" and (not self.uv_channels_available or 0 in self.uv_channels_available):
                self.uv_channel = 0
            self._reload_current_preview()
            label = f"Texture source: {self._preview_texture_source_label()} | UV{self.uv_channel}"
            self.view_name = label
            self.update()
            return label

        def show_normal_texture_debug(self) -> str:
            """Jump directly to normal/bump texture on UV0 for golf-ball debugging."""
            self.texture_source_mode = "normal"
            if not self.uv_channels_available or 0 in self.uv_channels_available:
                self.uv_channel = 0
            self._reload_current_preview()
            label = f"Normal/bump debug: UV{self.uv_channel}; press U for UV set, M for flip/domain"
            self.view_name = label
            self.update()
            return label

        def toggle_uv_channel(self) -> str:
            """Cycle the preview/export UV channel without resetting the view.

            Changing UV channel requires re-exporting/reloading the preview mesh,
            but the geometry itself has not changed.  Preserve the user's current
            close-up zoom, pan, orbit, FOV and model rotation across that reload.
            """
            channels = self.uv_channels_available or [0, 1]
            try:
                current_pos = channels.index(int(self.uv_channel))
                next_channel = channels[(current_pos + 1) % len(channels)]
            except Exception:
                next_channel = 1 if int(self.uv_channel or 0) == 0 else 0

            view_state = self._snapshot_view_state()
            self.uv_channel = int(next_channel)
            if self._last_record is not None:
                self._load_record_via_export(
                    self._last_record,
                    self._last_bundle_index,
                    self._last_asset_graph,
                    self._last_export_mode,
                )
                if getattr(self, "vertices", None):
                    self._restore_view_state(view_state)
            label = f"UV channel: UV{self.uv_channel}"
            if self.uv_channels_available:
                label += f" ({', '.join('UV'+str(x) for x in self.uv_channels_available)} available)"
            self.view_name = label
            self.update()
            return label

        def toggle_texture_tint(self) -> str:
            """Toggle whether texture previews are multiplied by Unity material colour.

            Default is OFF because many Shader Graph atlas materials use _Color/_BaseColor
            for shader logic rather than a simple diffuse tint.  Non-textured materials
            still use their colour swatch as before.
            """
            self.texture_tint_enabled = not bool(getattr(self, "texture_tint_enabled", False))
            label = "Texture tint: ON" if self.texture_tint_enabled else "Texture tint: OFF"
            self.view_name = label
            self.update()
            return label


        def toggle_lit_bump_preview(self) -> str:
            """Toggle real OpenGL normal-map lighting for the current preview."""
            self.lit_bump_enabled = not bool(getattr(self, "lit_bump_enabled", False))
            if self.lit_bump_enabled:
                if str(getattr(self, "texture_source_mode", "base") or "base") != "base":
                    self.texture_source_mode = "base"
                    self._reload_current_preview()
                label = f"Lit+bump preview: ON | height {self.bump_strength:.2f} | G flip {'ON' if self.normal_green_flip else 'OFF'}"
            else:
                label = "Lit+bump preview: OFF"
            self.view_name = label
            self.update()
            return label

        def adjust_bump_strength(self, delta: float) -> str:
            try:
                self.bump_strength = float(getattr(self, "bump_strength", 2.0)) + float(delta)
            except Exception:
                self.bump_strength = 2.0
            self.bump_strength = max(0.0, min(self.bump_strength, 6.0))
            label = f"Normal height / bump strength: {self.bump_strength:.2f}"
            self.view_name = label
            self.update()
            return label

        def toggle_normal_green_flip(self) -> str:
            self.normal_green_flip = not bool(getattr(self, "normal_green_flip", False))
            label = "Normal green/Y flip: ON" if self.normal_green_flip else "Normal green/Y flip: OFF"
            self.view_name = label
            self.update()
            return label

        def toggle_helper_preview(self) -> str:
            """Toggle a texture-free flat shaded helper/collision preview.

            This is deliberately separate from material/texture preview.  Some
            course helper meshes use large shader atlases or noisy UVs as a
            secondary data source, while their practical meaning is the shape:
            navmesh, collision player surface, walkway blocker, DoNotWarp, etc.
            """
            self.helper_preview_enabled = not bool(getattr(self, "helper_preview_enabled", False))
            if self.helper_preview_enabled:
                # Avoid the lit bump shader taking over the draw path.
                self.lit_bump_enabled = False
                label = "Flat/helper preview: ON (texture ignored; shape + wireframe)"
            else:
                label = "Flat/helper preview: OFF"
            self.view_name = label
            self.update()
            return label

        # =====================================================
        # MULTI-SELECTION MATERIAL-AWARE PREVIEW
        # =====================================================
        def show_multi_selection_unavailable(self, detail: str = "") -> str:
            self._last_record = None
            self._last_export_mode = "multi_select"
            self.vertices = []
            self.normals = []
            self.uvs = []
            self.faces = []
            self.face_colors = []
            self.face_child_indices = []
            self.face_texture_indices = []
            self.group_child_names = []
            self.group_hidden_child_index = None
            self.group_solo_child_index = None
            self.group_box_hidden_child_indices = set()
            self.group_box_solo_child_indices = None
            self.group_child_origins = []
            self.group_child_origin_labels = []
            self.material_color = None
            self._clear_texture()
            suffix = f"\n{detail}" if detail else ""
            self.message = f"Multi-select preview unavailable\nNeed at least two renderable selections.{suffix}"
            self.update()
            return "Multi-select preview: unavailable"

        def load_multi_object_records(self, group_name: str, records: list[Any], bundle_index=None, asset_graph=None, max_records: int = 4):
            """Preview a few user-selected objects/meshes together.

            This is a lightweight comparison/fit-check tool.  It is not trying to
            become a Unity scene renderer; it simply exports each selected item
            through the same object/mesh preview path and merges the OBJ geometry
            without re-centering each part.  If the selected records share an
            authored origin, they should line up in the preview.
            """
            clean_records: list[Any] = []
            seen: set[int] = set()
            for rec in records or []:
                if rec is None:
                    continue
                pid = getattr(rec, "path_id", None)
                if pid in seen:
                    continue
                seen.add(pid)
                clean_records.append(rec)
                if len(clean_records) >= int(max_records or 4):
                    break

            if len(clean_records) < 2:
                self.message = "Multi-select preview needs two or more renderable records."
                self.update()
                return "Multi-select preview: select at least two objects"

            self._last_record = None
            self._last_bundle_index = bundle_index
            self._last_asset_graph = asset_graph
            self._last_export_mode = "multi_select"
            self._last_group_preview_args = None
            self._last_lod_preview_args = None
            self.mesh_name = str(group_name or "Multi selection")
            self.message = f"Loading multi-select preview: {self.mesh_name}..."
            self.update()

            try:
                from ..exporters.mesh_exporter import export_mesh_record, export_object_record

                self._clear_texture()
                self.material_color = None
                self.texture_source_mode = "base"
                self.uv_channels_available = []
                self.bump_uvs = []
                self.lit_bump_enabled = False
                self.helper_preview_enabled = False

                all_vertices: list[tuple[float, float, float]] = []
                all_normals: list[tuple[float, float, float]] = []
                all_uvs: list[tuple[float, float]] = []
                all_faces = []
                all_face_colours: list[tuple[float, float, float]] = []
                all_face_child_indices: list[int] = []
                all_face_texture_indices: list[int | None] = []
                self.group_child_names = []
                self.group_child_origins = []
                self.group_child_origin_labels = []
                self.group_dynamic_parts = []
                self.group_hidden_child_index = None
                self.group_solo_child_index = None
                self.group_box_hidden_child_indices = set()
                self.group_box_solo_child_indices = None
                self.group_origin_markers_enabled = False

                # Fallback colours are only used when a selected item has no exported
                # texture.  They keep separate parts readable without overriding real
                # texture previews.
                palette = [
                    (0.78, 0.86, 0.96),
                    (0.94, 0.78, 0.52),
                    (0.62, 0.84, 0.62),
                    (0.86, 0.66, 0.86),
                    (0.90, 0.72, 0.68),
                    (0.64, 0.82, 0.86),
                ]

                texture_index_by_key: dict[str, int] = {}
                skipped: list[str] = []
                exported_count = 0
                requested_uv = int(getattr(self, "uv_channel", 0) or 0)

                with tempfile.TemporaryDirectory(prefix="ube_multi_preview_") as tmp:
                    tmp_root = Path(tmp)
                    for idx, rec in enumerate(clean_records):
                        name = str(getattr(rec, "name", f"part_{idx}"))
                        part_dir = tmp_root / f"part_{idx:03d}"
                        part_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            if getattr(rec, "type_name", "") == "Mesh":
                                result = export_mesh_record(rec, part_dir, bundle_index, asset_graph, uv_channel=requested_uv)
                            else:
                                result = export_object_record(rec, part_dir, bundle_index, asset_graph, uv_channel=requested_uv)
                        except Exception as exc:
                            skipped.append(f"{name}: {exc}")
                            continue

                        if not getattr(result, "ok", False) or not getattr(result, "path", None):
                            skipped.append(f"{name}: {getattr(result, 'message', 'export skipped')}")
                            continue

                        obj_path = Path(result.path)
                        verts, norms, uvs, faces = self._parse_obj_file(obj_path)
                        if not verts or not faces:
                            skipped.append(f"{name}: no preview geometry")
                            continue

                        meta_path = Path(getattr(result, "json_path", "") or "")
                        mtl_path = Path(getattr(result, "mtl_path", "") or "") if getattr(result, "mtl_path", None) else None
                        base_texture_path = self._find_base_texture_path(obj_path, mtl_path)
                        texture_path = self._choose_preview_texture_path(meta_path, base_texture_path)
                        tex_index: int | None = None
                        if texture_path is not None:
                            try:
                                key = str(texture_path.resolve())
                            except Exception:
                                key = str(texture_path)
                            if key in texture_index_by_key:
                                tex_index = texture_index_by_key[key]
                            else:
                                data, tw, th = self._load_texture_bytes_from_image(texture_path)
                                if data and tw and th:
                                    tex_index = len(self.multi_texture_images)
                                    texture_index_by_key[key] = tex_index
                                    self.multi_texture_images.append({
                                        "path": texture_path,
                                        "bytes": data,
                                        "width": int(tw),
                                        "height": int(th),
                                    })
                                    self.multi_texture_ids.append(None)

                        colour = self._extract_material_color(rec, asset_graph, bundle_index)
                        if colour is None:
                            colour = palette[exported_count % len(palette)]

                        base_v = len(all_vertices)
                        base_n = len(all_normals)
                        base_t = len(all_uvs)
                        child_index = len(self.group_child_names)
                        self.group_child_names.append(name)
                        self.group_child_origins.append((0.0, 0.0, 0.0))
                        self.group_child_origin_labels.append("origin 0.000, 0.000, 0.000")
                        self.group_dynamic_parts.append({
                            "child_index": child_index,
                            "vertex_start": base_v,
                            "source_vertices": list(verts),
                            "transform_key": None,
                            "base_unity_matrix": None,
                            "unitypy_obj_basis": False,
                            "item_index": idx,
                            "instance_key": None,
                        })

                        all_vertices.extend(verts)
                        all_normals.extend(norms)
                        all_uvs.extend(uvs)
                        for tri in faces:
                            remapped = []
                            for vi, ti, ni in tri:
                                remapped.append((
                                    vi + base_v,
                                    ti + base_t if ti is not None else None,
                                    ni + base_n if ni is not None else None,
                                ))
                            all_faces.append(tuple(remapped))
                            all_face_colours.append(colour)
                            all_face_child_indices.append(child_index)
                            all_face_texture_indices.append(tex_index)
                        exported_count += 1

                if not all_vertices or not all_faces or exported_count < 2:
                    self.vertices = []
                    self.normals = []
                    self.uvs = []
                    self.faces = []
                    self.face_colors = []
                    self.face_child_indices = []
                    self.face_texture_indices = []
                    self.group_child_names = []
                    detail = "\n".join(skipped[:8])
                    self.message = f"Multi-select preview unavailable\nNeed at least two renderable selections.\n{detail}"
                    self.update()
                    return "Multi-select preview: unavailable"

                self.vertices = all_vertices
                self.normals = all_normals
                self.uvs = all_uvs
                self._raw_uvs = list(all_uvs)
                self.faces = all_faces
                self.face_colors = all_face_colours
                self.face_child_indices = all_face_child_indices
                self.face_texture_indices = all_face_texture_indices
                self.texture_id = None
                self.texture_bytes = None
                self.texture_path = None
                self.texture_width = 0
                self.texture_height = 0
                self.material_color = None
                self._frame_mesh()
                self.message = ""
                skipped_text = f", {len(skipped)} skipped" if skipped else ""
                tex_text = f", {len(self.multi_texture_images)} texture(s)" if self.multi_texture_images else ", material colours"
                self.view_name = f"Multi-select preview: {exported_count} object(s){tex_text}{skipped_text}"
                self.update()
                return self.view_name

            except Exception as exc:
                self.vertices = []
                self.normals = []
                self.uvs = []
                self.faces = []
                self.face_colors = []
                self.face_child_indices = []
                self.face_texture_indices = []
                self.group_child_names = []
                self.material_color = None
                self._clear_texture()
                self.message = f"Multi-select preview failed:\n{exc}"
                self.update()
                return "Multi-select preview: failed"

        # =====================================================
        # LODGROUP MATERIAL-AWARE PREVIEW
        # =====================================================
        def load_lod_child_records(self, group_name: str, items: list[dict], bundle_index=None, asset_graph=None, start_index: int = 0):
            """Preview an LODGroup parent by showing one LOD child at a time.

            A normal transform-group preview deliberately assigns palette colours
            per child so layout mistakes are easy to spot.  That is not ideal for
            LODGroup parents, because only one LOD is normally visible in Unity and
            each LOD child already has a real SkinnedMeshRenderer/MeshRenderer with
            material slots.  This mode keeps the useful I/Shift+I stepping workflow,
            but each step uses the selected child object's own material/texture path.
            """
            clean_items: list[dict] = []
            names: list[str] = []
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                rec = item.get("record")
                if rec is None:
                    continue
                name = str(item.get("name") or getattr(rec, "name", f"LOD{len(clean_items)}"))
                clean_items.append(dict(item, record=rec, name=name))
                names.append(name)

            if not clean_items:
                self.vertices = []
                self.faces = []
                self.message = "LOD preview unavailable\nNo renderable LOD child meshes were found."
                self.update()
                return

            try:
                index = max(0, min(int(start_index), len(clean_items) - 1))
            except Exception:
                index = 0

            self._last_lod_preview_args = {
                "group_name": group_name,
                "items": clean_items,
                "bundle_index": bundle_index,
                "asset_graph": asset_graph,
            }
            self.lod_child_records = [item.get("record") for item in clean_items]
            self.lod_child_names = names
            self.lod_child_index = index
            # Reuse the child-name list for user-facing debug text/hotkeys.
            self.group_child_names = list(names)
            self.group_hidden_child_index = None
            self.group_solo_child_index = index
            self.group_child_origins = []
            self.group_child_origin_labels = []
            self.group_origin_markers_enabled = False
            return self._load_lod_child_at(index)

        def _snapshot_view_state(self) -> dict[str, float | str | bool]:
            """Capture the user-controlled 3D camera/view state.

            Used by LOD stepping so pressing I can swap LOD0/LOD1/LOD2
            without losing the user's close-up zoom, pan and rotation.
            """
            state: dict[str, float | str | bool] = {}
            for name in (
                "distance", "rot_x", "rot_y", "rot_z",
                "pan_x", "pan_y", "fov_degrees",
                "model_rot_x", "model_rot_y", "model_rot_z",
            ):
                try:
                    state[name] = float(getattr(self, name))
                except Exception:
                    pass
            try:
                state["view_name"] = str(getattr(self, "view_name", "") or "")
            except Exception:
                pass
            try:
                state["close_clip_enabled"] = bool(getattr(self, "close_clip_enabled", True))
            except Exception:
                pass
            return state

        def _restore_view_state(self, state: dict[str, float | str | bool] | None) -> None:
            """Restore a view-state snapshot captured before a reload."""
            if not state:
                return
            for name in (
                "distance", "rot_x", "rot_y", "rot_z",
                "pan_x", "pan_y", "fov_degrees",
                "model_rot_x", "model_rot_y", "model_rot_z",
            ):
                if name in state:
                    try:
                        setattr(self, name, float(state[name]))
                    except Exception:
                        pass
            if "close_clip_enabled" in state:
                try:
                    self.close_clip_enabled = bool(state["close_clip_enabled"])
                except Exception:
                    pass

        def _load_lod_child_at(self, index: int, preserve_view: bool = False) -> str:
            args = getattr(self, "_last_lod_preview_args", None) or {}
            items = list(args.get("items") or [])
            if not items:
                return "LOD preview: no LOD child list"

            try:
                index = max(0, min(int(index), len(items) - 1))
            except Exception:
                index = 0

            item = items[index]
            rec = item.get("record")
            name = str(item.get("name") or getattr(rec, "name", f"LOD{index}"))
            bundle_index = args.get("bundle_index")
            asset_graph = args.get("asset_graph")
            group_name = str(args.get("group_name") or "LODGroup")

            if rec is None:
                self.message = f"LOD preview unavailable\n{name}: no object record"
                self.update()
                return f"LOD preview: {name} unavailable"

            # Let the normal object preview path do the hard work: Mesh/SkinnedMesh,
            # sibling renderer material slots, texture selection, UV remap, bump map,
            # and framing.  When stepping between LOD children, preserve the user's
            # current camera/orbit/pan/zoom so close-up comparisons do not reset.
            view_state = self._snapshot_view_state() if preserve_view else None
            self._load_record_via_export(rec, bundle_index, asset_graph, export_mode="object")
            if preserve_view and getattr(self, "vertices", None):
                self._restore_view_state(view_state)
            self._last_export_mode = "lod_children"
            self._last_lod_preview_args = args
            self.lod_child_index = index
            self.lod_child_records = [it.get("record") for it in items]
            self.lod_child_names = [str(it.get("name") or getattr(it.get("record"), "name", f"LOD{i}")) for i, it in enumerate(items)]
            self.group_child_names = list(self.lod_child_names)
            self.group_hidden_child_index = None
            self.group_solo_child_index = index

            prefix = f"LOD material preview: {index + 1}/{len(items)} {name}"
            # Faces are loaded by the normal object preview path above.  In UBE's
            # preview data model each face entry represents one rendered triangle,
            # so this is a useful educational LOD cost hint rather than a full
            # Unity profiler number.
            try:
                tri_count = len(getattr(self, "faces", None) or [])
            except Exception:
                tri_count = 0
            if tri_count > 0:
                prefix += f" | ~{tri_count:,} tris"
            else:
                prefix += " | tris unavailable"
            if group_name:
                prefix += f"  ({group_name})"
            try:
                if self.view_name:
                    self.view_name = f"{prefix} | {self.view_name}"
                else:
                    self.view_name = prefix
            except Exception:
                self.view_name = prefix
            self.update()
            return prefix

        # =====================================================
        # GROUP / ASSEMBLY PREVIEW
        # =====================================================
        def load_object_group_records(
            self,
            group_name: str,
            items: list[dict],
            bundle_index=None,
            asset_graph=None,
            uv_channel: int | None = None,
            preserve_view: bool = False,
            preserve_debug_state: bool = False,
            preview_mode: str = "group",
            selection_count: int | None = None,
            context_label: str = "",
            default_solo_child_index: int | None = None,
            variant_context_label: str = "",
            progress_callback=None,
        ):
            """Preview a transform-only GameObject as an assembled group.

            Each item is expected to contain:
                record: the child GameObject/component to export
                matrix: 4x4 local-to-group transform matrix
                name: display name

            This is intentionally a preview feature, not a final scene exporter yet.
            It answers the common Unity hierarchy question: "this parent has no mesh,
            but what do its visible children look like together?"
            """
            view_state = self._snapshot_view_state() if preserve_view else None
            debug_state = None
            if preserve_debug_state:
                debug_state = {
                    "hidden": getattr(self, "group_hidden_child_index", None),
                    "solo": getattr(self, "group_solo_child_index", None),
                    "box_hidden": set(getattr(self, "group_box_hidden_child_indices", set()) or set()),
                    "box_solo": (
                        set(getattr(self, "group_box_solo_child_indices", set()) or set())
                        if getattr(self, "group_box_solo_child_indices", None) is not None
                        else None
                    ),
                    "origins": bool(getattr(self, "group_origin_markers_enabled", False)),
                }

            self._last_record = None
            self._last_bundle_index = bundle_index
            self._last_asset_graph = asset_graph
            preview_mode = "multi_select" if str(preview_mode) == "multi_select" else "group"
            self._last_export_mode = preview_mode
            self._last_group_preview_args = {
                "group_name": group_name,
                "items": list(items or []),
                "bundle_index": bundle_index,
                "asset_graph": asset_graph,
                "uv_channel": uv_channel,
                "preview_mode": preview_mode,
                "selection_count": selection_count,
                "context_label": context_label,
                "default_solo_child_index": default_solo_child_index,
                "variant_context_label": variant_context_label,
            }
            self.mesh_name = str(group_name or ("Multi selection" if preview_mode == "multi_select" else "Group"))
            loading_label = "multi-select hierarchy" if preview_mode == "multi_select" else "group"
            self.message = f"Loading {loading_label} preview: {self.mesh_name}..."
            self.update()

            try:
                from ..exporters.mesh_exporter import export_object_record

                self._clear_texture()
                self.material_color = None
                self.texture_source_mode = "base"
                self.uv_channels_available = []
                self.bump_uvs = []
                self.face_colors = []
                self.face_child_indices = []
                self.group_child_names = []
                self.group_hidden_child_index = None
                self.group_solo_child_index = None
                self.group_box_hidden_child_indices = set()
                self.group_box_solo_child_indices = None
                self.group_child_origins = []
                self.group_child_origin_labels = []
                self.group_dynamic_parts = []
                self.group_solo_child_index = None
                self.group_child_origins = []
                self.group_child_origin_labels = []

                all_vertices: list[tuple[float, float, float]] = []
                all_normals: list[tuple[float, float, float]] = []
                all_uvs: list[tuple[float, float]] = []
                all_faces = []
                all_face_colours: list[tuple[float, float, float]] = []
                all_face_child_indices: list[int] = []
                all_face_texture_indices: list[int | None] = []

                real_materials = bool(getattr(self, "group_real_materials_enabled", False))
                texture_index_by_key: dict[str, int] = {}
                palette_image_by_key: dict[str, Any] = {}
                palette_flattened_parts = 0

                palette = [
                    (0.78, 0.86, 0.96),
                    (0.94, 0.78, 0.52),
                    (0.62, 0.84, 0.62),
                    (0.86, 0.66, 0.86),
                    (0.90, 0.72, 0.68),
                    (0.64, 0.82, 0.86),
                    (0.86, 0.84, 0.58),
                    (0.74, 0.74, 0.82),
                ]

                exported_count = 0
                skipped: list[str] = []
                requested_uv = int(uv_channel if uv_channel is not None else getattr(self, "uv_channel", 0) or 0)

                with tempfile.TemporaryDirectory(prefix="ube_group_preview_") as tmp:
                    tmp_root = Path(tmp)
                    total_items = len(items or [])
                    progress_step = max(1, total_items // 16) if total_items else 1
                    for idx, item in enumerate(items or []):
                        if progress_callback is not None and (
                            idx == 0 or (idx + 1) % progress_step == 0 or idx + 1 == total_items
                        ):
                            progress_callback(
                                f"Building preview geometry: {idx + 1:,}/{total_items:,} render instance(s)…"
                            )
                        rec = item.get("record") if isinstance(item, dict) else None
                        if rec is None:
                            continue
                        # Hierarchy matrices are calculated in Unity coordinates. UnityPy's
                        # OBJ exporter mirrors vertex X, so Unity matrices are converted into
                        # that same mirrored basis before being applied to exported OBJ data.
                        unity_matrix = item.get("matrix") if isinstance(item, dict) else None
                        matrix = unity_matrix
                        name = str(item.get("name") or getattr(rec, "name", f"part_{idx}")) if isinstance(item, dict) else getattr(rec, "name", f"part_{idx}")
                        part_dir = tmp_root / f"part_{idx:03d}"
                        part_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            result = export_object_record(rec, part_dir, bundle_index, asset_graph, uv_channel=requested_uv)
                        except Exception as exc:
                            skipped.append(f"{name}: {exc}")
                            continue
                        if not getattr(result, "ok", False) or not getattr(result, "path", None):
                            skipped.append(f"{name}: {getattr(result, 'message', 'export skipped')}")
                            continue

                        obj_path = Path(result.path)
                        verts, norms, uvs, faces = self._parse_obj_file(obj_path)
                        if not verts or not faces:
                            skipped.append(f"{name}: no preview geometry")
                            continue

                        # UnityPy exports OBJ positions as (-x, y, z). Applying a Unity
                        # matrix directly to already-mirrored vertices mixes coordinate bases.
                        # Convert only UnityPy OBJ output; UBE's manual fallback keeps raw
                        # Unity coordinates and therefore keeps the original Unity matrix.
                        unitypy_obj_basis = "unitypy export" in str(getattr(result, "message", "") or "").lower()
                        if unitypy_obj_basis:
                            matrix = self._unity_matrix_to_unitypy_obj_basis(matrix)

                        base_v = len(all_vertices)
                        base_n = len(all_normals)
                        base_t = len(all_uvs)
                        child_index = len(self.group_child_names)
                        self.group_child_names.append(name)
                        try:
                            origin = self._apply_matrix_point(matrix, (0.0, 0.0, 0.0))
                        except Exception:
                            origin = (0.0, 0.0, 0.0)
                        self.group_child_origins.append(origin)
                        origin_owner = str(item.get("selection_name") or name) if isinstance(item, dict) else name
                        self.group_child_origin_labels.append(f"{origin_owner}: origin {origin[0]:.3f}, {origin[1]:.3f}, {origin[2]:.3f}")
                        transform_key = item.get("transform_key") if isinstance(item, dict) else None
                        if transform_key is None and isinstance(item, dict):
                            transform_key = item.get("instance_key")
                        self.group_dynamic_parts.append({
                            "child_index": child_index,
                            "vertex_start": base_v,
                            "source_vertices": list(verts),
                            "transform_key": transform_key,
                            "base_unity_matrix": unity_matrix,
                            "unitypy_obj_basis": bool(unitypy_obj_basis),
                            "item_index": idx,
                            "instance_key": item.get("instance_key") if isinstance(item, dict) else None,
                        })
                        tex_index: int | None = None
                        if real_materials:
                            meta_path = Path(getattr(result, "json_path", "") or "")
                            mtl_path = (
                                Path(getattr(result, "mtl_path", "") or "")
                                if getattr(result, "mtl_path", None)
                                else None
                            )
                            base_texture_path = self._find_base_texture_path(obj_path, mtl_path)
                            texture_path = self._choose_preview_texture_path(meta_path, base_texture_path)
                            palette_info = self._palette_lookup_export_info(meta_path)
                            palette_image = None
                            if texture_path is not None:
                                try:
                                    texture_key = str(texture_path.resolve())
                                except Exception:
                                    texture_key = str(texture_path)
                                if palette_info.get("active"):
                                    if texture_key not in palette_image_by_key:
                                        palette_image_by_key[texture_key] = self._load_palette_sampling_image(texture_path)
                                    palette_image = palette_image_by_key.get(texture_key)
                                    if palette_image is not None:
                                        palette_flattened_parts += 1
                                if palette_image is None:
                                    if texture_key in texture_index_by_key:
                                        tex_index = texture_index_by_key[texture_key]
                                    else:
                                        data, tw, th = self._load_texture_bytes_from_image(texture_path)
                                        if data and tw and th:
                                            tex_index = len(self.multi_texture_images)
                                            texture_index_by_key[texture_key] = tex_index
                                            self.multi_texture_images.append({
                                                "path": texture_path,
                                                "bytes": data,
                                                "width": int(tw),
                                                "height": int(th),
                                                "nearest": bool(palette_info.get("active")),
                                            })
                                            self.multi_texture_ids.append(None)

                            colour = self._extract_material_color(rec, asset_graph, bundle_index)
                            if colour is None:
                                # Runtime-assigned/palette materials can serialize
                                # without a conventional _BaseColor.  White keeps
                                # the neutral lighting readable and avoids making
                                # a valid asset look like a missing-material grey.
                                colour = (1.0, 1.0, 1.0)
                        else:
                            palette_index = child_index
                            if isinstance(item, dict):
                                try:
                                    palette_index = int(item.get("selection_index", child_index))
                                except Exception:
                                    palette_index = child_index
                            colour = palette[palette_index % len(palette)]

                        zero_offsets = bool(getattr(self, "group_zero_origin_offsets_enabled", False))
                        for v in verts:
                            tv = self._apply_matrix_point(matrix, v)
                            if zero_offsets:
                                # Debug-only: collapse each child Transform origin to the
                                # selected group origin.  This helps identify whether a
                                # group assembly mismatch is caused by child origin offsets
                                # being applied when the mesh vertices are already authored
                                # in a common coordinate frame.
                                tv = (tv[0] - origin[0], tv[1] - origin[1], tv[2] - origin[2])
                            all_vertices.append(tv)
                        # For now normals are not transformed here because the normal draw path
                        # recomputes face normals.  Keep OBJ normals for future export/debug.
                        all_normals.extend(norms)
                        all_uvs.extend(uvs)
                        for tri in faces:
                            remapped = []
                            for vi, ti, ni in tri:
                                remapped.append((
                                    vi + base_v,
                                    ti + base_t if ti is not None else None,
                                    ni + base_n if ni is not None else None,
                                ))
                            face_colour = colour
                            face_tex_index = tex_index
                            if real_materials and palette_image is not None:
                                sampled_colour = self._sample_palette_face_colour(palette_image, uvs, tri)
                                if sampled_colour is not None:
                                    face_colour = sampled_colour
                                    face_tex_index = None
                            all_faces.append(tuple(remapped))
                            all_face_colours.append(face_colour)
                            all_face_child_indices.append(child_index)
                            all_face_texture_indices.append(face_tex_index)
                        exported_count += 1

                if not all_vertices or not all_faces:
                    self.vertices = []
                    self.normals = []
                    self.uvs = []
                    self.faces = []
                    self.face_colors = []
                    self.face_child_indices = []
                    self.face_texture_indices = []
                    self.group_child_names = []
                    self.group_hidden_child_index = None
                    self.group_solo_child_index = None
                    self.group_box_hidden_child_indices = set()
                    self.group_box_solo_child_indices = None
                    self.group_child_origins = []
                    self.group_child_origin_labels = []
                    self.group_dynamic_parts = []
                    detail = "\n".join(skipped[:6])
                    self.message = f"Group preview unavailable\nNo renderable child meshes exported.\n{detail}"
                    self.update()
                    return

                self.vertices = all_vertices
                self.normals = all_normals
                self.uvs = all_uvs
                self._raw_uvs = list(all_uvs)
                self.faces = all_faces
                self.face_colors = all_face_colours
                self.face_child_indices = all_face_child_indices
                self.face_texture_indices = all_face_texture_indices if real_materials else []
                self.group_hidden_child_index = None
                self.material_color = None
                self.texture_id = None
                self.texture_bytes = None
                self.texture_path = None
                self.texture_width = 0
                self.texture_height = 0
                self.lit_bump_enabled = False
                self.helper_preview_enabled = False

                self._frame_mesh()
                if debug_state:
                    try:
                        hidden = debug_state.get("hidden")
                        solo = debug_state.get("solo")
                        count = len(self.group_child_names)
                        self.group_hidden_child_index = (
                            int(hidden) if hidden is not None and 0 <= int(hidden) < count else None
                        )
                        self.group_solo_child_index = (
                            int(solo) if solo is not None and 0 <= int(solo) < count else None
                        )
                        box_hidden = debug_state.get("box_hidden") or set()
                        self.group_box_hidden_child_indices = {
                            int(index) for index in box_hidden
                            if 0 <= int(index) < count
                        }
                        box_solo = debug_state.get("box_solo")
                        self.group_box_solo_child_indices = (
                            {
                                int(index) for index in (box_solo or set())
                                if 0 <= int(index) < count
                            }
                            if box_solo is not None
                            else None
                        )
                        self.group_origin_markers_enabled = bool(debug_state.get("origins", False))
                    except Exception:
                        self.group_hidden_child_index = None
                        self.group_solo_child_index = None
                elif default_solo_child_index is not None:
                    try:
                        requested_solo = int(default_solo_child_index)
                        if 0 <= requested_solo < len(self.group_child_names):
                            self.group_solo_child_index = requested_solo
                            self.group_hidden_child_index = None
                    except Exception:
                        self.group_solo_child_index = None
                if preserve_view and getattr(self, "vertices", None):
                    self._restore_view_state(view_state)
                self.message = ""
                skipped_text = f", {len(skipped)} skipped" if skipped else ""
                zero_text = ", origin offsets zeroed" if bool(getattr(self, "group_zero_origin_offsets_enabled", False)) else ""
                basis_text = ", UnityPy OBJ-basis corrected"
                if real_materials:
                    palette_text = f", {palette_flattened_parts} palette part(s) sampled exactly" if palette_flattened_parts else ""
                    material_text = (
                        f", real materials ({len(self.multi_texture_images)} texture(s)){palette_text}"
                        if self.multi_texture_images
                        else f", real material colours{palette_text}"
                    )
                else:
                    material_text = ", debug palette"
                variant_text = f", {variant_context_label}" if str(variant_context_label or "").strip() else ""
                if preview_mode == "multi_select":
                    selected_total = int(selection_count or 0)
                    selected_text = f"{selected_total} selection(s), " if selected_total else ""
                    context_text = f", {context_label}" if context_label else ""
                    self.view_name = f"Multi-select hierarchy preview: {selected_text}{exported_count} render instance(s){material_text}{skipped_text}{zero_text}{basis_text}{context_text}{variant_text}"
                else:
                    self.view_name = f"Group preview: {exported_count} child mesh(es){material_text}{skipped_text}{zero_text}{basis_text}{variant_text}"
                self.update()

            except Exception as exc:
                self.vertices = []
                self.normals = []
                self.uvs = []
                self.faces = []
                self.face_colors = []
                self.face_child_indices = []
                self.face_texture_indices = []
                self.group_child_names = []
                self.group_hidden_child_index = None
                self.group_solo_child_index = None
                self.group_box_hidden_child_indices = set()
                self.group_box_solo_child_indices = None
                self.group_child_origins = []
                self.group_child_origin_labels = []
                self.material_color = None
                self._clear_texture()
                self.message = f"Group preview failed:\n{exc}"
                self.update()

        def apply_group_dynamic_matrices(self, matrix_by_key: dict[Any, Any], local_vertices_by_child: dict[int, list] | None = None) -> int:
            """Apply new Unity-space matrices to an already loaded group preview.

            v2.2 uses this for basic Transform AnimationClip playback.  Geometry
            and materials remain cached; only child vertices/origins are rebuilt.
            Returns the number of child render instances updated.
            """
            parts = list(getattr(self, "group_dynamic_parts", []) or [])
            if not parts or not getattr(self, "vertices", None):
                return 0
            updated = 0
            vertices = self.vertices
            center_x, center_y, center_z = getattr(self, "frame_center_offset", (0.0, 0.0, 0.0))
            origins = list(getattr(self, "group_child_origins", []) or [])
            zero_offsets = bool(getattr(self, "group_zero_origin_offsets_enabled", False))
            for part in parts:
                key = part.get("transform_key")
                unity_matrix = matrix_by_key.get(key, part.get("base_unity_matrix"))
                if unity_matrix is None:
                    continue
                matrix = (
                    self._unity_matrix_to_unitypy_obj_basis(unity_matrix)
                    if part.get("unitypy_obj_basis")
                    else unity_matrix
                )
                try:
                    origin = self._apply_matrix_point(matrix, (0.0, 0.0, 0.0))
                    child_index = int(part.get("child_index", -1))
                    if 0 <= child_index < len(origins):
                        origins[child_index] = (
                            -center_x if zero_offsets else origin[0] - center_x,
                            -center_y if zero_offsets else origin[1] - center_y,
                            -center_z if zero_offsets else origin[2] - center_z,
                        )
                    start = int(part.get("vertex_start", 0))
                    child_index = int(part.get("child_index", -1))
                    source_vertices = (
                        (local_vertices_by_child or {}).get(child_index)
                        or part.get("source_vertices")
                        or []
                    )
                    for offset, vertex in enumerate(source_vertices):
                        transformed = self._apply_matrix_point(matrix, vertex)
                        if zero_offsets:
                            transformed = (
                                transformed[0] - origin[0],
                                transformed[1] - origin[1],
                                transformed[2] - origin[2],
                            )
                        transformed = (
                            transformed[0] - center_x,
                            transformed[1] - center_y,
                            transformed[2] - center_z,
                        )
                        target_index = start + offset
                        if 0 <= target_index < len(vertices):
                            vertices[target_index] = transformed
                    updated += 1
                except Exception:
                    continue
            self.group_child_origins = origins
            self.update()
            return updated

        def group_geometry_center(self, child_index: int | None = None):
            """Return the displayed bounds centre for a render part or whole group."""
            vertices = list(getattr(self, "vertices", []) or [])
            if not vertices:
                return None
            selected = vertices
            if child_index is not None:
                for part in list(getattr(self, "group_dynamic_parts", []) or []):
                    try:
                        if int(part.get("child_index", -1)) != int(child_index):
                            continue
                        start = int(part.get("vertex_start", 0))
                        count = len(part.get("source_vertices") or [])
                        if count > 0:
                            selected = vertices[start:start + count]
                        break
                    except Exception:
                        continue
            if not selected:
                return None
            try:
                xs = [float(v[0]) for v in selected]
                ys = [float(v[1]) for v in selected]
                zs = [float(v[2]) for v in selected]
                return (
                    (min(xs) + max(xs)) * 0.5,
                    (min(ys) + max(ys)) * 0.5,
                    (min(zs) + max(zs)) * 0.5,
                )
            except Exception:
                return None

        def lock_group_geometry_center(self, target_center, child_index: int | None = None) -> bool:
            """Translate the final displayed group so its anchor stays at target_center.

            This is intentionally a final-vertex operation.  It cannot be bypassed
            by hidden Unity parents, duplicated controller branches, skinning
            cancellation or coordinate-basis conversion.
            """
            current = self.group_geometry_center(child_index)
            if current is None or target_center is None:
                return False
            try:
                dx = float(target_center[0]) - float(current[0])
                dy = float(target_center[1]) - float(current[1])
                dz = float(target_center[2]) - float(current[2])
            except Exception:
                return False
            if abs(dx) + abs(dy) + abs(dz) <= 1.0e-12:
                return True
            try:
                self.vertices = [
                    (float(x) + dx, float(y) + dy, float(z) + dz)
                    for x, y, z in (getattr(self, "vertices", []) or [])
                ]
                origins = list(getattr(self, "group_child_origins", []) or [])
                if origins:
                    self.group_child_origins = [
                        (float(x) + dx, float(y) + dy, float(z) + dz)
                        for x, y, z in origins
                    ]
                self.update()
                return True
            except Exception:
                return False

        def reframe_current_group_pose(self, reset_distance: bool = True) -> bool:
            """Re-centre an already deformed/animated group around its current pose.

            Dynamic animation matrices are expressed in the same absolute preview
            space used when the group was first loaded.  Reframing therefore needs
            to update ``frame_center_offset`` by the *delta* between the old and
            current bounds centres, rather than replacing it with the centre of
            the already-centred vertex array.
            """
            vertices = list(getattr(self, "vertices", []) or [])
            if not vertices:
                return False
            try:
                xs = [float(v[0]) for v in vertices]
                ys = [float(v[1]) for v in vertices]
                zs = [float(v[2]) for v in vertices]
                dx = (min(xs) + max(xs)) * 0.5
                dy = (min(ys) + max(ys)) * 0.5
                dz = (min(zs) + max(zs)) * 0.5
                old_x, old_y, old_z = getattr(self, "frame_center_offset", (0.0, 0.0, 0.0))
                self.frame_center_offset = (old_x + dx, old_y + dy, old_z + dz)
                self.vertices = [(x - dx, y - dy, z - dz) for x, y, z in vertices]
                origins = list(getattr(self, "group_child_origins", []) or [])
                if origins:
                    self.group_child_origins = [(x - dx, y - dy, z - dz) for x, y, z in origins]

                xs = [v[0] for v in self.vertices]
                ys = [v[1] for v in self.vertices]
                zs = [v[2] for v in self.vertices]
                max_dim = max(
                    max(xs) - min(xs),
                    max(ys) - min(ys),
                    max(zs) - min(zs),
                )
                self.mesh_max_dim = max(0.001, float(max_dim))
                if reset_distance:
                    self.distance = max(0.1, self.mesh_max_dim * 1.8)
                    self.pan_x = 0.0
                    self.pan_y = 0.0
                self.update()
                return True
            except Exception:
                return False

        def toggle_group_material_mode(self) -> str:
            """Toggle generic group previews between debug colours and materials.

            The transform assembly is rebuilt because material-aware mode needs a
            separate texture assignment for every exported child.  Preserve the
            camera and group debugging state so P behaves as a visual comparison,
            not as a fresh preview selection.
            """
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select"):
                return "Group appearance: available on assembled parent/group previews"

            self.group_real_materials_enabled = not bool(
                getattr(self, "group_real_materials_enabled", False)
            )
            try:
                QSettings("UBE", "UnityBundleExplorer").setValue(
                    "group_real_materials", bool(self.group_real_materials_enabled)
                )
            except Exception:
                pass

            args = getattr(self, "_last_group_preview_args", None)
            if isinstance(args, dict) and args.get("items"):
                self.load_object_group_records(
                    args.get("group_name", self.mesh_name),
                    args.get("items") or [],
                    args.get("bundle_index"),
                    args.get("asset_graph"),
                    uv_channel=args.get("uv_channel"),
                    preserve_view=True,
                    preserve_debug_state=True,
                    preview_mode=args.get("preview_mode", "group"),
                    selection_count=args.get("selection_count"),
                    context_label=args.get("context_label", ""),
                    default_solo_child_index=args.get("default_solo_child_index"),
                    variant_context_label=args.get("variant_context_label", ""),
                )

            label = (
                "Group appearance: REAL MATERIALS"
                if self.group_real_materials_enabled
                else "Group appearance: DEBUG PALETTE"
            )
            try:
                detail = str(getattr(self, "view_name", "") or "")
                self.view_name = f"{detail} | {label}" if detail and label not in detail else label
            except Exception:
                self.view_name = label
            self.update()
            return label

        @staticmethod
        def _unity_matrix_to_unitypy_obj_basis(matrix):
            """Convert a Unity-space 4x4 matrix for UnityPy's mirrored-X OBJ basis.

            UnityPy's MeshExporter writes OBJ vertices/normals as (-x, y, z).
            For an exported point p_obj = C p_unity, the equivalent matrix is
            M_obj = C M_unity C^-1.  Since C is its own inverse, this is C M C.
            """
            if matrix is None:
                return None
            try:
                signs = (-1.0, 1.0, 1.0, 1.0)
                return [
                    [signs[r] * float(matrix[r][c]) * signs[c] for c in range(4)]
                    for r in range(4)
                ]
            except Exception:
                return matrix

        @staticmethod
        def _apply_matrix_point(matrix, point):
            """Apply a 4x4 row-major matrix to a point tuple."""
            try:
                x, y, z = float(point[0]), float(point[1]), float(point[2])
                m = matrix or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
                return (
                    m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
                    m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
                    m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
                )
            except Exception:
                return point

        def _group_child_is_visible(self, child_index: int) -> bool:
            """Return whether an assembled child should be drawn under visibility filters."""
            try:
                child_index = int(child_index)
            except Exception:
                return True

            box_solo = getattr(self, "group_box_solo_child_indices", None)
            if box_solo is not None and child_index not in box_solo:
                return False
            box_hidden = set(getattr(self, "group_box_hidden_child_indices", set()) or set())
            if child_index in box_hidden:
                return False

            solo = getattr(self, "group_solo_child_index", None)
            if solo is not None:
                return child_index == int(solo)
            hidden = getattr(self, "group_hidden_child_index", None)
            if hidden is not None:
                return child_index != int(hidden)
            return True

        def _group_visibility_filter_active(self) -> bool:
            return bool(
                getattr(self, "group_solo_child_index", None) is not None
                or getattr(self, "group_hidden_child_index", None) is not None
                or getattr(self, "group_box_solo_child_indices", None) is not None
                or bool(getattr(self, "group_box_hidden_child_indices", set()) or set())
            )

        def _clear_group_box_visibility_filters(self) -> None:
            self.group_box_hidden_child_indices = set()
            self.group_box_solo_child_indices = None

        def _notify_visibility_filter_changed(self, label: str) -> None:
            callback = getattr(self, "visibility_filter_changed_callback", None)
            if callable(callback):
                try:
                    callback(str(label or ""))
                except Exception:
                    pass

        def _group_face_is_visible(self, face_index: int) -> bool:
            """Return whether a face should be drawn under group child visibility filters."""
            child_indices = getattr(self, "face_child_indices", None) or []
            if face_index < 0 or face_index >= len(child_indices):
                return True
            return self._group_child_is_visible(int(child_indices[face_index]))

        def visible_group_item_indices(self) -> set[int] | None:
            """Return source item indices visible under I/V and viewport-box filters.

            ``None`` means no group visibility filtering is active.  The mapping
            comes from ``group_dynamic_parts`` because preview child indices only
            cover parts that successfully produced geometry, while ``item_index``
            points back to the original hierarchy/animation render-item list.
            """
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select"):
                return None
            parts = list(getattr(self, "group_dynamic_parts", []) or [])
            if not parts or not self._group_visibility_filter_active():
                return None

            visible_items: set[int] = set()
            for part in parts:
                try:
                    child_index = int(part.get("child_index", -1))
                    item_index = int(part.get("item_index", -1))
                except Exception:
                    continue
                if child_index < 0 or item_index < 0:
                    continue
                if self._group_child_is_visible(child_index):
                    visible_items.add(item_index)
            return visible_items

        def cycle_group_hidden_child(self, reset: bool = False) -> str:
            """Hide one assembled child at a time for transform/debug comparison.

            V cycles: hide child 1, hide child 2, ... then show all.
            Shift+V resets to all visible.  This is preview-only and is aimed at
            transform-only group previews where one child may be visibly offset.
            """
            names = list(getattr(self, "group_child_names", []) or [])
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select") or not names:
                return "Group child visibility: no assembled child list for this preview"

            # Hide mode and solo/box modes are mutually exclusive.
            self.group_solo_child_index = None
            self._clear_group_box_visibility_filters()

            if reset:
                self.group_hidden_child_index = None
                label = f"Group children: all visible ({len(names)} parts)"
            else:
                current = getattr(self, "group_hidden_child_index", None)
                if current is None:
                    next_index = 0
                else:
                    next_index = int(current) + 1
                if next_index >= len(names):
                    self.group_hidden_child_index = None
                    label = f"Group children: all visible ({len(names)} parts)"
                else:
                    self.group_hidden_child_index = next_index
                    child_name = names[next_index]
                    label = f"Group child hidden: {next_index + 1}/{len(names)}  {child_name}"

            self.view_name = label
            self._notify_visibility_filter_changed(label)
            self.update()
            return label

        def cycle_group_solo_child(self, reset: bool = False) -> str:
            """Show only one assembled child at a time for transform debugging.

            I cycles: only child 1, only child 2, ... then all visible.
            Shift+I resets to all visible.  This is useful when two parts look
            mismatched inside a group but look correct when inspected separately.

            For LODGroup parents, I cycles the real LOD children using their own
            material/texture context instead of the group debug palette.
            """
            if getattr(self, "_last_export_mode", "") == "lod_children":
                names = list(getattr(self, "lod_child_names", []) or [])
                if not names:
                    return "LOD preview: no LOD child list"
                if reset:
                    next_index = 0
                else:
                    try:
                        next_index = int(getattr(self, "lod_child_index", 0)) + 1
                    except Exception:
                        next_index = 0
                    if next_index >= len(names):
                        next_index = 0
                return self._load_lod_child_at(next_index, preserve_view=True)

            names = list(getattr(self, "group_child_names", []) or [])
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select") or not names:
                return "Group solo child: no assembled child list for this preview"

            # Solo mode and hide/box modes are mutually exclusive.
            self.group_hidden_child_index = None
            self._clear_group_box_visibility_filters()

            if reset:
                self.group_solo_child_index = None
                label = f"Group children: all visible ({len(names)} parts)"
            else:
                current = getattr(self, "group_solo_child_index", None)
                if current is None:
                    next_index = 0
                else:
                    next_index = int(current) + 1
                if next_index >= len(names):
                    self.group_solo_child_index = None
                    label = f"Group children: all visible ({len(names)} parts)"
                else:
                    self.group_solo_child_index = next_index
                    child_name = names[next_index]
                    origin_labels = list(getattr(self, "group_child_origin_labels", []) or [])
                    origin = f"  ({origin_labels[next_index]})" if next_index < len(origin_labels) else ""
                    label = f"Group child solo: {next_index + 1}/{len(names)}  {child_name}{origin}"

            self.view_name = label
            self._notify_visibility_filter_changed(label)
            self.update()
            return label

        def toggle_group_origin_markers(self) -> str:
            """Toggle origin/pivot markers for assembled group children."""
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select") or not getattr(self, "group_child_names", None):
                return "Group origins: no assembled child list for this preview"
            self.group_origin_markers_enabled = not bool(getattr(self, "group_origin_markers_enabled", False))
            label = "Group child origins: ON" if self.group_origin_markers_enabled else "Group child origins: OFF"
            self.view_name = label
            self.update()
            return label

        def toggle_group_origin_offset_mode(self) -> str:
            """Toggle debug mode that ignores child origin translations in group preview.

            This is not meant to be a final Unity scene interpretation.  It is a
            diagnostic view for prefab/common-bundle groups where child meshes may
            already contain their authored offsets and the Transform origins look
            like they double-place the parts.
            """
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select") or not getattr(self, "group_child_names", None):
                return "Group origin offset mode: no assembled child list for this preview"
            self.group_zero_origin_offsets_enabled = not bool(getattr(self, "group_zero_origin_offsets_enabled", False))
            label = (
                "Group origin offsets: ZEROED / child origins collapsed to group origin"
                if self.group_zero_origin_offsets_enabled
                else "Group origin offsets: APPLIED / Unity transform mode"
            )
            args = getattr(self, "_last_group_preview_args", None)
            if isinstance(args, dict) and args.get("items"):
                try:
                    self.load_object_group_records(
                        args.get("group_name", self.mesh_name),
                        args.get("items") or [],
                        args.get("bundle_index"),
                        args.get("asset_graph"),
                        uv_channel=args.get("uv_channel"),
                        preserve_view=True,
                        preserve_debug_state=True,
                        preview_mode=args.get("preview_mode", "group"),
                        selection_count=args.get("selection_count"),
                        context_label=args.get("context_label", ""),
                        default_solo_child_index=args.get("default_solo_child_index"),
                        variant_context_label=args.get("variant_context_label", ""),
                    )
                except Exception:
                    self.update()
            self.view_name = label
            self.update()
            return label

        # =====================================================
        # MATERIAL / TEXTURE EXTRACTION
        # =====================================================
        # =====================================================
        # MATERIAL / TEXTURE EXTRACTION
        # =====================================================
        def _extract_material_color(self, rec, asset_graph=None, bundle_index=None):
            """Return material _BaseColor/_Color when available. Many Unity materials
            are white here and rely on the base texture instead.
            """
            colour = self._material_color_from_record(rec)
            if colour is not None:
                return colour

            if asset_graph is None or bundle_index is None:
                return None

            for mat_rec in self._material_records_for_mesh(rec, asset_graph, bundle_index):
                colour = self._material_color_from_record(mat_rec)
                if colour is not None:
                    return colour

            return None

        def _material_records_for_mesh(self, rec, asset_graph, bundle_index):
            # Direct Mesh -> Material relationships.
            yield from self._material_records_from_references(rec, asset_graph, bundle_index)

            # Fallback: Mesh <- Renderer/Object, then Renderer/Object -> Material.
            try:
                used_by = asset_graph.used_by(rec, bundle_index)
            except Exception:
                used_by = []

            for rel in used_by or []:
                source_rec = self._record_from_relationship(rel, bundle_index, side="source")
                if source_rec is None:
                    continue
                yield from self._material_records_from_references(source_rec, asset_graph, bundle_index)

        def _material_records_from_references(self, rec, asset_graph, bundle_index):
            try:
                refs = asset_graph.references(rec, bundle_index)
            except Exception:
                refs = []

            seen = set()
            for rel in refs or []:
                if getattr(rel, "target_type", "") != "Material":
                    continue
                mat_rec = self._record_from_relationship(rel, bundle_index, side="target")
                if mat_rec is None:
                    continue
                pid = getattr(mat_rec, "path_id", None)
                if pid in seen:
                    continue
                seen.add(pid)
                yield mat_rec

        def _record_from_relationship(self, rel, bundle_index, side: str):
            records = {}
            records.update(getattr(bundle_index, "record_by_path_id", {}) or {})
            records.update(getattr(bundle_index, "external_record_by_path_id", {}) or {})

            for attr in (f"{side}_record", f"{side}_asset", side):
                obj = getattr(rel, attr, None)
                if obj is not None and hasattr(obj, "object"):
                    return obj

            for attr in (
                f"{side}_path_id",
                f"{side}_pathid",
                f"{side}_id",
                f"{side}_PathID",
                f"{side}_pathID",
            ):
                pid = getattr(rel, attr, None)
                if pid is None:
                    continue
                try:
                    found = records.get(int(pid))
                except Exception:
                    found = records.get(pid)
                if found is not None:
                    return found

            type_name = getattr(rel, f"{side}_type", None)
            name = getattr(rel, f"{side}_name", None)
            if type_name and name:
                for candidate in records.values():
                    if getattr(candidate, "type_name", None) == type_name and getattr(candidate, "name", None) == name:
                        return candidate
            return None

        def _material_color_from_record(self, mat_rec):
            if getattr(mat_rec, "type_name", None) != "Material":
                return None

            try:
                data = mat_rec.object.read()
            except Exception:
                return None

            props = self._get_any(data, "m_SavedProperties", "saved_properties")
            if props is None:
                return None

            colors = self._get_any(props, "m_Colors", "colors")
            if not colors:
                return None

            found: dict[str, tuple[float, float, float]] = {}
            for item in colors:
                key, value = self._pair_key_value(item)
                key_text = self._clean_key(key)
                if key_text not in ("_BaseColor", "_Color", "_Tint", "_TintColor", "_MainColor", "_ColorOverride", "_Color1"):
                    continue
                rgb = self._rgb_from_value(value)
                if rgb is not None:
                    found[key_text] = rgb

            # Explicit overrides win only when the material enables them.  The
            # remaining order mirrors common Unity diffuse/tint conventions.
            use_override = False
            try:
                floats = self._get_any(props, "m_Floats", "floats") or []
                for item in floats:
                    key, value = self._pair_key_value(item)
                    if self._clean_key(key) in ("_UseColorOverride", "_UseColourOverride"):
                        try:
                            use_override = float(value) > 0.5
                        except Exception:
                            use_override = False
                        break
            except Exception:
                pass
            if use_override and found.get("_ColorOverride") is not None:
                return found.get("_ColorOverride")
            return (
                found.get("_BaseColor")
                or found.get("_Color")
                or found.get("_Tint")
                or found.get("_TintColor")
                or found.get("_MainColor")
                or found.get("_Color1")
            )

        def _find_base_texture_path(self, obj_path: Path, mtl_path: Path | None = None) -> Path | None:
            """Find the base texture from the temporary OBJ/MTL export.
            The exporter creates these files in the temp preview folder, so the
            image must be read before the temp folder closes.
            """
            mtl_paths: list[Path] = []
            if mtl_path is not None and str(mtl_path):
                mtl_paths.append(mtl_path)

            try:
                for line in obj_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.lower().startswith("mtllib "):
                        name = line.split(None, 1)[1].strip()
                        mtl_paths.append((obj_path.parent / name).resolve())
            except Exception:
                pass

            mtl_paths.append(obj_path.with_suffix(".mtl"))

            seen = set()
            for candidate in mtl_paths:
                try:
                    candidate = candidate.resolve()
                except Exception:
                    pass
                if candidate in seen or not candidate.exists():
                    continue
                seen.add(candidate)

                try:
                    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.lower().startswith("map_kd "):
                            tex_name = line.split(None, 1)[1].strip().strip('"')
                            tex_path = (candidate.parent / tex_name).resolve()
                            if tex_path.exists():
                                return tex_path
                except Exception:
                    continue

            return None

        def _load_texture_bytes_from_image(self, tex_path: Path) -> tuple[bytes | None, int, int]:
            try:
                from PIL import Image

                img = Image.open(tex_path).convert("RGBA")
                # OpenGL expects the first row as the bottom row. Keep this
                # convention for both base and normal maps so the preview matches
                # the GLB V-direction work we already debugged.
                try:
                    img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                except Exception:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                w, h = img.size
                return img.tobytes(), int(w), int(h)
            except Exception:
                return None, 0, 0

        def _load_texture_image(self, tex_path: Path) -> None:
            data, w, h = self._load_texture_bytes_from_image(tex_path)
            if data:
                self.texture_path = tex_path
                self.texture_bytes = data
                self.texture_width = w
                self.texture_height = h
                self.texture_id = None
            else:
                self.texture_path = None
                self.texture_bytes = None
                self.texture_width = 0
                self.texture_height = 0
                self.texture_id = None

        def _load_normal_texture_image(self, tex_path: Path | None) -> None:
            if tex_path is None:
                self.normal_texture_path = None
                self.normal_texture_bytes = None
                self.normal_texture_width = 0
                self.normal_texture_height = 0
                self.normal_texture_id = None
                return
            data, w, h = self._load_texture_bytes_from_image(tex_path)
            if data:
                self.normal_texture_path = tex_path
                self.normal_texture_bytes = data
                self.normal_texture_width = w
                self.normal_texture_height = h
                self.normal_texture_id = None
            else:
                self.normal_texture_path = None
                self.normal_texture_bytes = None
                self.normal_texture_width = 0
                self.normal_texture_height = 0
                self.normal_texture_id = None

        def _load_normal_texture_for_lit_preview(self, meta_path: Path | None) -> None:
            p, _label = self._texture_file_from_metadata(meta_path, "normal")
            self._load_normal_texture_image(p)

        def _load_obj_uvs_only(self, path: Path) -> list[tuple[float, float]]:
            uvs: list[tuple[float, float]] = []
            try:
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("vt "):
                        parts = line.split()
                        if len(parts) >= 3:
                            uvs.append((float(parts[1]), float(parts[2])))
            except Exception:
                return []
            return uvs

        def _load_bump_uv0_for_lit_preview(self, rec, bundle_index, asset_graph, export_mode: str, tmp_root: str) -> None:
            """Load the UV0 vt list that should be used by the normal map."""
            self.bump_uvs = []
            try:
                from ..exporters.mesh_exporter import export_mesh_record, export_object_record

                if int(getattr(self, "uv_channel", 0) or 0) == 0:
                    self.bump_uvs = list(self.uvs or [])
                    return

                uv0_dir = Path(tmp_root) / "_normal_uv0_preview"
                uv0_dir.mkdir(parents=True, exist_ok=True)
                if export_mode == "object":
                    result = export_object_record(rec, uv0_dir, bundle_index, asset_graph, uv_channel=0)
                else:
                    result = export_mesh_record(rec, uv0_dir, bundle_index, asset_graph, uv_channel=0)
                if getattr(result, "ok", False) and getattr(result, "path", None):
                    self.bump_uvs = self._load_obj_uvs_only(Path(result.path))
            except Exception:
                self.bump_uvs = []

        @staticmethod
        def _get_any(obj: Any, *names: str):
            for name in names:
                if hasattr(obj, name):
                    try:
                        return getattr(obj, name)
                    except Exception:
                        pass
            if isinstance(obj, dict):
                for name in names:
                    if name in obj:
                        return obj[name]
            return None

        @staticmethod
        def _pair_key_value(item: Any):
            if item is None:
                return None, None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                return item[0], item[1]
            for a, b in (("key", "value"), ("first", "second"), ("Key", "Value"), ("m_Key", "m_Value")):
                if hasattr(item, a) and hasattr(item, b):
                    try:
                        return getattr(item, a), getattr(item, b)
                    except Exception:
                        pass
            if isinstance(item, dict):
                for a, b in (("key", "value"), ("first", "second"), ("Key", "Value"), ("m_Key", "m_Value")):
                    if a in item and b in item:
                        return item[a], item[b]
            return None, None

        @staticmethod
        def _clean_key(value: Any) -> str:
            if value is None:
                return ""
            return str(value).strip().strip("'").strip('"')

        def _rgb_from_value(self, value: Any):
            r = self._get_any(value, "r", "R", "x", "X")
            g = self._get_any(value, "g", "G", "y", "Y")
            b = self._get_any(value, "b", "B", "z", "Z")
            if r is not None and g is not None and b is not None:
                try:
                    return (float(r), float(g), float(b))
                except Exception:
                    return None
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                try:
                    return (float(value[0]), float(value[1]), float(value[2]))
                except Exception:
                    return None
            return None

        # =====================================================
        # QUICK VIEW ORIENTATION
        # =====================================================
        def set_standard_view(self, view_name: str) -> None:
            """Set a quick camera orientation for the current mesh preview.

            These are deliberately camera/view rotations, not changes to the
            exported mesh data.  The fixed model orientation remains underneath,
            so the shortcuts are relative to the same preview basis as mouse orbit.
            """
            key = str(view_name or "").strip().lower()

            views = {
                # User-facing number order: 1 Top, 2 Bottom, 3 Front,
                # 4 Back, 5 Left, 6 Right.  0 resets to the normal isometric view.
                "iso": (25.0, -35.0, 0.0, "Isometric"),
                "isometric": (25.0, -35.0, 0.0, "Isometric"),
                "reset": (25.0, -35.0, 0.0, "Isometric"),
                "top": (90.0, 0.0, 0.0, "Top"),
                "bottom": (-90.0, 0.0, 0.0, "Bottom"),
                "front": (0.0, 0.0, 0.0, "Front"),
                "back": (0.0, 180.0, 0.0, "Back"),
                "left": (0.0, -90.0, 0.0, "Left"),
                "right": (0.0, 90.0, 0.0, "Right"),
            }

            if key not in views:
                return

            self.rot_x, self.rot_y, self.rot_z, self.view_name = views[key]
            self.pan_x = 0.0
            self.pan_y = 0.0
            self.update()

        @staticmethod
        def _ground_axis_rotation(axis: str) -> tuple[float, float, float, str]:
            """Return model-rotation Euler angles for a simple authored-up axis.

            The chosen local/authored axis is rotated so it becomes viewer/export +Y.
            This is a coarse but very useful Unity/GLB/OBJ basis helper:
              +Y = Unity default
              +Z/-Z = common forward/up confusion
              +X/-X = imported/CAD-style side-up data
            """
            key = str(axis or "+Y").strip().upper().replace(" ", "")
            aliases = {
                "X": "+X", "+X": "+X", "POSX": "+X",
                "-X": "-X", "NEGX": "-X",
                "Y": "+Y", "+Y": "+Y", "POSY": "+Y",
                "-Y": "-Y", "NEGY": "-Y",
                "Z": "+Z", "+Z": "+Z", "POSZ": "+Z",
                "-Z": "-Z", "NEGZ": "-Z",
            }
            key = aliases.get(key, "+Y")
            mapping = {
                "+Y": (0.0, 0.0, 0.0, "+Y up / Unity default"),
                "-Y": (180.0, 0.0, 0.0, "-Y up"),
                "+Z": (-90.0, 0.0, 0.0, "+Z up"),
                "-Z": (90.0, 0.0, 0.0, "-Z up"),
                "+X": (0.0, 0.0, 90.0, "+X up"),
                "-X": (0.0, 0.0, -90.0, "-X up"),
            }
            return mapping.get(key, mapping["+Y"])

        def set_ground_up_axis(self, axis: str) -> str:
            """Set the model basis so the selected authored axis is treated as up.

            This changes the initial preview basis and is also read by export so
            OBJ/GLB output can match the current display orientation.
            """
            rx, ry, rz, label = self._ground_axis_rotation(axis)
            self.ground_up_axis = str(axis or "+Y").strip().upper().replace(" ", "")
            if self.ground_up_axis in ("X", "Y", "Z"):
                self.ground_up_axis = "+" + self.ground_up_axis
            if self.ground_up_axis not in ("+X", "-X", "+Y", "-Y", "+Z", "-Z"):
                self.ground_up_axis = "+Y"
            self.model_rot_x = rx
            self.model_rot_y = ry
            self.model_rot_z = rz
            self.view_name = f"Ground/up axis: {label}"
            self.update()
            return f"Ground/up axis: {label}"

        def get_ground_up_axis(self) -> str:
            axis = str(getattr(self, "ground_up_axis", "+Y") or "+Y").upper()
            return axis if axis in ("+X", "-X", "+Y", "-Y", "+Z", "-Z") else "+Y"


        def set_right_drag_axis(self, axis: str) -> str:
            """Choose which view axis the right mouse button rotates.

            Left mouse remains normal orbit. Right mouse is for corrective
            single-axis rotation/roll when a Unity object comes in at an
            awkward orientation.
            """
            axis = str(axis or "").strip().lower()
            if axis not in ("x", "y", "z"):
                axis = "z"
            self.right_drag_axis = axis
            self.view_name = f"Right drag: {axis.upper()} axis"
            self.update()
            return self.view_name

        def rotate_view_axis(self, axis: str, degrees: float, snap: bool = False) -> str:
            axis = str(axis or "").strip().lower()
            try:
                degrees = float(degrees)
            except Exception:
                degrees = 0.0

            if axis == "x":
                self.rot_x += degrees
                if snap:
                    self.rot_x = self._snap_angle(self.rot_x)
            elif axis == "y":
                self.rot_y += degrees
                if snap:
                    self.rot_y = self._snap_angle(self.rot_y)
            else:
                axis = "z"
                self.rot_z += degrees
                if snap:
                    self.rot_z = self._snap_angle(self.rot_z)

            self.view_name = f"View rotation: X {self.rot_x:.0f}°, Y {self.rot_y:.0f}°, Z {self.rot_z:.0f}°"
            self.update()
            return self.view_name

        @staticmethod
        def _snap_angle(value: float, step: float = 15.0) -> float:
            try:
                return round(float(value) / step) * step
            except Exception:
                return value

        def show_help_popup(self):
            show_preview_help_dialog(self)

        def toggle_axis_indicator(self) -> str:
            """Show or hide the lower-left camera-orientation triad."""
            self.axis_indicator_enabled = not bool(getattr(self, "axis_indicator_enabled", True))
            try:
                QSettings("UBE", "UnityBundleExplorer").setValue(
                    "preview_axis_indicator", bool(self.axis_indicator_enabled)
                )
            except Exception:
                pass
            label = "XYZ axis indicator: ON" if self.axis_indicator_enabled else "XYZ axis indicator: OFF"
            self.view_name = label
            self.update()
            return label

        @staticmethod
        def _rotate_axis_for_view(vector, rot_x: float, rot_y: float, rot_z: float):
            """Apply the same view rotation order used by paintGL to one axis vector."""
            x, y, z = (float(vector[0]), float(vector[1]), float(vector[2]))

            # OpenGL receives Rx, then Ry, then Rz.  With column vectors that
            # means the vector itself is evaluated Rz -> Ry -> Rx.
            rz = math.radians(float(rot_z))
            cz, sz = math.cos(rz), math.sin(rz)
            x, y = (cz * x - sz * y, sz * x + cz * y)

            ry = math.radians(float(rot_y))
            cy, sy = math.cos(ry), math.sin(ry)
            x, z = (cy * x + sy * z, -sy * x + cy * z)

            rx = math.radians(float(rot_x))
            cx, sx = math.cos(rx), math.sin(rx)
            y, z = (cx * y - sx * z, sx * y + cx * z)
            return (x, y, z)

        def _paint_axis_indicator(self) -> None:
            """Paint a compact RGB XYZ orientation indicator over the 3D view."""
            if not bool(getattr(self, "axis_indicator_enabled", True)):
                return
            try:
                from PySide6.QtCore import QPointF, QLineF
                from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

                height = max(1, int(self.height()))
                origin = QPointF(46.0, max(34.0, float(height) - 43.0))
                axis_length = 34.0

                axes = [
                    ("X", (1.0, 0.0, 0.0), QColor(245, 76, 86)),
                    ("Y", (0.0, 1.0, 0.0), QColor(74, 225, 92)),
                    ("Z", (0.0, 0.0, 1.0), QColor(74, 155, 255)),
                ]
                projected = []
                for label, vector, color in axes:
                    # Include both the selected authored/ground basis and the
                    # current camera orientation so the labels match the geometry
                    # seen after Ctrl+X/Y/Z basis changes as well as views 0-6.
                    model_vector = self._rotate_axis_for_view(
                        vector,
                        float(getattr(self, "model_rot_x", 0.0)),
                        float(getattr(self, "model_rot_y", 0.0)),
                        float(getattr(self, "model_rot_z", 0.0)),
                    )
                    vx, vy, vz = self._rotate_axis_for_view(
                        model_vector,
                        float(getattr(self, "rot_x", 0.0)),
                        float(getattr(self, "rot_y", 0.0)),
                        float(getattr(self, "rot_z", 0.0)),
                    )
                    projected.append((vz, label, vx, -vy, color))

                # Draw farther-facing axes first so the nearer ones remain clear.
                projected.sort(key=lambda item: item[0])

                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                font = QFont(painter.font())
                font.setPixelSize(12)
                font.setBold(True)
                painter.setFont(font)

                fallback_offsets = {
                    "X": QPointF(10.0, 8.0),
                    "Y": QPointF(-4.0, -11.0),
                    "Z": QPointF(-14.0, 8.0),
                }

                for _depth, label, px, py, color in projected:
                    screen_len = math.sqrt(px * px + py * py)
                    pen = QPen(color)
                    pen.setWidthF(2.2)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(pen)
                    painter.setBrush(QBrush(color))

                    if screen_len < 0.13:
                        # Axis is pointing almost directly into/out of the screen.
                        # A small ring/dot still identifies it without inventing a
                        # misleading sideways direction.
                        radius = 3.8
                        painter.drawEllipse(origin, radius, radius)
                        label_pos = origin + fallback_offsets[label]
                        painter.drawText(label_pos, label)
                        continue

                    dx = axis_length * px
                    dy = axis_length * py
                    end = QPointF(origin.x() + dx, origin.y() + dy)
                    painter.drawLine(QLineF(origin, end))

                    ux, uy = dx / math.sqrt(dx * dx + dy * dy), dy / math.sqrt(dx * dx + dy * dy)
                    perp_x, perp_y = -uy, ux
                    back = 6.5
                    wing = 3.2
                    arrow_a = QPointF(
                        end.x() - back * ux + wing * perp_x,
                        end.y() - back * uy + wing * perp_y,
                    )
                    arrow_b = QPointF(
                        end.x() - back * ux - wing * perp_x,
                        end.y() - back * uy - wing * perp_y,
                    )
                    painter.drawLine(QLineF(end, arrow_a))
                    painter.drawLine(QLineF(end, arrow_b))

                    label_pos = QPointF(end.x() + 7.0 * ux - 3.0, end.y() + 7.0 * uy + 4.0)
                    painter.drawText(label_pos, label)

                painter.setPen(QPen(QColor(235, 235, 235), 1.0))
                painter.setBrush(QBrush(QColor(235, 235, 235)))
                painter.drawEllipse(origin, 2.3, 2.3)
                painter.end()
            except Exception:
                pass

        def keyPressEvent(self, event):
            # Allow quick view control when the viewer has focus.
            # MainWindow also installs shortcuts so the same keys work even
            # when the asset tree still has focus.
            try:
                key = event.key()
            except Exception:
                return super().keyPressEvent(event)

            mapping = {
                Qt.Key_0: "isometric",
                Qt.Key_1: "top",
                Qt.Key_2: "bottom",
                Qt.Key_3: "front",
                Qt.Key_4: "back",
                Qt.Key_5: "left",
                Qt.Key_6: "right",
            }
            view = mapping.get(key)
            if view:
                self.set_standard_view(view)
                event.accept()
                return

            axis_mapping = {
                Qt.Key_X: "x",
                Qt.Key_Y: "y",
                Qt.Key_Z: "z",
            }
            axis = axis_mapping.get(key)

            try:
                mods = event.modifiers()
            except Exception:
                mods = Qt.NoModifier
            if axis and (mods & Qt.ControlModifier) and hasattr(self, "set_ground_up_axis"):
                sign = "-" if (mods & Qt.ShiftModifier) else "+"
                label = self.set_ground_up_axis(sign + axis.upper())
                event.accept()
                return

            if axis:
                self.set_right_drag_axis(axis)
                event.accept()
                return

            if key == Qt.Key_Q:
                self.rotate_view_axis("z", -15.0, snap=True)
                event.accept()
                return
            if key == Qt.Key_E:
                self.rotate_view_axis("z", 15.0, snap=True)
                event.accept()
                return

            if key == Qt.Key_A and mods == Qt.NoModifier:
                self.toggle_axis_indicator()
                event.accept()
                return

            if key == Qt.Key_U:
                self.toggle_uv_channel()
                event.accept()
                return

            if key == Qt.Key_M:
                self.toggle_uv_domain_mode()
                event.accept()
                return

            if key == Qt.Key_W:
                self.toggle_uv_wrap_mode()
                event.accept()
                return

            if key == Qt.Key_T:
                self.toggle_texture_tint()
                event.accept()
                return

            if key == Qt.Key_P:
                self.toggle_group_material_mode()
                event.accept()
                return

            if key == Qt.Key_F:
                self.toggle_helper_preview()
                event.accept()
                return

            if key == Qt.Key_B:
                self.toggle_texture_source_mode()
                event.accept()
                return

            if key == Qt.Key_N:
                self.show_normal_texture_debug()
                event.accept()
                return

            if key == Qt.Key_L:
                self.toggle_lit_bump_preview()
                event.accept()
                return

            if key == Qt.Key_G:
                self.toggle_normal_green_flip()
                event.accept()
                return

            if key == Qt.Key_BracketLeft:
                self.adjust_bump_strength(-0.25)
                event.accept()
                return

            if key == Qt.Key_BracketRight:
                self.adjust_bump_strength(0.25)
                event.accept()
                return

            if key == Qt.Key_V:
                reset = False
                try:
                    reset = bool(event.modifiers() & Qt.ShiftModifier)
                except Exception:
                    reset = False
                self.cycle_group_hidden_child(reset=reset)
                event.accept()
                return

            if key == Qt.Key_I:
                reset = False
                try:
                    reset = bool(event.modifiers() & Qt.ShiftModifier)
                except Exception:
                    reset = False
                self.cycle_group_solo_child(reset=reset)
                event.accept()
                return

            if key == Qt.Key_O:
                shifted = False
                try:
                    shifted = bool(event.modifiers() & Qt.ShiftModifier)
                except Exception:
                    shifted = False
                if shifted:
                    self.toggle_group_origin_offset_mode()
                else:
                    self.toggle_group_origin_markers()
                event.accept()
                return

            if key == Qt.Key_H:
                self.show_help_popup()
                event.accept()
                return

            if key == Qt.Key_C:
                self.close_clip_enabled = not bool(getattr(self, "close_clip_enabled", True))
                self.view_name = "Close clip: ON" if self.close_clip_enabled else "Close clip: OFF"
                self.update()
                event.accept()
                return

            return super().keyPressEvent(event)

        # =====================================================
        # CLEAR
        # =====================================================
        def clear_preview(self, text="Select a Mesh to preview"):
            self.vertices = []
            self.frame_center_offset = (0.0, 0.0, 0.0)
            self.normals = []
            self.uvs = []
            self.faces = []
            self.face_colors = []
            self.face_child_indices = []
            self.group_child_names = []
            self.group_hidden_child_index = None
            self.group_solo_child_index = None
            self.group_box_hidden_child_indices = set()
            self.group_box_solo_child_indices = None
            self.group_dynamic_parts = []
            self.material_color = None
            self._clear_texture()
            self.bump_uvs = []
            self.uv_channels_available = []
            self._raw_uvs = []
            self._last_texture_path_for_uv_domain = None
            self.message = text
            self.update()

        # =====================================================
        # OBJ LOADER
        # =====================================================
        def _load_obj(self, path: Path):
            verts, norms, uvs, faces = self._parse_obj_file(path)
            self.vertices = verts
            self.normals = norms
            self.uvs = uvs
            self._raw_uvs = list(uvs)
            self.faces = faces
            self.face_colors = []
            self.face_child_indices = []
            self.group_child_names = []
            self.group_hidden_child_index = None
            self.group_solo_child_index = None
            self.group_box_hidden_child_indices = set()
            self.group_box_solo_child_indices = None
            self.group_dynamic_parts = []

        def _parse_obj_file(self, path: Path):
            verts: list[tuple[float, float, float]] = []
            norms: list[tuple[float, float, float]] = []
            uvs: list[tuple[float, float]] = []
            faces = []

            def parse_index(text: str, count: int):
                if not text:
                    return None
                try:
                    idx = int(text)
                except Exception:
                    return None
                if idx > 0:
                    return idx - 1
                if idx < 0:
                    return count + idx
                return None

            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                return verts, norms, uvs, faces

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("v "):
                    p = line.split()
                    if len(p) >= 4:
                        try:
                            verts.append((float(p[1]), float(p[2]), float(p[3])))
                        except Exception:
                            pass

                elif line.startswith("vt "):
                    p = line.split()
                    if len(p) >= 3:
                        try:
                            uvs.append((float(p[1]), float(p[2])))
                        except Exception:
                            pass

                elif line.startswith("vn "):
                    p = line.split()
                    if len(p) >= 4:
                        try:
                            norms.append((float(p[1]), float(p[2]), float(p[3])))
                        except Exception:
                            pass

                elif line.startswith("f "):
                    poly = []
                    for part in line.split()[1:]:
                        bits = part.split("/")
                        vi = parse_index(bits[0], len(verts)) if len(bits) >= 1 else None
                        ti = parse_index(bits[1], len(uvs)) if len(bits) >= 2 else None
                        ni = parse_index(bits[2], len(norms)) if len(bits) >= 3 else None
                        if vi is not None and 0 <= vi < len(verts):
                            poly.append((vi, ti, ni))

                    if len(poly) >= 3:
                        for i in range(1, len(poly) - 1):
                            faces.append((poly[0], poly[i], poly[i + 1]))

            return verts, norms, uvs, faces

        def _uv_bounds_for_loaded_obj(self):
            if not self.uvs:
                return None
            try:
                us = [float(u) for u, _ in self.uvs]
                vs = [float(v) for _, v in self.uvs]
                return {
                    "u_min": min(us), "u_max": max(us),
                    "v_min": min(vs), "v_max": max(vs),
                    "u_span": max(us) - min(us),
                    "v_span": max(vs) - min(vs),
                }
            except Exception:
                return None

        def _looks_like_avatar_putter_texture(self, texture_path: Path | None) -> bool:
            if texture_path is None:
                return False
            name = str(texture_path.name or "").lower()
            return (
                "avatar_texture" in name
                or "brian_putters" in name
                or "putter" in name
            )

        def _uv_bounds_for_values(self, values):
            if not values:
                return None
            try:
                us = [float(u) for u, _ in values]
                vs = [float(v) for _, v in values]
                return {
                    "u_min": min(us),
                    "u_max": max(us),
                    "v_min": min(vs),
                    "v_max": max(vs),
                    "u_span": max(us) - min(us),
                    "v_span": max(vs) - min(vs),
                }
            except Exception:
                return None

        def _auto_uv_domain_mode_for_current_mesh(self, texture_path: Path | None) -> str:
            """Return the effective mode to use when self.uv_domain_mode == auto.

            Some Unity shaders do not feed the texture sampler with OBJ-style 0..1
            UVs.  A common avatar/putter pattern stores coordinates in a -1..+1
            domain and the shader remaps them to 0..1 before sampling the atlas.
            If UBE previews those raw values directly the atlas is smeared/repeated
            over the mesh.  Auto mode recognises that domain and remaps it for the
            preview only.
            """
            # Only auto-remap the visible/base texture.  Normal/metal/emission
            # debug views are often deliberately using a different UV domain.
            if str(getattr(self, "texture_source_mode", "base") or "base").lower() != "base":
                return "raw"

            b = self._uv_bounds_for_values(self._raw_uvs or self.uvs)
            if not b:
                return "raw"
            try:
                u_min, u_max = float(b["u_min"]), float(b["u_max"])
                v_min, v_max = float(b["v_min"]), float(b["v_max"])
                u_span, v_span = float(b["u_span"]), float(b["v_span"])
            except Exception:
                return "raw"

            near_signed_unit_domain = (
                u_min <= -0.70 and v_min <= -0.70
                and 0.70 <= u_max <= 1.15 and 0.70 <= v_max <= 1.15
                and 1.60 <= u_span <= 2.30 and 1.60 <= v_span <= 2.30
            )
            if not near_signed_unit_domain:
                return "raw"

            # Strong signal: known avatar/putter atlas names.
            if self._looks_like_avatar_putter_texture(texture_path):
                return "remap"

            # Fallback signal: a large texture with -1..+1 UVs is very likely a
            # shader-domain atlas/remap rather than a deliberate repeating tile.
            try:
                if int(getattr(self, "texture_width", 0) or 0) >= 1024 and int(getattr(self, "texture_height", 0) or 0) >= 1024:
                    return "remap"
            except Exception:
                pass

            return "raw"

        def _transform_uv_domain(self, uv_values, mode: str):
            if mode == "remap":
                return [(float(u) * 0.5 + 0.5, float(v) * 0.5 + 0.5) for u, v in uv_values]
            if mode == "flipv":
                return [(float(u), 1.0 - float(v)) for u, v in uv_values]
            if mode == "remap_flipv":
                return [(float(u) * 0.5 + 0.5, 1.0 - (float(v) * 0.5 + 0.5)) for u, v in uv_values]
            return list(uv_values)

        def _apply_uv_domain_mode(self, texture_path: Path | None = None):
            """Apply manual/auto UV-domain remapping to the preview UV list.

            This is intentionally preview-only.  It lets us test shader-style UV
            remaps quickly without damaging the raw mesh data.
            """
            if not self._raw_uvs:
                return
            mode = str(getattr(self, "uv_domain_mode", "auto") or "auto")
            effective = self._auto_uv_domain_mode_for_current_mesh(texture_path) if mode == "auto" else mode
            self._last_uv_domain_effective = effective
            self._last_uv_domain_note = ""
            self.uvs = self._transform_uv_domain(self._raw_uvs, effective)
            if effective != "raw":
                label = {
                    "remap": "UV remap -1..+1→0..1",
                    "flipv": "UV flip V",
                    "remap_flipv": "UV remap + flip V",
                }.get(effective, effective)
                self._last_uv_domain_note = label
                self.view_name = f"{label} | " + str(getattr(self, "view_name", "") or "3D Preview")

        def _maybe_apply_preview_uv_domain_fix(self, texture_path: Path | None):
            # Kept for older call sites; new code uses _apply_uv_domain_mode().
            self._last_texture_path_for_uv_domain = texture_path
            self._apply_uv_domain_mode(texture_path)

        def toggle_uv_domain_mode(self) -> str:
            modes = ["auto", "raw", "remap", "flipv", "remap_flipv"]
            labels = {
                "auto": "Auto",
                "raw": "Raw UV",
                "remap": "-1..+1 → 0..1",
                "flipv": "Flip V",
                "remap_flipv": "-1..+1 → 0..1 + Flip V",
            }
            cur = str(getattr(self, "uv_domain_mode", "auto") or "auto")
            try:
                idx = modes.index(cur)
            except ValueError:
                idx = 0
            self.uv_domain_mode = modes[(idx + 1) % len(modes)]
            self._apply_uv_domain_mode(getattr(self, "_last_texture_path_for_uv_domain", None))
            label = f"UV mode: {labels.get(self.uv_domain_mode, self.uv_domain_mode)}"
            self.view_name = label
            self.update()
            return label

        def _auto_uv_wrap_mode_for_current_mesh(self) -> str:
            """Guess whether texture sampling should clamp or repeat.

            Unity Texture import settings/default samplers commonly repeat when UVs
            go outside 0..1.  The preview used to force clamp-to-edge, which makes
            stretched edge-colour smears on meshes such as Angry Birds boss pigs.
            We inspect the *effective* UVs after any M-key domain remap.
            """
            vals = list(getattr(self, "uvs", []) or [])
            if not vals:
                return "clamp"
            b = self._uv_bounds_for_values(vals)
            if not b:
                return "clamp"
            try:
                u_min, u_max = float(b["u_min"]), float(b["u_max"])
                v_min, v_max = float(b["v_min"]), float(b["v_max"])
                u_span, v_span = float(b["u_span"]), float(b["v_span"])
            except Exception:
                return "clamp"

            outside = (u_min < -0.01) or (v_min < -0.01) or (u_max > 1.01) or (v_max > 1.01)
            # Small excursions can be padding/rounding. Large excursions are the
            # real signal that the mesh expects the sampler to repeat.
            strong_span = (u_span > 1.05) or (v_span > 1.05)
            if outside and strong_span:
                return "repeat"
            return "clamp"

        def _effective_uv_wrap_mode(self) -> str:
            mode = str(getattr(self, "uv_wrap_mode", "auto") or "auto").lower()
            if mode == "repeat":
                return "repeat"
            if mode == "clamp":
                return "clamp"
            return self._auto_uv_wrap_mode_for_current_mesh()

        def _uv_wrap_status_short(self) -> str:
            effective = self._effective_uv_wrap_mode()
            self._last_uv_wrap_effective = effective
            if str(getattr(self, "uv_wrap_mode", "auto") or "auto").lower() == "auto":
                if effective == "repeat":
                    return "UV wrap Auto→Repeat"
                return "UV wrap Auto→Clamp"
            return "UV wrap Repeat" if effective == "repeat" else "UV wrap Clamp"

        def toggle_uv_wrap_mode(self) -> str:
            modes = ["auto", "clamp", "repeat"]
            labels = {
                "auto": "Auto",
                "clamp": "Clamp to edge",
                "repeat": "Repeat / modulo UV",
            }
            cur = str(getattr(self, "uv_wrap_mode", "auto") or "auto").lower()
            try:
                idx = modes.index(cur)
            except ValueError:
                idx = 0
            self.uv_wrap_mode = modes[(idx + 1) % len(modes)]
            label = f"UV texture wrap: {labels.get(self.uv_wrap_mode, self.uv_wrap_mode)}"
            effective = self._effective_uv_wrap_mode()
            if self.uv_wrap_mode == "auto":
                label += f" → {'Repeat' if effective == 'repeat' else 'Clamp'}"
            # Existing GL texture IDs can keep the old sampler state.  Update()
            # will also re-apply parameters after binding, but clear the message
            # immediately so the user sees the chosen mode.
            self._last_uv_wrap_effective = effective
            self.view_name = label
            self.update()
            return label

        def _apply_current_texture_wrap_params(self) -> None:
            """Apply current clamp/repeat sampler state to the currently bound GL texture."""
            try:
                from OpenGL.GL import (
                    glTexParameteri,
                    GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
                    GL_CLAMP_TO_EDGE, GL_REPEAT,
                )
                wrap = GL_REPEAT if self._effective_uv_wrap_mode() == "repeat" else GL_CLAMP_TO_EDGE
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
            except Exception:
                pass

        # =====================================================
        # FRAME MESH
        # =====================================================
        def _frame_mesh(self):
            if not self.vertices:
                self.distance = 4.0
                return

            xs = [v[0] for v in self.vertices]
            ys = [v[1] for v in self.vertices]
            zs = [v[2] for v in self.vertices]

            cx = (min(xs) + max(xs)) * 0.5
            cy = (min(ys) + max(ys)) * 0.5
            cz = (min(zs) + max(zs)) * 0.5
            self.frame_center_offset = (cx, cy, cz)

            self.vertices = [(x - cx, y - cy, z - cz) for x, y, z in self.vertices]
            if getattr(self, "group_child_origins", None):
                try:
                    if bool(getattr(self, "group_zero_origin_offsets_enabled", False)):
                        # In zero-origin debug mode every child origin is intentionally
                        # collapsed to the selected group origin before the final
                        # preview centering step.  Draw the origin markers in that
                        # same collapsed place, otherwise Shift+O looks as if it did
                        # nothing because the overlay still shows the true Unity
                        # child transform positions.
                        collapsed = (-cx, -cy, -cz)
                        self.group_child_origins = [collapsed for _ in self.group_child_origins]
                    else:
                        self.group_child_origins = [(x - cx, y - cy, z - cz) for x, y, z in self.group_child_origins]
                except Exception:
                    pass

            xs = [v[0] for v in self.vertices]
            ys = [v[1] for v in self.vertices]
            zs = [v[2] for v in self.vertices]

            max_dim = max(
                max(xs) - min(xs),
                max(ys) - min(ys),
                max(zs) - min(zs),
            )
            self.mesh_max_dim = max(0.001, float(max_dim))

            self.distance = max(0.1, self.mesh_max_dim * 1.8)

            self.rot_x = 25.0
            self.rot_y = -35.0
            self.rot_z = 0.0
            self.pan_x = 0.0
            self.pan_y = 0.0

        # =====================================================
        # OPENGL
        # =====================================================
        def initializeGL(self):
            try:
                from OpenGL.GL import (
                    glClearColor, glEnable, glDisable,
                    GL_DEPTH_TEST, GL_CULL_FACE,
                    GL_LIGHTING, GL_LIGHT0, GL_COLOR_MATERIAL,
                    glLightfv, glLightModelfv,
                    GL_POSITION, GL_DIFFUSE, GL_SPECULAR,
                    GL_LIGHT_MODEL_TWO_SIDE, GL_LIGHT_MODEL_AMBIENT,
                )

                glClearColor(0.11, 0.11, 0.12, 1.0)
                glEnable(GL_DEPTH_TEST)
                glDisable(GL_CULL_FACE)

                glEnable(GL_LIGHTING)
                glEnable(GL_LIGHT0)
                glEnable(GL_COLOR_MATERIAL)

                glLightModelfv(GL_LIGHT_MODEL_TWO_SIDE, (1.0,))
                glLightModelfv(GL_LIGHT_MODEL_AMBIENT, (0.28, 0.28, 0.30, 1.0))

                glLightfv(GL_LIGHT0, GL_POSITION, (3.5, 4.5, 6.0, 1.0))
                glLightfv(GL_LIGHT0, GL_DIFFUSE, (1.0, 1.0, 1.0, 1.0))
                glLightfv(GL_LIGHT0, GL_SPECULAR, (0.4, 0.4, 0.4, 1.0))

                self.has_gl = True

            except Exception as e:
                self.has_gl = False
                self.message = f"OpenGL unavailable:\n{e}"

        def resizeGL(self, w, h):
            if not self.has_gl:
                return

            from OpenGL.GL import glViewport

            h = max(h, 1)
            glViewport(0, 0, w, h)
            self._apply_projection()

        def _apply_projection(self):
            if not self.has_gl:
                return

            from OpenGL.GL import glMatrixMode, glLoadIdentity, GL_PROJECTION, GL_MODELVIEW
            from OpenGL.GLU import gluPerspective

            w = max(int(self.width()), 1)
            h = max(int(self.height()), 1)

            # Dynamic near/far clip range.  The old fixed near plane of 0.01
            # was fine for normal-sized meshes, but close inspection of large
            # VR scene chunks could visibly slice the model.  This keeps the
            # near plane tiny when zoomed close, while keeping the far plane
            # large enough for whole-course chunks.
            if getattr(self, "close_clip_enabled", True):
                near_clip = max(0.000001, min(0.01, max(self.distance, 0.0001) * 0.0005))
            else:
                near_clip = 0.01

            max_dim = max(getattr(self, "mesh_max_dim", 1.0), 1.0)
            far_clip = max(1000.0, max_dim * 20.0, self.distance + max_dim * 8.0)
            if far_clip <= near_clip * 10.0:
                far_clip = near_clip * 10.0

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(float(getattr(self, "fov_degrees", 45.0)), w / h, near_clip, far_clip)
            glMatrixMode(GL_MODELVIEW)

        def _clear_texture(self):
            ids_to_delete = []
            if self.texture_id is not None:
                ids_to_delete.append(int(self.texture_id))
            if self.normal_texture_id is not None:
                ids_to_delete.append(int(self.normal_texture_id))
            for _tid in getattr(self, "multi_texture_ids", []) or []:
                if _tid is not None:
                    try:
                        ids_to_delete.append(int(_tid))
                    except Exception:
                        pass
            if ids_to_delete:
                try:
                    self.makeCurrent()
                    from OpenGL.GL import glDeleteTextures
                    glDeleteTextures(ids_to_delete)
                    self.doneCurrent()
                except Exception:
                    pass
            self.texture_path = None
            self.texture_bytes = None
            self.texture_width = 0
            self.texture_height = 0
            self.texture_id = None
            self.palette_lookup_texture_enabled = False
            self.normal_texture_path = None
            self.normal_texture_bytes = None
            self.normal_texture_width = 0
            self.normal_texture_height = 0
            self.normal_texture_id = None
            self.multi_texture_images = []
            self.multi_texture_ids = []
            self.face_texture_indices = []
            self.bump_uvs = []

        def _upload_texture_if_needed(self):
            if self.texture_id is not None:
                return
            if not self.texture_bytes or not self.texture_width or not self.texture_height:
                return

            try:
                from OpenGL.GL import (
                    glGenTextures, glBindTexture, glTexParameteri, glTexImage2D, glTexEnvi,
                    GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
                    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_LINEAR, GL_NEAREST, GL_CLAMP_TO_EDGE, GL_REPEAT,
                    GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE,
                )

                tex_id = glGenTextures(1)
                try:
                    tex_id = int(tex_id)
                except Exception:
                    tex_id = int(tex_id[0])

                glBindTexture(GL_TEXTURE_2D, tex_id)
                # Tiny Texture2DArray slices are often palette/lookup textures.
                # NEAREST avoids blending neighbouring 4x4 colour cells together.
                tex_filter = GL_NEAREST if (
                    bool(getattr(self, "palette_lookup_texture_enabled", False))
                    or (self.texture_width <= 16 and self.texture_height <= 16)
                ) else GL_LINEAR
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, tex_filter)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, tex_filter)
                wrap = GL_REPEAT if self._effective_uv_wrap_mode() == "repeat" else GL_CLAMP_TO_EDGE
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
                glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                glTexImage2D(
                    GL_TEXTURE_2D,
                    0,
                    GL_RGBA,
                    self.texture_width,
                    self.texture_height,
                    0,
                    GL_RGBA,
                    GL_UNSIGNED_BYTE,
                    self.texture_bytes,
                )
                self.texture_id = tex_id
            except Exception:
                self.texture_id = None

        def _upload_multi_textures_if_needed(self):
            images = list(getattr(self, "multi_texture_images", []) or [])
            if not images:
                return
            if len(getattr(self, "multi_texture_ids", []) or []) != len(images):
                self.multi_texture_ids = [None for _ in images]

            try:
                from OpenGL.GL import (
                    glGenTextures, glBindTexture, glTexParameteri, glTexImage2D, glTexEnvi,
                    GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
                    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_LINEAR, GL_NEAREST, GL_CLAMP_TO_EDGE, GL_REPEAT,
                    GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE,
                )
            except Exception:
                return

            for i, info in enumerate(images):
                if self.multi_texture_ids[i] is not None:
                    continue
                try:
                    data = info.get("bytes")
                    width = int(info.get("width") or 0)
                    height = int(info.get("height") or 0)
                    if not data or not width or not height:
                        continue
                    tex_id = glGenTextures(1)
                    try:
                        tex_id = int(tex_id)
                    except Exception:
                        tex_id = int(tex_id[0])
                    glBindTexture(GL_TEXTURE_2D, tex_id)
                    tex_filter = GL_NEAREST if (
                        bool(info.get("nearest", False)) or (width <= 16 and height <= 16)
                    ) else GL_LINEAR
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, tex_filter)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, tex_filter)
                    wrap = GL_REPEAT if self._effective_uv_wrap_mode() == "repeat" else GL_CLAMP_TO_EDGE
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
                    self.multi_texture_ids[i] = tex_id
                except Exception:
                    self.multi_texture_ids[i] = None

        def _upload_normal_texture_if_needed(self):
            if self.normal_texture_id is not None:
                return
            if not self.normal_texture_bytes or not self.normal_texture_width or not self.normal_texture_height:
                return
            try:
                from OpenGL.GL import (
                    glGenTextures, glBindTexture, glTexParameteri, glTexImage2D, glTexEnvi,
                    GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
                    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_LINEAR, GL_CLAMP_TO_EDGE,
                    GL_RGBA, GL_UNSIGNED_BYTE, GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE,
                )
                tex_id = glGenTextures(1)
                try:
                    tex_id = int(tex_id)
                except Exception:
                    tex_id = int(tex_id[0])
                glBindTexture(GL_TEXTURE_2D, tex_id)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
                glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                glTexImage2D(
                    GL_TEXTURE_2D, 0, GL_RGBA,
                    self.normal_texture_width, self.normal_texture_height,
                    0, GL_RGBA, GL_UNSIGNED_BYTE, self.normal_texture_bytes,
                )
                self.normal_texture_id = tex_id
            except Exception:
                self.normal_texture_id = None

        def _compile_bump_shader_if_needed(self) -> bool:
            if self.bump_shader_program:
                return True
            if self.bump_shader_error:
                return False
            try:
                from OpenGL.GL import (
                    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv, glGetShaderInfoLog,
                    glCreateProgram, glAttachShader, glLinkProgram, glGetProgramiv, glGetProgramInfoLog,
                    glGetUniformLocation, glGetAttribLocation,
                    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER, GL_COMPILE_STATUS, GL_LINK_STATUS,
                )

                vertex_src = """#version 120
                    attribute vec4 a_tangent;
                    varying vec2 v_base_uv;
                    varying vec2 v_normal_uv;
                    varying vec3 v_light_ts;
                    varying vec3 v_view_ts;
                    void main() {
                        vec4 pos_eye = gl_ModelViewMatrix * gl_Vertex;
                        vec3 n = normalize(gl_NormalMatrix * gl_Normal);
                        vec3 t = normalize(gl_NormalMatrix * a_tangent.xyz);
                        vec3 b = normalize(cross(n, t) * a_tangent.w);
                        vec3 light_eye = normalize(vec3(0.45, 0.65, 0.85));
                        vec3 view_eye = normalize(-pos_eye.xyz);
                        v_light_ts = normalize(vec3(dot(light_eye, t), dot(light_eye, b), dot(light_eye, n)));
                        v_view_ts = normalize(vec3(dot(view_eye, t), dot(view_eye, b), dot(view_eye, n)));
                        v_base_uv = gl_MultiTexCoord0.st;
                        v_normal_uv = gl_MultiTexCoord1.st;
                        gl_Position = ftransform();
                    }
                """

                fragment_src = """#version 120
                    uniform sampler2D u_base_tex;
                    uniform sampler2D u_normal_tex;
                    uniform float u_bump_strength;
                    uniform bool u_flip_green;
                    uniform bool u_use_base;
                    varying vec2 v_base_uv;
                    varying vec2 v_normal_uv;
                    varying vec3 v_light_ts;
                    varying vec3 v_view_ts;
                    void main() {
                        vec4 base = u_use_base ? texture2D(u_base_tex, v_base_uv) : vec4(1.0, 1.0, 1.0, 1.0);
                        vec3 nm = texture2D(u_normal_tex, v_normal_uv).xyz * 2.0 - 1.0;
                        if (u_flip_green) {
                            nm.y = -nm.y;
                        }
                        nm.xy *= max(u_bump_strength, 0.0);
                        nm = normalize(nm);
                        vec3 l = normalize(v_light_ts);
                        vec3 v = normalize(v_view_ts);
                        float diff = max(dot(nm, l), 0.0);
                        vec3 h = normalize(l + v);
                        float spec = pow(max(dot(nm, h), 0.0), 36.0) * 0.18;
                        float shade = 0.34 + diff * 0.74;
                        vec3 rgb = base.rgb * shade + vec3(spec);
                        gl_FragColor = vec4(rgb, base.a);
                    }
                """

                def compile_one(kind, src):
                    shader = glCreateShader(kind)
                    glShaderSource(shader, src)
                    glCompileShader(shader)
                    ok = glGetShaderiv(shader, GL_COMPILE_STATUS)
                    if not ok:
                        info = glGetShaderInfoLog(shader)
                        raise RuntimeError(info.decode("utf-8", "ignore") if isinstance(info, bytes) else str(info))
                    return shader

                vs = compile_one(GL_VERTEX_SHADER, vertex_src)
                fs = compile_one(GL_FRAGMENT_SHADER, fragment_src)
                program = glCreateProgram()
                glAttachShader(program, vs)
                glAttachShader(program, fs)
                glLinkProgram(program)
                ok = glGetProgramiv(program, GL_LINK_STATUS)
                if not ok:
                    info = glGetProgramInfoLog(program)
                    raise RuntimeError(info.decode("utf-8", "ignore") if isinstance(info, bytes) else str(info))

                self.bump_shader_program = int(program)
                self._bump_shader_locations = {
                    "u_base_tex": int(glGetUniformLocation(program, "u_base_tex")),
                    "u_normal_tex": int(glGetUniformLocation(program, "u_normal_tex")),
                    "u_bump_strength": int(glGetUniformLocation(program, "u_bump_strength")),
                    "u_flip_green": int(glGetUniformLocation(program, "u_flip_green")),
                    "u_use_base": int(glGetUniformLocation(program, "u_use_base")),
                    "a_tangent": int(glGetAttribLocation(program, "a_tangent")),
                }
                return True
            except Exception as exc:
                self.bump_shader_error = str(exc)
                return False

        @staticmethod
        def _vec_sub(a, b):
            return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

        @staticmethod
        def _vec_cross(a, b):
            return (
                a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0],
            )

        @staticmethod
        def _vec_dot(a, b):
            return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

        @staticmethod
        def _vec_norm(v, fallback=(1.0, 0.0, 0.0)):
            length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
            if length <= 1e-8:
                return fallback
            return (v[0] / length, v[1] / length, v[2] / length)

        def _vertex_normal_for_face_item(self, item, face_n):
            try:
                ni = item[2]
                if ni is not None and 0 <= ni < len(self.normals):
                    return self._vec_norm(self.normals[ni], face_n)
            except Exception:
                pass
            return face_n

        def _triangle_tangent(self, tri, face_n):
            try:
                i0, i1, i2 = tri[0][0], tri[1][0], tri[2][0]
                t0, t1, t2 = tri[0][1], tri[1][1], tri[2][1]
                if t0 is None or t1 is None or t2 is None:
                    return (1.0, 0.0, 0.0, 1.0)
                if not self.bump_uvs or t0 >= len(self.bump_uvs) or t1 >= len(self.bump_uvs) or t2 >= len(self.bump_uvs):
                    return (1.0, 0.0, 0.0, 1.0)
                p0, p1, p2 = self.vertices[i0], self.vertices[i1], self.vertices[i2]
                uv0, uv1, uv2 = self.bump_uvs[t0], self.bump_uvs[t1], self.bump_uvs[t2]
                e1 = self._vec_sub(p1, p0)
                e2 = self._vec_sub(p2, p0)
                du1, dv1 = uv1[0] - uv0[0], uv1[1] - uv0[1]
                du2, dv2 = uv2[0] - uv0[0], uv2[1] - uv0[1]
                denom = du1 * dv2 - du2 * dv1
                if abs(denom) <= 1e-10:
                    return (1.0, 0.0, 0.0, 1.0)
                r = 1.0 / denom
                tangent = ((e1[0] * dv2 - e2[0] * dv1) * r, (e1[1] * dv2 - e2[1] * dv1) * r, (e1[2] * dv2 - e2[2] * dv1) * r)
                bitangent = ((e2[0] * du1 - e1[0] * du2) * r, (e2[1] * du1 - e1[1] * du2) * r, (e2[2] * du1 - e1[2] * du2) * r)
                tangent = self._vec_norm(tangent, (1.0, 0.0, 0.0))
                bitangent = self._vec_norm(bitangent, (0.0, 1.0, 0.0))
                sign = -1.0 if self._vec_dot(self._vec_cross(face_n, tangent), bitangent) < 0.0 else 1.0
                return (tangent[0], tangent[1], tangent[2], sign)
            except Exception:
                return (1.0, 0.0, 0.0, 1.0)

        def _helper_preview_colour(self) -> tuple[float, float, float]:
            """Pick an educational flat-shade colour based on helper-ish names."""
            name = str(getattr(self, "mesh_name", "") or "").lower()
            if "donotwarp" in name or "no_warp" in name or "nowarp" in name:
                return (0.92, 0.55, 0.18)
            if "walkway" in name or "path" in name:
                return (0.22, 0.48, 0.90)
            if "trigger" in name or "zone" in name:
                return (0.78, 0.42, 0.92)
            if "navmesh" in name or "collision" in name or "collider" in name:
                return (0.20, 0.72, 0.48)
            return (0.68, 0.70, 0.74)

        def _paint_helper_preview(self) -> bool:
            """Draw a texture-free flat shaded mesh with wireframe edges.

            This is useful for collision/nav/helper meshes where the assigned
            texture may be misleading.  The mesh shape is the important data.
            """
            if not getattr(self, "helper_preview_enabled", False):
                return False
            if not self.vertices or not self.faces:
                return False
            try:
                from OpenGL.GL import (
                    glBegin, glEnd, glColor3f, glVertex3f, glDisable, glEnable,
                    glLineWidth, GL_TRIANGLES, GL_LINES, GL_TEXTURE_2D,
                    GL_LIGHTING, GL_CULL_FACE, GL_DEPTH_TEST,
                )
            except Exception:
                return False

            base = self._helper_preview_colour()
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_LIGHTING)
            glDisable(GL_CULL_FACE)
            glEnable(GL_DEPTH_TEST)

            # Soft flat shaded fill.  Keep it neutral enough that triangle shape
            # and helper/collision form read clearly.
            glBegin(GL_TRIANGLES)
            for face_index, tri in enumerate(self.faces):
                if not self._group_face_is_visible(face_index):
                    continue
                n = self._face_normal(tri)
                shade = max(0.32, min(1.0, 0.62 + (n[1] * 0.22) + (n[2] * 0.18)))
                glColor3f(base[0] * shade, base[1] * shade, base[2] * shade)
                for vi, _ti, _ni in tri:
                    if 0 <= vi < len(self.vertices):
                        p = self.vertices[vi]
                        glVertex3f(p[0], p[1], p[2])
            glEnd()

            # Edge overlay.  This makes nav/collision strips and green surfaces
            # much easier to read while arrowing through helper objects.
            try:
                glLineWidth(1.15)
            except Exception:
                pass
            glColor3f(0.03, 0.06, 0.07)
            glBegin(GL_LINES)
            for face_index, tri in enumerate(self.faces):
                if not self._group_face_is_visible(face_index):
                    continue
                pairs = ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0]))
                for a, b in pairs:
                    ia, ib = a[0], b[0]
                    if 0 <= ia < len(self.vertices) and 0 <= ib < len(self.vertices):
                        pa = self.vertices[ia]
                        pb = self.vertices[ib]
                        glVertex3f(pa[0], pa[1], pa[2])
                        glVertex3f(pb[0], pb[1], pb[2])
            glEnd()
            try:
                glLineWidth(1.0)
            except Exception:
                pass
            self._paint_group_origin_markers()
            return True

        def _paint_group_origin_markers(self) -> bool:
            """Draw small cross/axis markers at assembled child origins."""
            if not getattr(self, "group_origin_markers_enabled", False):
                return False
            origins = list(getattr(self, "group_child_origins", []) or [])
            names = list(getattr(self, "group_child_names", []) or [])
            if not origins or getattr(self, "_last_export_mode", "") not in ("group", "multi_select"):
                return False
            try:
                from OpenGL.GL import (
                    glBegin, glEnd, glColor3f, glVertex3f, glDisable, glLineWidth,
                    GL_LINES, GL_TEXTURE_2D, GL_LIGHTING, GL_DEPTH_TEST, glEnable,
                )
            except Exception:
                return False

            glDisable(GL_TEXTURE_2D)
            glDisable(GL_LIGHTING)
            glEnable(GL_DEPTH_TEST)
            try:
                glLineWidth(2.0)
            except Exception:
                pass

            size = max(0.03, float(getattr(self, "mesh_max_dim", 1.0) or 1.0) * 0.035)
            glBegin(GL_LINES)
            for idx, origin in enumerate(origins):
                if not self._group_child_is_visible(idx):
                    continue
                x, y, z = origin
                # X axis marker, red-ish
                glColor3f(1.0, 0.18, 0.16)
                glVertex3f(x - size, y, z)
                glVertex3f(x + size, y, z)
                # Y axis marker, green-ish
                glColor3f(0.18, 0.95, 0.28)
                glVertex3f(x, y - size, z)
                glVertex3f(x, y + size, z)
                # Z axis marker, blue-ish
                glColor3f(0.20, 0.45, 1.0)
                glVertex3f(x, y, z - size)
                glVertex3f(x, y, z + size)
            glEnd()
            try:
                glLineWidth(1.0)
            except Exception:
                pass
            return True

        def _paint_lit_bump_preview(self) -> bool:
            """Draw the lit normal/bump preview.

            This path uses a small GLSL shader and immediate-mode OpenGL for
            maximum compatibility with the rest of UBE's lightweight previewer.
            Some odd meshes/drivers can throw GL_INVALID_OPERATION during the
            glBegin/glEnd block.  Do not let that kill the whole QOpenGLWidget;
            disable lit bump for this view and fall back to the normal preview.
            """
            if not getattr(self, "lit_bump_enabled", False):
                return False
            if not self.vertices or not self.faces or not self.normal_texture_bytes or not self.bump_uvs:
                return False
            if not self._compile_bump_shader_if_needed():
                self.view_name = f"Bump shader unavailable: {self.bump_shader_error[:80]}"
                return False
            self._upload_texture_if_needed()
            self._upload_normal_texture_if_needed()
            if self.normal_texture_id is None:
                return False

            def _finite2(v) -> bool:
                try:
                    return math.isfinite(float(v[0])) and math.isfinite(float(v[1]))
                except Exception:
                    return False

            def _finite3(v) -> bool:
                try:
                    return math.isfinite(float(v[0])) and math.isfinite(float(v[1])) and math.isfinite(float(v[2]))
                except Exception:
                    return False

            began = False
            try:
                from OpenGL.GL import (
                    glUseProgram, glUniform1i, glUniform1f, glActiveTexture, glBindTexture,
                    glBegin, glEnd, glVertex3f, glNormal3f, glMultiTexCoord2f, glVertexAttrib4f,
                    glDisable, glEnable, glColor3f, glGetError,
                    GL_TRIANGLES, GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1,
                    GL_LIGHTING, GL_CULL_FACE, GL_NO_ERROR,
                )
            except Exception:
                return False

            loc = self._bump_shader_locations or {}
            program = int(self.bump_shader_program or 0)
            tangent_loc = int(loc.get("a_tangent", -1))

            def _clear_gl_errors() -> None:
                try:
                    for _ in range(16):
                        if glGetError() == GL_NO_ERROR:
                            break
                except Exception:
                    pass

            try:
                # Clear stale GL error flags from a previous bad draw so PyOpenGL
                # does not report an old error on this path's first checked call.
                _clear_gl_errors()

                glDisable(GL_LIGHTING)
                glDisable(GL_CULL_FACE)
                glEnable(GL_TEXTURE_2D)
                glUseProgram(program)
                glActiveTexture(GL_TEXTURE0)
                if self.texture_id is not None:
                    glBindTexture(GL_TEXTURE_2D, int(self.texture_id))
                    self._apply_current_texture_wrap_params()
                glUniform1i(loc.get("u_base_tex", -1), 0)
                glUniform1i(loc.get("u_use_base", -1), 1 if self.texture_id is not None and bool(self.uvs) else 0)
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, int(self.normal_texture_id))
                self._apply_current_texture_wrap_params()
                glUniform1i(loc.get("u_normal_tex", -1), 1)
                glUniform1f(loc.get("u_bump_strength", -1), float(getattr(self, "bump_strength", 2.0)))
                glUniform1i(loc.get("u_flip_green", -1), 1 if getattr(self, "normal_green_flip", False) else 0)
                glColor3f(1.0, 1.0, 1.0)

                glBegin(GL_TRIANGLES)
                began = True
                v_count = len(self.vertices)
                uv_count = len(self.uvs)
                bump_uv_count = len(self.bump_uvs)
                for face_index, tri in enumerate(self.faces):
                    if not self._group_face_is_visible(face_index):
                        continue
                    face_n = self._face_normal(tri)
                    if not _finite3(face_n):
                        continue
                    tangent = self._triangle_tangent(tri, face_n)
                    if not _finite3(tangent):
                        tangent = (1.0, 0.0, 0.0, 1.0)
                    for item in tri:
                        vi, ti, _ni = item
                        if vi is None or vi < 0 or vi >= v_count:
                            continue
                        p = self.vertices[vi]
                        if not _finite3(p):
                            continue
                        n = self._vertex_normal_for_face_item(item, face_n)
                        if not _finite3(n):
                            n = face_n
                        glNormal3f(float(n[0]), float(n[1]), float(n[2]))
                        if tangent_loc >= 0:
                            glVertexAttrib4f(tangent_loc, float(tangent[0]), float(tangent[1]), float(tangent[2]), float(tangent[3]))
                        if ti is not None and 0 <= ti < uv_count and _finite2(self.uvs[ti]):
                            u, v = self.uvs[ti]
                        else:
                            u, v = 0.0, 0.0
                        if ti is not None and 0 <= ti < bump_uv_count and _finite2(self.bump_uvs[ti]):
                            nu, nv = self.bump_uvs[ti]
                        else:
                            nu, nv = u, v
                        glMultiTexCoord2f(GL_TEXTURE0, float(u), float(v))
                        glMultiTexCoord2f(GL_TEXTURE1, float(nu), float(nv))
                        glVertex3f(float(p[0]), float(p[1]), float(p[2]))
                glEnd()
                began = False
                glUseProgram(0)
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, 0)
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, 0)
                glDisable(GL_TEXTURE_2D)
                _clear_gl_errors()
                return True
            except Exception as exc:
                # If the immediate-mode shader path hits a driver/mesh-specific
                # invalid operation, recover and fall back to the regular preview.
                try:
                    if began:
                        glEnd()
                except Exception:
                    pass
                try:
                    glUseProgram(0)
                    glActiveTexture(GL_TEXTURE1)
                    glBindTexture(GL_TEXTURE_2D, 0)
                    glActiveTexture(GL_TEXTURE0)
                    glBindTexture(GL_TEXTURE_2D, 0)
                    glDisable(GL_TEXTURE_2D)
                except Exception:
                    pass
                _clear_gl_errors()
                self.lit_bump_enabled = False
                self.bump_shader_error = f"Lit bump preview disabled after OpenGL error: {exc}"
                self.view_name = "Lit bump preview disabled for this mesh; using regular preview"
                return False

        def paintGL(self):
            if not self.has_gl:
                self._paint_message()
                return

            from OpenGL.GL import (
                glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
                glMatrixMode, glLoadIdentity, GL_MODELVIEW,
                glTranslatef, glRotatef,
                glBegin, glEnd, GL_TRIANGLES,
                glColor3f, glVertex3f, glTexCoord2f,
                glDisable, glEnable, glBindTexture,
                GL_LIGHTING, GL_DEPTH_TEST, GL_CULL_FACE, GL_TEXTURE_2D,
            )

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            self._apply_projection()

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            glTranslatef(self.pan_x, self.pan_y, -self.distance)
            glRotatef(self.rot_x, 1.0, 0.0, 0.0)
            glRotatef(self.rot_y, 0.0, 1.0, 0.0)
            glRotatef(self.rot_z, 0.0, 0.0, 1.0)

            # MODEL BASE ORIENTATION FIX
            glRotatef(self.model_rot_x, 1.0, 0.0, 0.0)
            glRotatef(self.model_rot_y, 0.0, 1.0, 0.0)
            glRotatef(self.model_rot_z, 0.0, 0.0, 1.0)

            glDisable(GL_LIGHTING)
            glDisable(GL_CULL_FACE)
            glEnable(GL_DEPTH_TEST)

            if not self.vertices or not self.faces:
                glDisable(GL_TEXTURE_2D)
                self._draw_fallback_cube()
                self._paint_message()
                self._paint_axis_indicator()
                return

            if self._paint_helper_preview():
                glEnable(GL_LIGHTING)
                self._paint_axis_indicator()
                return

            self._upload_texture_if_needed()
            self._upload_multi_textures_if_needed()
            use_multi_texture = bool(getattr(self, "multi_texture_images", None)) and bool(getattr(self, "face_texture_indices", None))
            use_texture = self.texture_id is not None and bool(self.uvs) and not use_multi_texture
            if use_texture:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, int(self.texture_id))
                self._apply_current_texture_wrap_params()
            else:
                glDisable(GL_TEXTURE_2D)

            if (not use_multi_texture) and self._paint_lit_bump_preview():
                self._paint_group_origin_markers()
                glEnable(GL_LIGHTING)
                self._paint_axis_indicator()
                return

            if use_multi_texture:
                texture_ids = list(getattr(self, "multi_texture_ids", []) or [])
                face_tex = list(getattr(self, "face_texture_indices", []) or [])
                current_bound = object()
                drawing = False
                for face_index, tri in enumerate(self.faces):
                    if not self._group_face_is_visible(face_index):
                        continue
                    tex_idx = face_tex[face_index] if face_index < len(face_tex) else None
                    tex_id = None
                    if tex_idx is not None and 0 <= int(tex_idx) < len(texture_ids):
                        tex_id = texture_ids[int(tex_idx)]
                    if tex_id != current_bound:
                        if drawing:
                            glEnd()
                            drawing = False
                        if tex_id is not None:
                            glEnable(GL_TEXTURE_2D)
                            glBindTexture(GL_TEXTURE_2D, int(tex_id))
                            self._apply_current_texture_wrap_params()
                        else:
                            glDisable(GL_TEXTURE_2D)
                        glBegin(GL_TRIANGLES)
                        drawing = True
                        current_bound = tex_id

                    n = self._face_normal(tri)
                    shade = max(0.35, min(1.0, 0.65 + (n[1] * 0.25) + (n[2] * 0.20)))
                    if tex_id is None and getattr(self, "face_colors", None) and face_index < len(self.face_colors):
                        r, g, b = self.face_colors[face_index]
                        glColor3f(shade * r, shade * g, shade * b)
                    else:
                        glColor3f(shade, shade, shade)
                    for vi, ti, _ni in tri:
                        if tex_id is not None and ti is not None and 0 <= ti < len(self.uvs):
                            u, v = self.uvs[ti]
                            glTexCoord2f(u, v)
                        vtx = self.vertices[vi]
                        glVertex3f(vtx[0], vtx[1], vtx[2])
                if drawing:
                    glEnd()
                glDisable(GL_TEXTURE_2D)
                self._paint_group_origin_markers()
                glEnable(GL_LIGHTING)
                self._paint_axis_indicator()
                return

            glBegin(GL_TRIANGLES)

            for face_index, tri in enumerate(self.faces):
                if not self._group_face_is_visible(face_index):
                    continue
                n = self._face_normal(tri)
                shade = max(0.35, min(1.0, 0.65 + (n[1] * 0.25) + (n[2] * 0.20)))

                # OpenGL fixed-pipeline colour multiplies the texture.
                # For textured meshes default to neutral shading only.  Tint can be
                # toggled with T for materials where Unity _BaseColor really is a tint.
                if (not use_texture) and getattr(self, "face_colors", None) and face_index < len(self.face_colors):
                    r, g, b = self.face_colors[face_index]
                    glColor3f(shade * r, shade * g, shade * b)
                elif self.material_color and (not use_texture or getattr(self, "texture_tint_enabled", False)):
                    r, g, b = self.material_color
                    glColor3f(shade * r, shade * g, shade * b)
                else:
                    glColor3f(shade, shade, shade)

                for vi, ti, _ni in tri:
                    if use_texture and ti is not None and 0 <= ti < len(self.uvs):
                        u, v = self.uvs[ti]
                        glTexCoord2f(u, v)
                    vtx = self.vertices[vi]
                    glVertex3f(vtx[0], vtx[1], vtx[2])

            glEnd()
            glDisable(GL_TEXTURE_2D)
            self._paint_group_origin_markers()
            glEnable(GL_LIGHTING)
            self._paint_axis_indicator()

        def _paint_message(self):
            if not self.message:
                return
            try:
                from PySide6.QtGui import QPainter, QColor
                painter = QPainter(self)
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(self.rect(), Qt.AlignCenter, self.message)
                painter.end()
            except Exception:
                pass

        def _draw_fallback_cube(self):
            from OpenGL.GL import glBegin, glEnd, GL_TRIANGLES, glColor3f, glVertex3f

            verts = [
                (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
                (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
            ]
            faces = [
                (0, 1, 2), (0, 2, 3),
                (4, 6, 5), (4, 7, 6),
                (0, 4, 5), (0, 5, 1),
                (3, 2, 6), (3, 6, 7),
                (1, 5, 6), (1, 6, 2),
                (0, 3, 7), (0, 7, 4),
            ]

            glColor3f(0.65, 0.67, 0.72)
            glBegin(GL_TRIANGLES)
            for face in faces:
                for idx in face:
                    glVertex3f(*verts[idx])
            glEnd()

        # =====================================================
        # NORMALS
        # =====================================================
        def _face_normal(self, tri):
            try:
                a = self.vertices[tri[0][0]]
                b = self.vertices[tri[1][0]]
                c = self.vertices[tri[2][0]]

                ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
                vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]

                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx

                length = math.sqrt(nx * nx + ny * ny + nz * nz)
                if length <= 1e-6:
                    return (0.0, 1.0, 0.0)

                return (nx / length, ny / length, nz / length)
            except Exception:
                return (0.0, 1.0, 0.0)

        # =====================================================
        # VIEWPORT BOX VISIBILITY SELECTION
        # =====================================================
        def _group_child_screen_bounds(self) -> dict[int, tuple[float, float, float, float]]:
            """Project each render element into the current viewport.

            Bounds are calculated from a bounded vertex sample at the currently
            displayed animation pose.  This keeps selection responsive even for
            very dense meshes while remaining much more precise than projecting
            one world-space aggregate box.
            """
            if not self.has_gl or getattr(self, "_last_export_mode", "") not in ("group", "multi_select"):
                return {}
            parts = list(getattr(self, "group_dynamic_parts", []) or [])
            vertices = list(getattr(self, "vertices", []) or [])
            if not parts or not vertices:
                return {}

            bounds: dict[int, tuple[float, float, float, float]] = {}
            try:
                from OpenGL.GL import (
                    glMatrixMode, glLoadIdentity, glTranslatef, glRotatef,
                    glGetDoublev, glGetIntegerv,
                    GL_MODELVIEW, GL_MODELVIEW_MATRIX, GL_PROJECTION_MATRIX, GL_VIEWPORT,
                )
                from OpenGL.GLU import gluProject

                self.makeCurrent()
                self._apply_projection()
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                glTranslatef(self.pan_x, self.pan_y, -self.distance)
                glRotatef(self.rot_x, 1.0, 0.0, 0.0)
                glRotatef(self.rot_y, 0.0, 1.0, 0.0)
                glRotatef(self.rot_z, 0.0, 0.0, 1.0)
                glRotatef(self.model_rot_x, 1.0, 0.0, 0.0)
                glRotatef(self.model_rot_y, 0.0, 1.0, 0.0)
                glRotatef(self.model_rot_z, 0.0, 0.0, 1.0)

                model = glGetDoublev(GL_MODELVIEW_MATRIX)
                projection = glGetDoublev(GL_PROJECTION_MATRIX)
                viewport = glGetIntegerv(GL_VIEWPORT)
                widget_w = max(float(self.width()), 1.0)
                widget_h = max(float(self.height()), 1.0)
                scale_x = max(float(viewport[2]) / widget_w, 1e-9)
                scale_y = max(float(viewport[3]) / widget_h, 1e-9)

                for part in parts:
                    try:
                        child_index = int(part.get("child_index", -1))
                        start = int(part.get("vertex_start", 0))
                        count = len(part.get("source_vertices") or [])
                    except Exception:
                        continue
                    if child_index < 0 or count <= 0 or start < 0 or start >= len(vertices):
                        continue
                    end = min(len(vertices), start + count)
                    if end <= start:
                        continue
                    # A few hundred projected points per render element is ample
                    # for screen-space selection and avoids touching every vertex.
                    stride = max(1, (end - start) // 640)
                    indices = list(range(start, end, stride))
                    if indices[-1] != end - 1:
                        indices.append(end - 1)
                    xs = []
                    ys = []
                    for vertex_index in indices:
                        vertex = vertices[vertex_index]
                        try:
                            win_x, win_y, win_z = gluProject(
                                float(vertex[0]), float(vertex[1]), float(vertex[2]),
                                model, projection, viewport,
                            )
                        except Exception:
                            continue
                        if not (math.isfinite(win_x) and math.isfinite(win_y) and math.isfinite(win_z)):
                            continue
                        if win_z < 0.0 or win_z > 1.0:
                            continue
                        xs.append((float(win_x) - float(viewport[0])) / scale_x)
                        ys.append((float(viewport[3]) - (float(win_y) - float(viewport[1]))) / scale_y)
                    if xs and ys:
                        bounds[child_index] = (min(xs), min(ys), max(xs), max(ys))
            except Exception:
                bounds = {}
            finally:
                try:
                    self.doneCurrent()
                except Exception:
                    pass
            return bounds

        @staticmethod
        def _screen_rect_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
            return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])

        def _apply_group_box_visibility(self, rect: QRect, mode: str) -> str:
            names = list(getattr(self, "group_child_names", []) or [])
            if getattr(self, "_last_export_mode", "") not in ("group", "multi_select") or not names:
                return "Viewport box selection: no assembled render elements"
            normalized = rect.normalized()
            if normalized.width() < 3 or normalized.height() < 3:
                return "Viewport box selection cancelled"

            selection_rect = (
                float(normalized.left()), float(normalized.top()),
                float(normalized.right()), float(normalized.bottom()),
            )
            selected = {
                child_index
                for child_index, child_bounds in self._group_child_screen_bounds().items()
                if self._group_child_is_visible(child_index)
                and self._screen_rect_intersects(selection_rect, child_bounds)
            }
            if not selected:
                label = "Viewport box selection: no visible render elements touched"
                self.view_name = label
                self.update()
                return label

            self.group_hidden_child_index = None
            self.group_solo_child_index = None
            if str(mode) == "hide":
                hidden = set(getattr(self, "group_box_hidden_child_indices", set()) or set())
                hidden.update(selected)
                self.group_box_hidden_child_indices = hidden
                visible_count = sum(1 for index in range(len(names)) if self._group_child_is_visible(index))
                label = (
                    f"Box hidden: {len(selected)} render element(s); "
                    f"{visible_count}/{len(names)} remain visible/exportable"
                )
            else:
                self.group_box_hidden_child_indices = set()
                self.group_box_solo_child_indices = set(selected)
                label = (
                    f"Box isolated: {len(selected)}/{len(names)} render element(s) "
                    f"visible/exportable"
                )

            self.view_name = label
            self._notify_visibility_filter_changed(label)
            self.update()
            return label

        def paintEvent(self, event):
            # Let QOpenGLWidget render the scene first, then place the rubber-band
            # rectangle above the framebuffer with QPainter.
            super().paintEvent(event)
            if not bool(getattr(self, "box_select_active", False)):
                return
            try:
                from PySide6.QtGui import QPainter, QColor, QPen, QBrush
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                mode = str(getattr(self, "box_select_mode", "") or "")
                color = QColor(255, 105, 95, 220) if mode == "hide" else QColor(80, 190, 255, 230)
                fill = QColor(color)
                fill.setAlpha(38)
                pen = QPen(color)
                pen.setWidth(2)
                pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
                painter.setBrush(QBrush(fill))
                rect = QRect(self.box_select_start, self.box_select_end).normalized()
                painter.drawRect(rect)
                painter.setPen(color)
                label = "Hide touched render elements" if mode == "hide" else "Isolate touched render elements"
                painter.drawText(rect.adjusted(5, 4, -4, -4), Qt.AlignLeft | Qt.AlignTop, label)
                painter.end()
            except Exception:
                pass

        # =====================================================
        # INPUT
        # =====================================================
        def mousePressEvent(self, event):
            try:
                self.setFocus()
            except Exception:
                pass
            pos = event.position().toPoint()
            try:
                mods = event.modifiers()
                button = event.button()
            except Exception:
                mods = Qt.NoModifier
                button = Qt.NoButton

            if button == Qt.LeftButton and (mods & (Qt.ShiftModifier | Qt.ControlModifier)):
                self.box_select_active = True
                self.box_select_mode = "hide" if (mods & Qt.ControlModifier) else "isolate"
                self.box_select_start = QPoint(pos)
                self.box_select_end = QPoint(pos)
                try:
                    self.setCursor(Qt.CrossCursor)
                except Exception:
                    pass
                event.accept()
                self.update()
                return

            self.last_pos = pos

        def mouseMoveEvent(self, event):
            pos = event.position().toPoint()
            if bool(getattr(self, "box_select_active", False)):
                self.box_select_end = QPoint(pos)
                event.accept()
                self.update()
                return

            dx = pos.x() - self.last_pos.x()
            dy = pos.y() - self.last_pos.y()

            buttons = event.buttons()

            snap = False
            try:
                snap = bool(event.modifiers() & Qt.ShiftModifier)
            except Exception:
                snap = False

            # Left mouse = normal orbit / tumble.
            # The multiplier is degrees per mouse pixel.
            if buttons & Qt.LeftButton:
                self.rot_y += dx * 0.5
                self.rot_x += dy * 0.5
                if snap:
                    self.rot_x = self._snap_angle(self.rot_x)
                    self.rot_y = self._snap_angle(self.rot_y)

            # Right mouse = single-axis corrective rotation.
            # Default is Z roll, useful when a Unity object comes in tilted.
            # Press X/Y/Z to choose the right-drag axis.  Hold Shift for 15° snap.
            elif buttons & Qt.RightButton:
                axis = getattr(self, "right_drag_axis", "z")
                if axis == "x":
                    self.rot_x += dy * 0.5
                    if snap:
                        self.rot_x = self._snap_angle(self.rot_x)
                elif axis == "y":
                    self.rot_y += dx * 0.5
                    if snap:
                        self.rot_y = self._snap_angle(self.rot_y)
                else:
                    self.rot_z += dx * 0.5
                    if snap:
                        self.rot_z = self._snap_angle(self.rot_z)

            # Middle mouse = pan
            elif buttons & Qt.MiddleButton:
                scale = max(self.distance, 0.1) * 0.0015
                self.pan_x += dx * scale
                self.pan_y -= dy * scale

            self.last_pos = pos
            self.update()

        def mouseReleaseEvent(self, event):
            if bool(getattr(self, "box_select_active", False)):
                try:
                    pos = event.position().toPoint()
                except Exception:
                    pos = QPoint(self.box_select_end)
                self.box_select_end = QPoint(pos)
                rect = QRect(self.box_select_start, self.box_select_end)
                mode = str(getattr(self, "box_select_mode", "") or "isolate")
                self.box_select_active = False
                self.box_select_mode = ""
                try:
                    self.unsetCursor()
                except Exception:
                    pass
                self._apply_group_box_visibility(rect, mode)
                event.accept()
                self.update()
                return
            return super().mouseReleaseEvent(event)

        def wheelEvent(self, event):
            delta = event.angleDelta().y()

            ctrl = False
            try:
                ctrl = bool(event.modifiers() & Qt.ControlModifier)
            except Exception:
                ctrl = False

            if ctrl:
                # Ctrl + wheel changes the lens/FOV instead of dollying.
                # Useful for very large scene chunks where you want a little
                # more perspective/overview without moving the camera through
                # the mesh.
                self.fov_degrees -= (delta / 120.0) * 3.0
                self.fov_degrees = max(15.0, min(float(self.fov_degrees), 80.0))
                self.view_name = f"FOV {self.fov_degrees:.0f}°"
                self.update()
                return

            zoom_speed = 0.0015 * self.distance

            self.distance -= delta * zoom_speed
            min_distance = 0.0001 if getattr(self, "close_clip_enabled", True) else 0.01
            self.distance = max(min_distance, min(self.distance, 5000.0))

            self.update()

else:

    class Preview3DWidget:
        pass
