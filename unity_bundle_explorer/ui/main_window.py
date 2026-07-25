from __future__ import annotations

from pathlib import Path
from html import escape
import csv
import datetime as dt
import json
import math
import re
import subprocess
import struct
import sys
import threading
import time
from urllib.parse import quote, unquote

from ..core.bundle_reader import load_bundle, AssetRecord
from ..core.unityfs_header import read_unityfs_header
from ..core.project_scanner import scan_project_folder, related_bundle_paths
from ..core.project_ref_index import INDEX_FILENAME, index_path, lookup_pathid_index_records
from ..core.asset_details import (
    describe_record,
    texture_details,
    cubemap_details,
    audio_details,
    display_name_with_icon,
    friendly_type_name,
    preview_unavailable_message,
    _resolve_record,
    _animctrl_unique_clip_refs,
    _anim_build_path_hash_index,
    _anim_build_path_record_index,
    _anim_binding_property_text,
    _anim_binding_type_id,
    ANIMATION_BINDING_TYPE_NAMES,
    _animation_runtime_linkage_diagnostic,
)
from ..exporters.texture_exporter import export_texture_record, export_texture_array_record, export_sprite_record, export_sprite_renderer_record
from ..exporters.audio_exporter import export_audio_record, export_audio_wav_record
from ..exporters.audio_decoder import inspect_fsb5_file, find_vgmstream_cli, decode_with_vgmstream
from ..exporters.report_exporter import write_combined_html_report, write_separate_html_reports, safe_report_filename
from ..exporters.mesh_exporter import (
    export_mesh_record,
    export_object_record,
    export_mesh_glb_record,
    export_object_glb_record,
    export_multi_object_record,
    export_multi_object_glb_records,
    apply_ground_axis_to_export_result,
    _matrix_gltf_trs_shear,
)
from ..cache.thumbnail_cache import get_texture_preview
from ..asset_graph import AssetGraph
from ..app_info import APP_VERSION, APP_BUILD, full_title
from ..core.comment_store import BundleCommentStore
from ..core.streamed_animation import decode_streamed_transform_tracks
from ..core.render_variants import detect_overlapping_render_variants


def main() -> None:
    try:
        from PySide6.QtCore import Qt, QPoint, QEvent, QUrl, QPointF, QRectF, QSettings, QByteArray, QTimer, QEventLoop
        from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont, QFontDatabase
        from PySide6.QtWidgets import (
            QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox,
            QSplitter, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout,
            QTextBrowser, QPushButton, QLineEdit, QHBoxLayout, QMenu, QToolBar,
            QDialog, QDialogButtonBox, QComboBox, QFormLayout, QAbstractItemView,
            QInputDialog, QPlainTextEdit, QSizePolicy, QSlider, QCheckBox,
            QDoubleSpinBox, QAbstractSpinBox
        )
        from PySide6.QtWidgets import QStackedWidget
        from .preview_3d import Preview3DWidget, show_preview_help_dialog
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        except Exception:
            QMediaPlayer = None
            QAudioOutput = None
    except Exception as e:
        print("PySide6 is not installed. Install with: pip install -r requirements.txt")
        print(e)
        return

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(full_title())
            self.resize(1250, 780)
            self.bundle_index = None
            self.project_index = None
            self.current_project_folder = None
            self.serialized_assets_folder = None
            self.selected_record = None
            self.asset_graph = AssetGraph()
            self.item_by_path_id = {}
            self.history = []
            self.history_index = -1
            self._suppress_history = False
            self.collapsed_inspector_sections = set()
            self.external_bundle_cache = {}
            self.pathid_index = None
            self.pathid_index_status = ""
            self.pathid_lookup_cache = {}
            self._pathid_lookup_render_budget = 0
            self.preview_focus_mode = False
            self.preview_focus_prev_splitter_sizes = None
            self.last_export_folder = ""
            self.recent_items = self.load_recent_items()
            self.texture_preview_base_pixmap = None
            self.texture_preview_record_path_id = None
            self.texture_preview_texture_size = None
            self.texture_preview_cache_path = None
            self.texture_atlas_overlay = None
            self.texture_preview_zoom = 1.0
            self.texture_preview_pan = QPointF(0.0, 0.0)
            self.texture_preview_panning = False
            self.texture_preview_pan_last_pos = QPointF(0.0, 0.0)
            # v2.0l: preserve the texture viewer's zoom level and viewed region
            # while entering/leaving preview focus mode.  The texture remains
            # capped at a true 1:1 display of the decoded preview pixels.
            self._texture_focus_restore_pending = False
            self.texture_region_selecting = False
            self.texture_region_select_start = None
            self.texture_region_select_current = None
            self.texture_region_search_html_by_pid = {}
            self.texture_region_search_visible_by_pid = {}

            # v1.8zk: optional right-click branch scoped filter.
            # This lets a branch such as Mesh (440) be narrowed to "trex"
            # without filtering the rest of the bundle tree into the same view.
            self.branch_filter_item = None
            self.branch_filter_text = ""
            self.branch_filter_label = ""

            # v2.0d: one active asset-type isolation at a time.  The tree keeps
            # its full contents in memory; this only changes item visibility so
            # clearing the isolation is immediate even on very large bundles.
            self.isolated_asset_type = ""
            self.asset_type_items = {}

            # v1.8d: persistent breadcrumb trail for screenshots/debug browsing.
            # This is separate from Back/Forward navigation history.
            self.selection_history_log = []
            self.selection_history_max = 500
            self.selection_history_file = Path.home() / ".ube_cache" / "selection_history.tsv"

            # v1.8e: in-app search results for current bundle/project PathID lookup.
            self.project_search_results = []

            # v2.0a: small, human-readable, bundle-specific JSON annotations.
            # Keys include the owning internal SerializedFile name because a PathID
            # is only unique inside that file, not across an entire Unity project.
            self.comment_store = BundleCommentStore()
            self.item_by_comment_key = {}

            # v2.0h: remember the active relationship-flow record so the HTML
            # card grid can be rebuilt when the preview viewport is resized.
            # Qt's rich-text engine does not provide a dependable CSS flex/grid
            # layout, so UBE calculates a safe number of table columns itself.
            self._relationship_flow_record = None
            self._relationship_flow_forced = False
            self._relationship_flow_last_width = 0
            self._relationship_flow_refresh_pending = False

            # v2.0k: non-blocking loading notice.  Large Unity bundles can spend
            # several seconds in UnityPy decoding and tree construction.  Keep a
            # small modal notice visible and pump Qt events so Windows never has
            # to label UBE as "Not Responding" while legitimate work continues.
            self._loading_dialog = None
            self._loading_heading_label = None
            self._loading_detail_label = None

            # v2.0r: native mesh/group exports can spend a long time assembling
            # descendants, decoding textures and writing GLB/OBJ data.  Keep a
            # modal status notice alive and run the expensive writer off the Qt
            # GUI thread so Windows never presents a misleading Not Responding
            # state during a legitimate export.
            self._export_work_dialog = None
            self._export_work_heading_label = None
            self._export_work_detail_label = None

            # v2.4d: large AnimationClip previews can spend substantial time
            # resolving owners, decoding streamed curves, collecting renderers,
            # rebuilding materials and preparing CPU skinning.  Keep a clear,
            # stage-based notice visible without pretending that every vertex or
            # authored frame is a useful progress unit.
            self._animation_work_dialog = None
            self._animation_work_heading_label = None
            self._animation_work_detail_label = None
            self._animation_work_elapsed_label = None
            self._animation_work_started = 0.0


            # Catch mouse Back/Forward buttons globally while the window is active.
            # This makes relationship browsing feel like a web browser.
            QApplication.instance().installEventFilter(self)

            file_menu = self.menuBar().addMenu("File")
            open_action = QAction("Open Bundle...", self)
            open_action.triggered.connect(self.open_bundle)
            file_menu.addAction(open_action)

            open_serialized_action = QAction("Open Unity Serialized Assets...", self)
            open_serialized_action.triggered.connect(self.open_serialized_assets_file)
            file_menu.addAction(open_serialized_action)

            open_serialized_folder_action = QAction("Open Serialized Assets Folder...", self)
            open_serialized_folder_action.triggered.connect(self.open_serialized_assets_folder)
            file_menu.addAction(open_serialized_folder_action)

            open_folder_action = QAction("Open Folder / Project...", self)
            open_folder_action.triggered.connect(self.open_folder)
            file_menu.addAction(open_folder_action)

            self.recent_menu = file_menu.addMenu("Recent")
            self.refresh_recent_menu()

            self.return_project_action = QAction("Return to Source List", self)
            self.return_project_action.setShortcut("Alt+Left")
            self.return_project_action.triggered.connect(self.return_to_project_view)
            self.return_project_action.setEnabled(False)
            file_menu.addAction(self.return_project_action)

            view_menu = self.menuBar().addMenu("View")
            self.preview_focus_action = QAction("Toggle Preview Focus (` / ~ / F11 / Tab)", self)
            self.preview_focus_action.triggered.connect(self.toggle_preview_focus_mode)
            view_menu.addAction(self.preview_focus_action)

            self.preview_help_action = QAction("3D Preview Help (H)", self)
            self.preview_help_action.triggered.connect(self.show_3d_preview_help)
            view_menu.addAction(self.preview_help_action)

            self.selection_history_action = QAction("Selection History / Session Log...", self)
            self.selection_history_action.triggered.connect(self.show_selection_history_dialog)
            view_menu.addAction(self.selection_history_action)

            self.project_search_action = QAction("Project Search / PathID Lookup...", self)
            self.project_search_action.setShortcut("Ctrl+Shift+F")
            self.project_search_action.triggered.connect(self.show_project_search_dialog)
            view_menu.addAction(self.project_search_action)

            self.inspector_coverage_action = QAction("Inspector Coverage Report...", self)
            self.inspector_coverage_action.triggered.connect(self.show_inspector_coverage_report_dialog)
            view_menu.addAction(self.inspector_coverage_action)

            tree_columns_menu = view_menu.addMenu("Asset Tree Columns")
            self.show_kind_column_action = QAction("Show Kind", self)
            self.show_kind_column_action.setCheckable(True)
            self.show_kind_column_action.setChecked(self._read_bool_setting("tree_columns/show_kind", True))
            self.show_kind_column_action.toggled.connect(
                lambda visible: self.set_tree_column_visible(1, visible, "tree_columns/show_kind")
            )
            tree_columns_menu.addAction(self.show_kind_column_action)

            self.show_pathid_column_action = QAction("Show Path ID", self)
            self.show_pathid_column_action.setCheckable(True)
            self.show_pathid_column_action.setChecked(self._read_bool_setting("tree_columns/show_path_id", False))
            self.show_pathid_column_action.toggled.connect(
                lambda visible: self.set_tree_column_visible(2, visible, "tree_columns/show_path_id")
            )
            tree_columns_menu.addAction(self.show_pathid_column_action)

            self.show_comment_column_action = QAction("Show Comment Preview", self)
            self.show_comment_column_action.setCheckable(True)
            self.show_comment_column_action.setChecked(self._read_bool_setting("tree_columns/show_comment", True))
            self.show_comment_column_action.toggled.connect(
                lambda visible: self.set_tree_column_visible(3, visible, "tree_columns/show_comment")
            )
            tree_columns_menu.addAction(self.show_comment_column_action)

            nav = QToolBar("Navigation", self)
            self.nav_toolbar = nav
            nav.setMovable(False)
            self.addToolBar(nav)
            self.back_action = QAction("← Back", self)
            self.back_action.triggered.connect(self.go_back)
            self.back_action.setEnabled(False)
            nav.addAction(self.back_action)
            self.forward_action = QAction("Forward →", self)
            self.forward_action.triggered.connect(self.go_forward)
            self.forward_action.setEnabled(False)
            nav.addAction(self.forward_action)

            self.search = QLineEdit()
            self.search.setPlaceholderText("Search current tree...  (Ctrl+F style quick filter)")
            self.search.textChanged.connect(self.apply_tree_filter)

            self.tree = QTreeWidget()
            self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
            # Large Unity bundles can contain 100,000+ rows.  All asset-tree
            # rows use the same height, so tell Qt it does not need to measure
            # every item during layout/paint.  Disabling branch animations also
            # avoids expensive transitions when the root is first revealed.
            self.tree.setUniformRowHeights(True)
            self.tree.setAnimated(False)
            self.tree.setHeaderLabels(["Asset", "Kind", "Path ID", "Comment"])
            self.tree.itemSelectionChanged.connect(self.on_select)
            self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
            self.apply_tree_column_visibility()

            left = QWidget()
            self.left_panel = left
            left_layout = QVBoxLayout(left)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.addWidget(self.search)
            left_layout.addWidget(self.tree)

            self.info = QTextBrowser()
            self.info.setReadOnly(True)
            self.info.setOpenLinks(False)
            self.info.anchorClicked.connect(self.on_info_link_clicked)
            self.info.setContextMenuPolicy(Qt.CustomContextMenu)
            self.info.customContextMenuRequested.connect(self.show_info_context_menu)

            self.preview_stack = QStackedWidget()

            self.preview = QLabel("Open a .bundle file or a folder to begin")
            self.preview.setWordWrap(True)
            self.preview.setAlignment(Qt.AlignCenter)
            self.preview.setMinimumHeight(320)
            # v2.0n: a QLabel normally advertises its current pixmap dimensions
            # as a layout size hint.  Texture focus mode draws a window-sized
            # canvas, so that stale fullscreen size could force the right panel
            # wide and collapse the asset sidebar after returning.  Ignore the
            # pixmap size hint and let the splitter own the available geometry.
            self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.preview.setMinimumWidth(0)
            self.preview.setMouseTracking(True)
            self.preview.installEventFilter(self)

            self.preview_3d = Preview3DWidget()
            self.preview_3d.visibility_filter_changed_callback = self._animation_preview_visibility_changed

            ground_menu = view_menu.addMenu("Ground / Up Axis")
            self.ground_axis_actions = {}
            for axis, label, shortcut in (
                ("+Y", "+Y up / Unity default", "Ctrl+Y"),
                ("-Y", "-Y up", "Ctrl+Shift+Y"),
                ("+Z", "+Z up", "Ctrl+Z"),
                ("-Z", "-Z up", "Ctrl+Shift+Z"),
                ("+X", "+X up", "Ctrl+X"),
                ("-X", "-X up", "Ctrl+Shift+X"),
            ):
                action = QAction(label, self)
                action.setCheckable(True)
                action.setShortcut(shortcut)
                action.triggered.connect(lambda checked=False, a=axis: self.set_ground_up_axis(a))
                ground_menu.addAction(action)
                self.ground_axis_actions[axis] = action
            self._refresh_ground_axis_actions()

            self.audio_widget = QWidget()
            audio_layout = QVBoxLayout(self.audio_widget)
            self.audio_label = QLabel("Select an AudioClip")
            self.audio_label.setAlignment(Qt.AlignCenter)
            self.audio_label.setWordWrap(True)
            self.audio_label.setMinimumHeight(250)
            audio_layout.addWidget(self.audio_label)

            self.audio_subsong_row = QWidget()
            audio_subsong_layout = QHBoxLayout(self.audio_subsong_row)
            audio_subsong_layout.setContentsMargins(0, 0, 0, 0)
            self.audio_subsong_label = QLabel("FSB5 sample:")
            self.audio_subsong_combo = QComboBox()
            self.audio_subsong_combo.setMinimumWidth(260)
            audio_subsong_layout.addStretch(1)
            audio_subsong_layout.addWidget(self.audio_subsong_label)
            audio_subsong_layout.addWidget(self.audio_subsong_combo)
            audio_subsong_layout.addStretch(1)
            self.audio_subsong_row.setVisible(False)
            audio_layout.addWidget(self.audio_subsong_row)

            audio_buttons = QHBoxLayout()
            self.audio_play_button = QPushButton("Play")
            self.audio_stop_button = QPushButton("Stop")
            self.audio_decoder_button = QPushButton("Locate vgmstream...")
            self.audio_play_button.setEnabled(False)
            self.audio_stop_button.setEnabled(False)
            self.audio_decoder_button.setEnabled(False)
            audio_buttons.addStretch(1)
            audio_buttons.addWidget(self.audio_play_button)
            audio_buttons.addWidget(self.audio_stop_button)
            audio_buttons.addWidget(self.audio_decoder_button)
            audio_buttons.addStretch(1)
            audio_layout.addLayout(audio_buttons)

            self.audio_temp_dir = None
            self.audio_player = None
            self.audio_output = None
            self._audio_shutdown_done = False
            self.audio_preview_result = None
            self.audio_fsb_info = None
            self.audio_decoder_path = None
            self.audio_decoded_path = None
            self.audio_decoded_subsong = None
            self.audio_base_text = ""
            self.audio_subsong_combo.currentIndexChanged.connect(self.on_audio_subsong_changed)
            self.audio_play_button.clicked.connect(self.play_current_audio)
            self.audio_stop_button.clicked.connect(self.stop_current_audio)
            self.audio_decoder_button.clicked.connect(self.choose_audio_decoder)
            if QMediaPlayer is not None and QAudioOutput is not None:
                self.audio_player = QMediaPlayer(self)
                self.audio_output = QAudioOutput(self)
                self.audio_output.setVolume(0.75)
                self.audio_player.setAudioOutput(self.audio_output)

            self.object_view = QTextBrowser()
            self.object_view.setReadOnly(True)
            self.object_view.setOpenLinks(False)
            self.object_view.anchorClicked.connect(self.on_info_link_clicked)
            self.object_view.setHtml("<html><body style='font-family: Segoe UI, Arial; color:#ddd'>Select an Object, Transform, Mesh Link, Renderer, or Skinned Renderer.</body></html>")

            # v2.0g: compact clickable relationship diagram for assets that do
            # not have a useful 2D/3D preview of their own.  This intentionally
            # shows only the nearest useful layer in either direction so a large
            # Unity scene does not turn into an unreadable dependency graph.
            self.relationship_view = QTextBrowser()
            self.relationship_view.setReadOnly(True)
            self.relationship_view.setOpenLinks(False)
            self.relationship_view.anchorClicked.connect(self.on_info_link_clicked)
            self.relationship_view.installEventFilter(self)
            self.relationship_view.viewport().installEventFilter(self)
            self.relationship_view.setHtml(
                "<html><body style='font-family: Segoe UI, Arial; color:#ddd'>"
                "Select an AnimationClip, Animator, Controller, component, or other non-visual asset."
                "</body></html>"
            )

            self.preview_stack.addWidget(self.preview)
            self.preview_stack.addWidget(self.preview_3d)
            self.preview_stack.addWidget(self.audio_widget)
            self.preview_stack.addWidget(self.object_view)
            self.preview_stack.addWidget(self.relationship_view)

            # v2.2: first-pass AnimationClip Transform playback controls.
            # The controls live below the shared 3D viewer and remain hidden for
            # normal assets, so the established preview layout is unchanged.
            self.animation_controls = QWidget()
            animation_layout = QVBoxLayout(self.animation_controls)
            animation_layout.setContentsMargins(4, 2, 4, 2)
            self.animation_status_label = QLabel("Select an AnimationClip")
            self.animation_status_label.setWordWrap(True)
            animation_layout.addWidget(self.animation_status_label)

            animation_transport = QHBoxLayout()
            self.animation_play_button = QPushButton("Play")
            self.animation_reset_button = QPushButton("Reset pose")
            self.animation_export_glb_button = QPushButton("Export GLB")
            # v2.3l: these are transport controls, not dialog buttons.  Native
            # Qt button size hints include generous desktop-dialog padding,
            # which wastes a large amount of space at Windows display scaling.
            # Fixed compact widths keep the whole animation row toolbar-like.
            for button, width in (
                (self.animation_play_button, 44),
                (self.animation_reset_button, 70),
                (self.animation_export_glb_button, 86),
            ):
                button.setFixedWidth(width)
                button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                button.setStyleSheet("QPushButton { padding: 2px 5px; }")
            self.animation_play_button.setToolTip("Play or pause the active AnimationClip. Space bar toggles play/pause globally while an animation preview is ready.")
            self.animation_export_glb_button.setVisible(False)
            self.animation_export_glb_button.setToolTip(
                "Export the currently previewable rigid, skinned, or mixed rigid-plus-skinned animation as a self-contained animated GLB."
            )
            self.animation_loop_check = QCheckBox("Loop")
            self.animation_loop_check.setChecked(True)
            self.animation_in_place_check = QCheckBox("In place")
            self.animation_in_place_check.setChecked(False)
            self.animation_in_place_check.setToolTip(
                "Hold each detected world-motion controller at its authored first-frame position, "
                "rotation and scale. Internal bones, fins, wings and body motion continue normally. "
                "When enabled, the Limit control can isolate one short local motion cycle for "
                "looping and Animated GLB export."
            )
            self.animation_speed_combo = QComboBox()
            for speed_label, speed_value in (("0.25x", 0.25), ("0.5x", 0.5), ("1x", 1.0), ("1.5x", 1.5), ("2x", 2.0)):
                self.animation_speed_combo.addItem(speed_label, speed_value)
            self.animation_speed_combo.setCurrentIndex(2)
            # v2.3l: a fixed toolbar-sized combo is substantially narrower
            # than the Windows native size hint while still fitting "0.25×".
            self.animation_speed_combo.setFixedWidth(58)
            self.animation_speed_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.animation_speed_combo.setStyleSheet(
                "QComboBox { padding: 1px 0px 1px 5px; } "
                "QComboBox::drop-down { width: 0px; border: 0px; } "
                "QComboBox::down-arrow { image: none; }"
            )
            self.animation_duration_limit_spin = QDoubleSpinBox()
            self.animation_duration_limit_spin.setDecimals(3)
            self.animation_duration_limit_spin.setRange(0.001, 86400.0)
            self.animation_duration_limit_spin.setSingleStep(0.5)
            self.animation_duration_limit_spin.setSuffix(" s")
            self.animation_duration_limit_spin.setKeyboardTracking(False)
            # v2.3h: application-wide viewer hotkeys must never consume digits
            # while the user is editing this value.  Mark both the spin box and
            # its internal line editor because Qt may report either as focused.
            self.animation_duration_limit_spin.setProperty("ube_text_entry", True)
            try:
                self.animation_duration_limit_spin.lineEdit().setProperty("ube_text_entry", True)
            except Exception:
                pass
            self.animation_duration_limit_spin.setMinimumWidth(90)
            self.animation_duration_limit_spin.setMaximumWidth(108)
            self.animation_duration_limit_spin.setEnabled(False)
            self.animation_duration_limit_spin.setToolTip(
                "When In place is enabled, limit preview looping and Animated GLB export "
                "to the first N seconds of the clip. Use this to isolate one clean local "
                "motion cycle from a long world-travel animation."
            )
            self.animation_duration_full_button = QPushButton("Full")
            self.animation_duration_full_button.setFixedWidth(44)
            self.animation_duration_full_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.animation_duration_full_button.setStyleSheet("QPushButton { padding: 2px 4px; }")
            self.animation_duration_full_button.setEnabled(False)
            self.animation_duration_full_button.setToolTip(
                "Restore the preview/export duration to the complete AnimationClip."
            )
            self.animation_time_label = QLabel("0.000 / 0.000 s • 0/0")
            # v2.3n: keep the useful scrubber time/frame readout visible without
            # allowing long clip counts to resize the main window.  A fixed
            # toolbar-width label is stable; the full verbose value remains in
            # its tooltip.
            self.animation_time_label.setFixedWidth(205)
            self.animation_time_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            self.animation_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            animation_transport.setSpacing(4)
            animation_transport.addWidget(self.animation_play_button)
            animation_transport.addWidget(self.animation_reset_button)
            animation_transport.addWidget(self.animation_export_glb_button)
            animation_transport.addWidget(self.animation_loop_check)
            animation_transport.addWidget(self.animation_in_place_check)
            animation_transport.addWidget(QLabel("Speed:"))
            animation_transport.addWidget(self.animation_speed_combo)
            animation_transport.addWidget(QLabel("Limit:"))
            animation_transport.addWidget(self.animation_duration_limit_spin)
            animation_transport.addWidget(self.animation_duration_full_button)
            animation_transport.addStretch(1)
            animation_transport.addWidget(self.animation_time_label)
            animation_layout.addLayout(animation_transport)

            self.animation_slider = QSlider(Qt.Horizontal)
            # v2.3i: the slider is reconfigured to one integer step per
            # authored animation frame when a clip is loaded.  A temporary
            # one-step range keeps the empty state valid.
            self.animation_slider.setRange(0, 1)
            self.animation_slider.setSingleStep(1)
            self.animation_slider.setPageStep(1)
            self.animation_slider.setValue(0)
            animation_layout.addWidget(self.animation_slider)
            self.animation_controls.setVisible(False)

            self.animation_timer = QTimer(self)
            self.animation_timer.setInterval(16)
            self.animation_timer.timeout.connect(self._animation_tick)
            self.animation_play_button.clicked.connect(self._animation_toggle_play)
            self.animation_reset_button.clicked.connect(self._animation_reset_pose)
            self.animation_export_glb_button.clicked.connect(self._animation_export_animated_glb)
            self.animation_slider.valueChanged.connect(self._animation_slider_changed)
            self.animation_in_place_check.toggled.connect(self._animation_in_place_toggled)
            self.animation_duration_limit_spin.valueChanged.connect(self._animation_duration_limit_changed)
            self.animation_duration_full_button.clicked.connect(self._animation_restore_full_duration)
            self.animation_clip_record = None
            self.animation_clip_data = None
            self.animation_duration = 0.0
            self.animation_current_time = 0.0
            self.animation_last_clock = 0.0
            self.animation_playback_time = 0.0
            self.animation_tracks = []
            self.animation_root_transform = None
            self.animation_render_items = []
            self.animation_transform_by_key = {}
            self.animation_skinning_descriptors = []
            self.animation_constraint_descriptors = []
            self.animation_export_eligible = False
            self.animation_export_reason = ""
            self.animation_export_warnings = []
            self.animation_unsupported_property_bindings = 0
            self.animation_export_sample_rate = 0.0
            self.animation_export_context = {}
            self.animation_status_base_text = ""
            self.animation_target_instance_summary = ""
            self.animation_render_variant_info = {}
            self.animation_root_lock_keys = set()
            # First-frame position/scale values for each in-place locked root.
            # In-place playback freezes to these authored values rather than the
            # serialized/rest pose, avoiding a large frame-zero teleport.
            self.animation_in_place_baseline = {}
            # v2.3m: effective world-space anchor used by In place.  Local
            # channel locking remains only as a defensive fallback when no
            # render-branch anchor can be established.
            self.animation_in_place_anchor_key = None
            self.animation_in_place_anchor_transform = None
            self.animation_in_place_anchor_name = ""
            self.animation_in_place_anchor_baseline_matrix = None
            # v2.3n: final rendered-geometry fallback anchor.  Some imported
            # controller rigs duplicate/flatten motion across several branches,
            # so no single Transform reliably represents what the user sees.
            # This anchor is measured after CPU skinning and final renderer
            # transforms, guaranteeing that In place holds the visible asset.
            self.animation_in_place_preview_center = None
            self.animation_in_place_preview_child_index = None
            self.animation_root_motion_summary = ""
            self.animation_slider_updating = False

            self.export_button = QPushButton("Export Selected Asset...")
            self.export_button.clicked.connect(self.export_selected_asset)
            self.export_button.setEnabled(False)

            right = QWidget()
            self.right_panel = right
            layout = QVBoxLayout(right)
            layout.addWidget(self.preview_stack)
            layout.addWidget(self.animation_controls)
            layout.addWidget(self.export_button)
            layout.addWidget(self.info)

            splitter = QSplitter()
            self.splitter = splitter
            splitter.addWidget(left)
            splitter.addWidget(right)
            splitter.setSizes([470, 780])
            self.setCentralWidget(splitter)


        def _current_ground_up_axis(self) -> str:
            try:
                axis = self.preview_3d.get_ground_up_axis()
            except Exception:
                axis = "+Y"
            return axis if axis in ("+X", "-X", "+Y", "-Y", "+Z", "-Z") else "+Y"

        def _refresh_ground_axis_actions(self) -> None:
            try:
                current = self._current_ground_up_axis()
                for axis, action in getattr(self, "ground_axis_actions", {}).items():
                    action.setChecked(axis == current)
            except Exception:
                pass

        def set_ground_up_axis(self, axis: str) -> str:
            """Set simple session-only authored-up axis for 3D preview and mesh export."""
            if not hasattr(self, "preview_3d") or not hasattr(self.preview_3d, "set_ground_up_axis"):
                return "Ground/up axis unavailable"
            label = self.preview_3d.set_ground_up_axis(axis)
            self._refresh_ground_axis_actions()
            try:
                self.statusBar().showMessage(f"3D preview/export: {label}", 3500)
            except Exception:
                pass
            return label



        # ------------------------------------------------------------------
        # v1.8o: Inspector Coverage Report.
        # ------------------------------------------------------------------
        def _coverage_catalog(self) -> dict[str, dict[str, str]]:
            """Static self-audit table for what UBE currently understands.

            This is intentionally human/educational rather than a strict test
            suite.  It tells users which Unity object families have specialised
            inspectors, previews, export, or only raw/basic coverage.
            """
            specialised = {
                "GameObject": ("Strong", "Object hierarchy, components, owner links, preview context, motion-source investigation, references/used-by.", "3D/group", "OBJ/GLB when renderable"),
                "Transform": ("Strong", "Position/rotation/scale, parent/child hierarchy, owner GameObject links.", "3D via owner", "OBJ/GLB when renderable owner"),
                "Mesh": ("Strong", "Vertices/faces/submeshes/UVs/bounds plus material/renderer relationship hints.", "3D", "OBJ/GLB"),
                "MeshFilter": ("Strong", "Mesh link, owning GameObject, renderer pairing.", "3D via mesh/owner", "OBJ/GLB"),
                "MeshRenderer": ("Strong", "Materials, light/shadow flags, owning GameObject, texture/material links and shader-motion clues.", "3D via owner", "OBJ/GLB"),
                "SkinnedMeshRenderer": ("Strong", "Skinned mesh/material links, owner object, bone list and motion-source explanation.", "3D static pose", "OBJ/GLB static"),
                "Material": ("Strong", "Shader/material properties, texture slots, transparent/glass/water/glow intent and procedural-motion clues.", "intent card", "-"),
                "Shader": ("Strong", "Shader metadata, parsed names/tags/properties, visual intent classification.", "intent card", "-"),
                "Texture2D": ("Strong", "Size/format/mips/memory, usage finder, atlas/UV region finder, zoom/pan/manual region search.", "image", "PNG"),
                "Texture2DArray": ("Strong", "Array/slice format details and export support.", "slice/contact sheet", "PNG slices"),
                "Cubemap": ("Strong", "Six-face/environment texture explanation, size/format/mips/stream data.", "cubemap/contact sheet", "PNG/contact sheet"),
                "Sprite": ("Strong", "Rect/pivot/PPU/border/tight mesh/texture links.", "2D", "PNG"),
                "SpriteRenderer": ("Strong", "Sprite/material/color/flip/draw mode and external sprite resolver.", "2D/owner", "PNG"),
                "SpriteMask": ("Strong", "Sprite mask shape, alpha cutoff and sorting range; explains 2D stencil masking.", "symbolic/mask", "-"),
                "LineRenderer": ("Strong", "Generated line/ribbon renderer: materials, width, positions, alignment and texture mode.", "symbolic line", "-"),
                "TrailRenderer": ("Strong", "Generated trail/ribbon renderer: material, width, lifetime, vertex distance and trail behaviour.", "symbolic trail", "-"),
                "Rigidbody": ("Strong", "Physics body: mass, gravity, kinematic state, damping, collision mode and constraints.", "symbolic physics", "-"),
                "SphereCollider": ("Strong", "Primitive sphere collider shape, trigger/material/layer settings.", "symbolic collider", "-"),
                "CapsuleCollider": ("Strong", "Primitive capsule collider shape, radius/height/direction, trigger/material/layer settings.", "symbolic collider", "-"),
                "MeshCollider": ("Strong", "Mesh-based collider reference, convex/cooking/trigger/material settings.", "symbolic collider", "-"),
                "PhysicMaterial": ("Strong", "Friction/bounce material used by colliders.", "-", "-"),
                "TextAsset": ("Strong", "Readable text/JSON/config preview or binary hex preview, plus data-size hints.", "text preview", "-"),
                "PlayableDirector": ("Strong", "Timeline/Playable controller: playable asset, playback mode, update mode and scene bindings.", "timeline context", "-"),
                "NavMeshData": ("Strong", "Baked AI/pathfinding walking map: tiles, build settings, bounds/raw data and travel-surface explanation.", "symbolic navmesh", "-"),
                "NavMeshSettings": ("Strong", "Scene/source navigation settings: NavMeshData references, agent/build settings and area costs where exposed.", "symbolic navmesh", "-"),
                "NavMeshProjectSettings": ("Strong", "Project-wide navigation settings: agent types, area names/costs and build defaults where exposed.", "symbolic navmesh", "-"),
                "AudioClip": ("Strong", "Clip length/frequency/channels/compression/load type/streaming hints.", "audio player", "audio file"),
                "AudioSource": ("Strong", "Assigned AudioClip, playback/loop/volume/pitch, mixer routing, 2D/3D spatial settings, custom curves, owner and clickable clip links.", "owner/context", "AudioClip via link"),
                "AudioMixerController": ("Strong", "Master/output routing, groups, snapshots, exposed parameters and suspend/update settings.", "relationship flow", "-"),
                "AudioMixerGroupController": ("Strong", "Mixer hierarchy, parameter IDs, effect chain and reverse links to every routed AudioSource.", "relationship flow", "-"),
                "AudioMixerSnapshotController": ("Strong", "Stored mixer values, transition overrides and owning mixer relationship.", "relationship flow", "-"),
                "AudioMixerEffectController": ("Good", "Effect-chain owner, send target, bypass/enabled state and exposed parameters where available.", "relationship flow", "-"),
                "Animation": ("Strong", "Legacy Animation component: clips, default clip, play automatically, wrap/culling bridge.", "-", "-"),
                "AnimationClip": ("Strong", "Timeline/storage, binding-path resolver, rigid Transform playback and CPU bone skinning.", "3D timeline for Transform + skinned curves", "Animated GLB from the resolved preview hierarchy; unsupported non-Transform properties are reported and omitted"),
                "Animator": ("Strong", "Modern Mecanim component: controller/avatar/settings, resolved clips and motion-source summary.", "-", "HTML report"),
                "AnimatorController": ("Strong", "Parameters, layers, states, motions/clips, state-machine overview.", "-", "-"),
                "AnimatorOverrideController": ("Strong", "Controller override mapping where exposed by UnityPy.", "-", "-"),
                "LODGroup": ("Strong", "LOD count, thresholds, renderers, triangles/verts, material LOD preview stepping.", "3D LOD", "-"),
                "Camera": ("Strong", "Lens/FOV/projection/clip/clear flags plus frustum/lens visual.", "frustum", "-"),
                "Light": ("Strong", "Type/color/intensity/range/spot/shadows/cookie/culling mask.", "symbolic light", "-"),
                "ReflectionProbe": ("Strong", "Probe mode/box/importance/culling/clear settings with probe visual.", "symbolic probe", "-"),
                "BoxCollider": ("Strong", "Center/size/trigger/material and CAD-style collider volume preview.", "wire box", "-"),
                "ParticleSystem": ("Strong", "Main/emission/shape/renderer relationship and symbolic particle preview.", "symbolic particles", "-"),
                "ParticleSystemRenderer": ("Strong", "Renderer/material/mesh/trail/sort hints and paired ParticleSystem lookup.", "symbolic particles", "-"),
                "LightProbeGroup": ("Strong", "Probe positions/counts and educational light-probe explanation.", "symbolic", "-"),
                "LightingSettings": ("Strong", "Scene lighting/bake/global illumination settings where exposed.", "-", "-"),
                "LightmapSettings": ("Strong", "Lightmap/probe references and baked-lighting explanation.", "-", "-"),
                "RectTransform": ("Strong", "Anchors, pivot, size delta, anchored position and UI layout visual.", "2D UI visual", "-"),
                "Canvas": ("Strong", "Render mode, camera, scaling/sorting/pixel settings.", "UI context", "-"),
                "CanvasGroup": ("Strong", "Alpha/interactable/block raycasts/ignore parent groups.", "-", "-"),
                "CanvasRenderer": ("Strong", "UI renderer/culling/material/texture hints.", "-", "-"),
                "MonoBehaviour": ("Good", "Script/class/assembly owner and readable fields/references/strings.", "owner preview", "-"),
            }

            partial = {
                "Animator": ("Basic", "Component can be reached from GameObject; controller/avatar/runtime settings inspector is a future target.", "-", "-"),
                "Avatar": ("Good", "Animation rig mapping inspector: role hints, exposed skeleton/human data, relationships and symbolic skeleton preview.", "skeleton card", "-"),
                "Rigidbody2D": ("Basic", "Detected through component/raw fields; 2D physics inspector is a future target.", "-", "-"),
                "CharacterController": ("Basic", "Detected through component/raw fields; controller/capsule visual is a future target.", "-", "-"),
                "AudioListener": ("Basic", "Detected through component/raw fields; listener/camera audio context is a future target.", "-", "-"),
                "Joint": ("Basic", "Detected through raw fields; joint visual/limits are future work.", "-", "-"),
                "HingeJoint": ("Basic", "Detected through raw fields; joint visual/limits are future work.", "-", "-"),
                "FixedJoint": ("Basic", "Detected through raw fields; joint visual/limits are future work.", "-", "-"),
                "SpringJoint": ("Basic", "Detected through raw fields; joint visual/limits are future work.", "-", "-"),
                "ConfigurableJoint": ("Basic", "Detected through raw fields; joint visual/limits are future work.", "-", "-"),
                "TerrainData": ("Basic", "Recognised as terrain data; heightmap/splat/tree inspector is future work.", "-", "-"),
                "Terrain": ("Basic", "Recognised as terrain component; terrain visual is future work.", "-", "-"),
                "VideoClip": ("Basic", "Recognised as media asset; video metadata/export is future work.", "-", "-"),
                "TimelineAsset": ("Basic", "Recognised as Timeline asset; track/clip overview is future work.", "-", "-"),
                "Font": ("Good", "Font name/data/metrics/glyph table plus sample preview; atlas/material links where exposed.", "sample card", "-"),
                "TMP_FontAsset": ("Basic", "TextMeshPro font asset recognised; first-pass font/sample card and raw exposed fields where available.", "sample card", "-"),
                "RenderTexture": ("Basic", "Recognised render target texture; preview depends on stored data being available.", "-", "-"),
                "Texture3D": ("Basic", "Recognised 3D/volume texture; slice preview is future work.", "-", "-"),
                "ComputeShader": ("Basic", "Recognised shader/program asset; static metadata only.", "-", "-"),
                "ShaderVariantCollection": ("Basic", "Recognised shader variant asset; variant list overview is future work.", "-", "-"),
                "Script": ("Basic", "Script object is listed and linked where referenced; source code is usually not present in Unity bundles.", "-", "-"),
                "MonoScript": ("Basic", "Script metadata/source reference; source code is usually not present in Unity bundles.", "-", "-"),
            }

            out = {}
            for k, v in specialised.items():
                out[k] = {
                    "level": v[0],
                    "inspector": v[1],
                    "preview": v[2],
                    "export": v[3],
                }
            for k, v in partial.items():
                out[k] = {
                    "level": v[0],
                    "inspector": v[1],
                    "preview": v[2],
                    "export": v[3],
                }
            return out

        def _coverage_level_order(self, level: str) -> int:
            return {"Strong": 0, "Good": 1, "Basic": 2, "Raw": 3}.get(str(level), 4)

        def _coverage_rows(self) -> list[dict]:
            idx = getattr(self, "bundle_index", None)
            if idx is None:
                return []
            catalog = self._coverage_catalog()
            rows = []
            for type_name, records in sorted(getattr(idx, "objects_by_type", {}).items(), key=lambda kv: kv[0].lower()):
                info = catalog.get(type_name)
                if info is None:
                    info = {
                        "level": "Raw",
                        "inspector": "No specialised inspector yet. UBE will show the asset in the tree and generic readable fields where UnityPy exposes them.",
                        "preview": "-",
                        "export": "-",
                    }
                rows.append({
                    "type": str(type_name),
                    "friendly": friendly_type_name(type_name),
                    "count": int(len(records)),
                    "level": info.get("level", "Raw"),
                    "inspector": info.get("inspector", ""),
                    "preview": info.get("preview", "-"),
                    "export": info.get("export", "-"),
                })
            rows.sort(key=lambda r: (self._coverage_level_order(r["level"]), str(r["friendly"]).lower()))
            return rows

        def _coverage_summary(self, rows: list[dict]) -> dict:
            total_objects = sum(int(r.get("count", 0)) for r in rows)
            total_types = len(rows)
            by_level: dict[str, int] = {}
            type_by_level: dict[str, int] = {}
            for r in rows:
                level = str(r.get("level", "Raw"))
                by_level[level] = by_level.get(level, 0) + int(r.get("count", 0))
                type_by_level[level] = type_by_level.get(level, 0) + 1
            return {
                "total_objects": total_objects,
                "total_types": total_types,
                "by_level": by_level,
                "type_by_level": type_by_level,
            }

        def _coverage_future_targets(self, rows: list[dict]) -> list[str]:
            present = {str(r.get("type", "")): int(r.get("count", 0)) for r in rows}
            target_groups = [
                (("Animator", "Avatar"), "Animator/Avatar component bridge"),
                (("Rigidbody2D", "CharacterController"), "2D physics / character controller inspector"),
                (("HingeJoint", "FixedJoint", "SpringJoint", "ConfigurableJoint", "Joint"), "Joint/constraint visual inspector"),
                (("Terrain", "TerrainData"), "Terrain/heightmap/splat inspector"),
                (("VideoClip", "TimelineAsset"), "Video/Timeline asset inspector"),
                (("Font", "TMP_FontAsset"), "Font/TextMeshPro atlas inspector"),
                (("RenderTexture", "Texture3D"), "RenderTexture/Texture3D preview"),
            ]
            out = []
            for names, label in target_groups:
                count = sum(present.get(n, 0) for n in names)
                if count:
                    out.append(f"{label}: {count:,} object(s)")
            return out[:8]

        def _coverage_html(self) -> str:
            rows = self._coverage_rows()
            if not rows:
                return (
                    "<html><body style='font-family: Segoe UI, Arial; color:#eee;'>"
                    "<h2>Inspector Coverage Report</h2>"
                    "<p>No bundle is open.</p>"
                    "</body></html>"
                )
            summary = self._coverage_summary(rows)
            idx = getattr(self, "bundle_index", None)
            bundle_name = escape(Path(getattr(idx, "path", "")).name if idx is not None else "-")
            total_objects = int(summary["total_objects"])
            total_types = int(summary["total_types"])
            strong_count = int(summary["by_level"].get("Strong", 0)) + int(summary["by_level"].get("Good", 0))
            strong_types = int(summary["type_by_level"].get("Strong", 0)) + int(summary["type_by_level"].get("Good", 0))
            pct_objects = (100.0 * strong_count / total_objects) if total_objects else 0.0
            pct_types = (100.0 * strong_types / total_types) if total_types else 0.0

            cards = []
            for level in ("Strong", "Good", "Basic", "Raw"):
                obj_count = int(summary["by_level"].get(level, 0))
                type_count = int(summary["type_by_level"].get(level, 0))
                cards.append(
                    "<div class='card'>"
                    f"<div class='cardnum'>{obj_count:,}</div>"
                    f"<div>{escape(level)} objects</div>"
                    f"<div class='muted'>{type_count:,} type(s)</div>"
                    "</div>"
                )

            future = self._coverage_future_targets(rows)
            future_html = ""
            if future:
                future_html = (
                    "<h3>Possible next useful targets found in this bundle</h3>"
                    "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in future) + "</ul>"
                )

            row_html = []
            level_class = {"Strong": "strong", "Good": "good", "Basic": "basic", "Raw": "raw"}
            for r in rows:
                level = str(r.get("level", "Raw"))
                cls = level_class.get(level, "raw")
                row_html.append(
                    "<tr>"
                    f"<td>{escape(str(r.get('friendly', r.get('type', ''))))}<br><span class='muted'>{escape(str(r.get('type', '')))}</span></td>"
                    f"<td class='num'>{int(r.get('count', 0)):,}</td>"
                    f"<td><span class='pill {cls}'>{escape(level)}</span></td>"
                    f"<td>{escape(str(r.get('inspector', '')))}</td>"
                    f"<td>{escape(str(r.get('preview', '-')))}</td>"
                    f"<td>{escape(str(r.get('export', '-')))}</td>"
                    "</tr>"
                )

            return (
                "<html><body style='font-family: Segoe UI, Arial, sans-serif; font-size:10pt; color:#eee;'>"
                "<style>"
                "a{color:#8ecbff;text-decoration:none;} .muted{color:#aaa;}"
                ".cards{display:flex; gap:10px; margin:10px 0 14px 0;}"
                ".card{border:1px solid #444; background:#252525; padding:8px 12px; min-width:120px;}"
                ".cardnum{font-size:18pt; font-weight:bold; color:#fff;}"
                "table{border-collapse:collapse;width:100%;} th,td{border:1px solid #444;padding:6px;vertical-align:top;}"
                "th{background:#303030;color:#fff;} tr:nth-child(even){background:#252525;}"
                ".num{text-align:right; white-space:nowrap;}"
                ".pill{display:inline-block; padding:2px 8px; border-radius:10px; font-weight:bold;}"
                ".strong{background:#174c2a;color:#b8ffc9;} .good{background:#204a70;color:#b9e2ff;}"
                ".basic{background:#5a4b1f;color:#ffe39d;} .raw{background:#5a2b2b;color:#ffc2c2;}"
                "</style>"
                "<h2>🧭 Inspector Coverage Report</h2>"
                f"<p><b>Bundle:</b> {bundle_name}<br>"
                f"<b>Specialised/good coverage:</b> {strong_count:,} / {total_objects:,} objects ({pct_objects:.1f}%), "
                f"{strong_types:,} / {total_types:,} asset types ({pct_types:.1f}%).</p>"
                "<p class='muted'>Object percentages can be misleading because GameObject/Transform counts are huge. "
                "The type-level view is usually a better guide for what UBE still needs.</p>"
                "<div class='cards'>" + "".join(cards) + "</div>"
                + future_html +
                "<h3>Coverage by asset type in this bundle</h3>"
                "<table>"
                "<tr><th>Asset type</th><th>Count</th><th>Coverage</th><th>What UBE explains</th><th>Preview</th><th>Export</th></tr>"
                + "".join(row_html) +
                "</table>"
                "<p class='muted'>Strong = specialised inspector/links/explanation. Good = useful field explorer/context. "
                "Basic = recognised but not deeply visualised yet. Raw = generic fallback only.</p>"
                "</body></html>"
            )

        def _coverage_tsv(self) -> str:
            fields = ["type", "friendly", "count", "coverage", "inspector", "preview", "export"]
            lines = ["\t".join(fields)]
            for r in self._coverage_rows():
                vals = [
                    str(r.get("type", "")),
                    str(r.get("friendly", "")),
                    str(r.get("count", "")),
                    str(r.get("level", "")),
                    str(r.get("inspector", "")),
                    str(r.get("preview", "")),
                    str(r.get("export", "")),
                ]
                vals = [v.replace("\t", " ").replace("\r", " ").replace("\n", " ") for v in vals]
                lines.append("\t".join(vals))
            return "\n".join(lines) + "\n"

        def show_inspector_coverage_report_dialog(self):
            if not getattr(self, "bundle_index", None):
                QMessageBox.information(self, "Inspector Coverage Report", "Open a bundle first.")
                return

            dlg = QDialog(self)
            dlg.setWindowTitle("UBE Inspector Coverage Report")
            dlg.resize(1120, 720)
            layout = QVBoxLayout(dlg)
            browser = QTextBrowser(dlg)
            browser.setOpenLinks(False)
            browser.setHtml(self._coverage_html())
            layout.addWidget(browser)

            buttons = QHBoxLayout()
            copy_btn = QPushButton("Copy TSV")
            export_btn = QPushButton("Export TSV...")
            close_btn = QPushButton("Close")
            buttons.addWidget(copy_btn)
            buttons.addWidget(export_btn)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            layout.addLayout(buttons)

            def copy_tsv():
                QApplication.clipboard().setText(self._coverage_tsv())
                self.statusBar().showMessage("Inspector coverage copied as TSV", 1800)

            def export_tsv():
                default = "UBE_inspector_coverage.tsv"
                try:
                    if getattr(self, "bundle_index", None) is not None:
                        default = f"{Path(self.bundle_index.path).stem}_inspector_coverage.tsv"
                except Exception:
                    pass
                path, _ = QFileDialog.getSaveFileName(self, "Export Inspector Coverage TSV", default, "TSV files (*.tsv);;All files (*.*)")
                if not path:
                    return
                try:
                    Path(path).write_text(self._coverage_tsv(), encoding="utf-8")
                    self.statusBar().showMessage(f"Inspector coverage exported: {path}", 2500)
                except Exception as exc:
                    QMessageBox.warning(self, "Export Inspector Coverage", f"Could not export inspector coverage:\n{exc}")

            copy_btn.clicked.connect(copy_tsv)
            export_btn.clicked.connect(export_tsv)
            close_btn.clicked.connect(dlg.accept)
            dlg.exec()



        def _capture_texture_focus_state(self):
            """Snapshot the texture region centred in the current viewport.

            Texture zoom is stored as a multiplier of fit-to-window.  When the
            panel becomes much larger or smaller, retaining only that number can
            move the user's close-up away from the point they were inspecting.
            Preserve both the zoom multiplier and the texture pixel under the
            viewport centre, then restore them after Qt finishes relaying out the
            focused/unfocused interface.
            """
            if not self._texture_preview_active():
                return None
            try:
                x0, y0, scale = self._texture_view_origin_and_scale()
                if scale <= 0.0:
                    return None
                centre_x = float(self.preview.width()) * 0.5
                centre_y = float(self.preview.height()) * 0.5
                return {
                    "zoom": max(1.0, float(self.texture_preview_zoom)),
                    "base_x": (centre_x - x0) / scale,
                    "base_y": (centre_y - y0) / scale,
                }
            except Exception:
                return None

        def _restore_texture_focus_state(self, state):
            if not state or not self._texture_preview_active():
                self._texture_focus_restore_pending = False
                return
            try:
                # Keep the same fit-relative close-up, but never allow the
                # decoded preview to be enlarged beyond one screen pixel per
                # preview pixel.  This prevents fullscreen from implying detail
                # which is not present in the texture preview.
                zoom = max(1.0, min(float(state.get("zoom", 1.0)), self._texture_max_zoom()))
                self.texture_preview_zoom = zoom
                fit = self._texture_fit_scale()
                scale = fit * zoom
                base_w = float(self.texture_preview_base_pixmap.width())
                base_h = float(self.texture_preview_base_pixmap.height())
                draw_w = base_w * scale
                draw_h = base_h * scale
                view_w = float(self.preview.width())
                view_h = float(self.preview.height())
                centred_x = (view_w - draw_w) * 0.5
                centred_y = (view_h - draw_h) * 0.5
                desired_x0 = view_w * 0.5 - float(state.get("base_x", base_w * 0.5)) * scale
                desired_y0 = view_h * 0.5 - float(state.get("base_y", base_h * 0.5)) * scale
                self.texture_preview_pan = QPointF(desired_x0 - centred_x, desired_y0 - centred_y)
                self._clamp_texture_pan()
                self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            except Exception:
                pass
            self._texture_focus_restore_pending = False

        def _restore_preview_focus_layout(self):
            """Restore splitter geometry after hidden panels re-enter layout.

            Qt may not honour setSizes() while a splitter child is still hidden
            or before its size hints have settled.  Texture previews make this
            especially visible because their focus canvas was window-sized.
            Run this after the event loop has relaid out the normal interface.
            """
            try:
                sizes = list(self.preview_focus_prev_splitter_sizes or [])
                if sizes and hasattr(self, "splitter"):
                    self.splitter.setSizes(sizes)
            except Exception:
                pass

        def toggle_preview_focus_mode(self):
            """Toggle an Adobe-style focused preview panel.

            This maximises the current preview inside the UBE window.  It does
            not change the selected asset, mesh orientation, export data, or the
            OS-level window state; it simply hides the tree/inspector chrome so
            the visual preview can breathe.  Texture previews retain their zoom
            and centred inspection point across the layout change.
            """
            texture_state = self._capture_texture_focus_state()
            try:
                if not self.preview_focus_mode:
                    if hasattr(self, "splitter"):
                        self.preview_focus_prev_splitter_sizes = self.splitter.sizes()
                    self.preview_focus_mode = True
                    self.left_panel.setVisible(False)
                    self.info.setVisible(False)
                    self.export_button.setVisible(False)
                    self.menuBar().setVisible(False)
                    if hasattr(self, "nav_toolbar"):
                        self.nav_toolbar.setVisible(False)
                    self.preview_stack.setMinimumHeight(0)
                    if texture_state:
                        self.statusBar().showMessage(
                            "Texture focus mode — Tab / ` / ~ / F11 returns; native preview is capped at 100%",
                            4500,
                        )
                    else:
                        self.statusBar().showMessage("Preview focus mode — press ` / ~ / F11 to return", 3500)
                else:
                    self.preview_focus_mode = False
                    self.left_panel.setVisible(True)
                    self.info.setVisible(True)
                    self.export_button.setVisible(True)
                    self.menuBar().setVisible(True)
                    if hasattr(self, "nav_toolbar"):
                        self.nav_toolbar.setVisible(True)
                    # Restore after the hidden left panel and inspector have
                    # actually re-entered the layout.  Repeating the same saved
                    # sizes is harmless and catches Windows/Qt geometry settling
                    # over more than one event-loop turn.
                    QTimer.singleShot(0, self._restore_preview_focus_layout)
                    QTimer.singleShot(50, self._restore_preview_focus_layout)
                    QTimer.singleShot(140, self._restore_preview_focus_layout)
                    self.statusBar().showMessage("Preview focus mode off", 1500)

                if texture_state and not self._texture_focus_restore_pending:
                    self._texture_focus_restore_pending = True
                    # Restore the viewed texture region after the normal splitter
                    # geometry is back, then redraw once more after it settles.
                    QTimer.singleShot(10, lambda st=texture_state: self._restore_texture_focus_state(st))
                    QTimer.singleShot(80, lambda st=texture_state: self._restore_texture_focus_state(st))
                    if not self.preview_focus_mode:
                        QTimer.singleShot(170, lambda st=texture_state: self._restore_texture_focus_state(st))
            except Exception as exc:
                self._texture_focus_restore_pending = False
                QMessageBox.warning(self, "Preview Focus", f"Could not toggle preview focus mode:\n{exc}")


        def _selection_history_bundle_path(self) -> str:
            try:
                if self.bundle_index is not None and getattr(self.bundle_index, "path", None) is not None:
                    return str(self.bundle_index.path)
            except Exception:
                pass
            return ""

        def _selection_history_owner(self, rec) -> tuple[str, str]:
            """Return owning GameObject name/path_id for component-style records."""
            try:
                go_rec = self._ov_owning_gameobject(rec) if getattr(rec, "type_name", "") != "GameObject" else rec
                if go_rec is not None:
                    return (str(getattr(go_rec, "name", "") or f"GameObject_{getattr(go_rec, 'path_id', '')}"), str(getattr(go_rec, "path_id", "")))
            except Exception:
                pass
            return ("", "")

        def _selection_history_hierarchy_path(self, rec, max_depth: int = 12) -> str:
            """Best-effort owner hierarchy: Root / Parent / Object.

            This is intentionally lightweight.  It only walks the currently
            loaded bundle's Transform parent chain and quietly falls back when
            UnityPy does not expose enough data.
            """
            try:
                go_rec = self._ov_owning_gameobject(rec) if getattr(rec, "type_name", "") != "GameObject" else rec
                if go_rec is None:
                    return ""
                names = [str(getattr(go_rec, "name", "") or f"GameObject_{getattr(go_rec, 'path_id', '')}")]
                tr = self._ov_transform_for_gameobject(go_rec)
                depth = 0
                seen = set()
                while tr is not None and depth < max_depth:
                    if getattr(tr, "path_id", None) in seen:
                        break
                    seen.add(getattr(tr, "path_id", None))
                    data = self._ov_read(tr)
                    parent_pptr = self._ov_get(data, "m_Father", "father", default=None) if data is not None else None
                    parent_tr = self._ov_resolve(parent_pptr) if parent_pptr is not None else None
                    if parent_tr is None:
                        break
                    parent_go = self._ov_gameobject_for_transform(parent_tr)
                    if parent_go is None:
                        break
                    names.append(str(getattr(parent_go, "name", "") or f"GameObject_{getattr(parent_go, 'path_id', '')}"))
                    tr = parent_tr
                    depth += 1
                names.reverse()
                return " / ".join(names)
            except Exception:
                return ""

        def _selection_history_entry_for_record(self, rec) -> dict:
            owner_name, owner_pid = self._selection_history_owner(rec)
            return {
                "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bundle": self._selection_history_bundle_path(),
                "asset_name": str(getattr(rec, "name", "") or ""),
                "type": str(getattr(rec, "type_name", "") or ""),
                "path_id": str(getattr(rec, "path_id", "") or ""),
                "owner_name": owner_name,
                "owner_path_id": owner_pid,
                "hierarchy": self._selection_history_hierarchy_path(rec),
            }

        def _append_selection_history_file(self, entry: dict):
            """Append selection history to a local TSV so screenshots can be traced later."""
            try:
                self.selection_history_file.parent.mkdir(parents=True, exist_ok=True)
                exists = self.selection_history_file.exists()
                fields = ["timestamp", "bundle", "asset_name", "type", "path_id", "owner_name", "owner_path_id", "hierarchy"]
                with self.selection_history_file.open("a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
                    if not exists:
                        w.writeheader()
                    w.writerow({k: entry.get(k, "") for k in fields})
            except Exception:
                # History is helpful, not mission-critical. Never let it break browsing.
                pass

        def record_selection_history(self, rec):
            if rec is None:
                return
            try:
                entry = self._selection_history_entry_for_record(rec)
                # Avoid spamming duplicates when the inspector refreshes the same asset.
                if self.selection_history_log:
                    last = self.selection_history_log[-1]
                    if last.get("bundle") == entry.get("bundle") and last.get("path_id") == entry.get("path_id"):
                        return
                self.selection_history_log.append(entry)
                if len(self.selection_history_log) > self.selection_history_max:
                    self.selection_history_log = self.selection_history_log[-self.selection_history_max:]
                self._append_selection_history_file(entry)
            except Exception:
                pass

        def _selection_history_html(self) -> str:
            rows = []
            for idx, entry in reversed(list(enumerate(self.selection_history_log))):
                bundle_name = Path(entry.get("bundle", "")).name if entry.get("bundle") else "-"
                asset_name = entry.get("asset_name", "") or "-"
                type_name = friendly_type_name(entry.get("type", "")) if entry.get("type") else "-"
                path_id = entry.get("path_id", "") or "-"
                owner = entry.get("owner_name", "") or "-"
                hierarchy = entry.get("hierarchy", "") or "-"
                rows.append(
                    "<tr>"
                    f"<td>{escape(entry.get('timestamp', ''))}</td>"
                    f"<td>{escape(bundle_name)}</td>"
                    f"<td><a href='ube://history/{idx}'>{escape(asset_name)}</a><br><span class='muted'>{escape(type_name)} | PathID {escape(path_id)}</span></td>"
                    f"<td>{escape(owner)}</td>"
                    f"<td>{escape(hierarchy)}</td>"
                    "</tr>"
                )
            if not rows:
                rows.append("<tr><td colspan='5'><span class='muted'>No selections recorded yet.</span></td></tr>")
            autosave = escape(str(self.selection_history_file))
            return (
                "<html><body style='font-family: Segoe UI, Arial, sans-serif; font-size:10pt; color:#eee;'>"
                "<style>"
                "a{color:#8ecbff;text-decoration:none;} .muted{color:#aaa;}"
                "table{border-collapse:collapse;width:100%;} th,td{border:1px solid #444;padding:5px;vertical-align:top;}"
                "th{background:#303030;color:#fff;} tr:nth-child(even){background:#252525;}"
                "</style>"
                "<h2>Selection History / Session Log</h2>"
                f"<p class='muted'>Newest first. Click an asset name to return to it. Auto-saved TSV: {autosave}</p>"
                "<table>"
                "<tr><th>Time</th><th>Bundle</th><th>Asset</th><th>Owner</th><th>Hierarchy hint</th></tr>"
                + "".join(rows) +
                "</table></body></html>"
            )

        def _selection_history_tsv(self) -> str:
            fields = ["timestamp", "bundle", "asset_name", "type", "path_id", "owner_name", "owner_path_id", "hierarchy"]
            lines = ["\t".join(fields)]
            for entry in self.selection_history_log:
                vals = []
                for f in fields:
                    vals.append(str(entry.get(f, "")).replace("\t", " ").replace("\r", " ").replace("\n", " "))
                lines.append("\t".join(vals))
            return "\n".join(lines) + "\n"

        def show_selection_history_dialog(self):
            dlg = QDialog(self)
            dlg.setWindowTitle("UBE Selection History / Session Log")
            dlg.resize(1000, 620)
            layout = QVBoxLayout(dlg)
            browser = QTextBrowser(dlg)
            browser.setOpenLinks(False)
            browser.setHtml(self._selection_history_html())
            layout.addWidget(browser)

            buttons = QHBoxLayout()
            copy_btn = QPushButton("Copy TSV")
            export_btn = QPushButton("Export TSV...")
            clear_btn = QPushButton("Clear Session History")
            close_btn = QPushButton("Close")
            buttons.addWidget(copy_btn)
            buttons.addWidget(export_btn)
            buttons.addWidget(clear_btn)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            layout.addLayout(buttons)

            def refresh():
                browser.setHtml(self._selection_history_html())

            def open_history_link(url):
                text = url.toString()
                prefix = "ube://history/"
                if not text.startswith(prefix):
                    return
                try:
                    idx = int(text[len(prefix):])
                    entry = self.selection_history_log[idx]
                except Exception:
                    return
                bundle_text = entry.get("bundle", "")
                pid_text = entry.get("path_id", "")
                try:
                    if bundle_text:
                        current = str(getattr(getattr(self, "bundle_index", None), "path", "") or "")
                        if current != bundle_text:
                            self.load_path(Path(bundle_text), from_project=self.current_project_folder is not None)
                    self.select_record_by_path_id(int(pid_text), push_history=True)
                    self.statusBar().showMessage("Returned to selection history item", 1800)
                except Exception as exc:
                    QMessageBox.warning(self, "Selection History", f"Could not return to this item:\n{exc}")

            def copy_tsv():
                QApplication.clipboard().setText(self._selection_history_tsv())
                self.statusBar().showMessage("Selection history copied as TSV", 1800)

            def export_tsv():
                path, _ = QFileDialog.getSaveFileName(self, "Export Selection History TSV", "UBE_selection_history.tsv", "TSV files (*.tsv);;All files (*.*)")
                if not path:
                    return
                try:
                    Path(path).write_text(self._selection_history_tsv(), encoding="utf-8")
                    self.statusBar().showMessage(f"Selection history exported: {path}", 2500)
                except Exception as exc:
                    QMessageBox.warning(self, "Export Selection History", f"Could not export selection history:\n{exc}")

            def clear_session():
                if QMessageBox.question(self, "Clear Selection History", "Clear this session's selection history?\n\nThe auto-saved TSV file is left in place.") == QMessageBox.Yes:
                    self.selection_history_log.clear()
                    refresh()
                    self.statusBar().showMessage("Session selection history cleared", 1800)

            browser.anchorClicked.connect(open_history_link)
            copy_btn.clicked.connect(copy_tsv)
            export_btn.clicked.connect(export_tsv)
            clear_btn.clicked.connect(clear_session)
            close_btn.clicked.connect(dlg.accept)
            dlg.exec()


        # ------------------------------------------------------------------
        # v1.8e: In-app project / PathID search.
        # ------------------------------------------------------------------
        def _search_terms_match(self, text: str, terms: list[str]) -> bool:
            low = str(text or "").lower()
            return all(t in low for t in terms if t)

        def _search_make_result(self, *, kind: str, source: str, bundle: str, name: str, type_name: str = "", path_id: str = "", owner: str = "", hierarchy: str = "") -> dict:
            return {
                "kind": kind,
                "source": source,
                "bundle": str(bundle or ""),
                "name": str(name or ""),
                "type": str(type_name or ""),
                "path_id": str(path_id or ""),
                "owner": str(owner or ""),
                "hierarchy": str(hierarchy or ""),
            }

        def _search_json_line_value(self, line: str):
            try:
                _, value = line.split(":", 1)
                value = value.strip()
                if value.endswith(","):
                    value = value[:-1]
                return json.loads(value)
            except Exception:
                return None

        def _bundle_paths_for_project_search(self) -> list[Path]:
            project = getattr(self, "project_index", None)
            paths: list[Path] = []
            if not project:
                return paths
            try:
                for course in getattr(project, "courses", {}).values():
                    if getattr(course, "assets_bundle", None):
                        paths.append(Path(course.assets_bundle))
                    for scene in getattr(course, "scenes", []) or []:
                        paths.append(Path(scene.path))
                    for extra in getattr(course, "extras", []) or []:
                        paths.append(Path(extra))
                for pth in getattr(project, "loose_bundles", []) or []:
                    paths.append(Path(pth))
            except Exception:
                pass
            out = []
            seen = set()
            for pth in paths:
                key = str(pth).lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(pth)
            return out

        def _search_current_bundle_records(self, query: str, max_results: int = 120) -> list[dict]:
            idx = getattr(self, "bundle_index", None)
            if not idx:
                return []
            q = str(query or "").strip()
            if not q:
                return []
            terms = [t.lower() for t in q.split() if t.strip()]
            exact_pid = None
            try:
                exact_pid = int(q)
            except Exception:
                pass

            rows = []
            records = list(getattr(idx, "record_by_path_id", {}).values())
            external = getattr(idx, "external_record_by_path_id", {}) or {}
            records.extend(list(external.values()))

            seen = set()
            for rec in records:
                try:
                    pid = int(getattr(rec, "path_id", 0) or 0)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    local = pid in getattr(idx, "record_by_path_id", {})
                    bundle_path = str(getattr(idx, "path", "") or "")
                    if not local:
                        bundle_path = str((getattr(idx, "external_bundle_by_path_id", {}) or {}).get(pid, bundle_path))
                    name = str(getattr(rec, "name", "") or f"PathID {pid}")
                    type_name = str(getattr(rec, "type_name", "") or "Unknown")
                    owner = ""
                    hierarchy = ""
                    if local:
                        try:
                            owner, _owner_pid = self._selection_history_owner(rec)
                            hierarchy = self._selection_history_hierarchy_path(rec)
                        except Exception:
                            pass
                    hay = f"{name} {type_name} {pid} {Path(bundle_path).name} {bundle_path} {owner} {hierarchy}"
                    ok = (pid == exact_pid) if exact_pid is not None else self._search_terms_match(hay, terms)
                    if not ok:
                        continue
                    rows.append(self._search_make_result(
                        kind="asset",
                        source="Current bundle" if local else "Related/external bundle",
                        bundle=bundle_path,
                        name=name,
                        type_name=type_name,
                        path_id=str(pid),
                        owner=owner,
                        hierarchy=hierarchy,
                    ))
                    if len(rows) >= max_results:
                        break
                except Exception:
                    continue
            return rows

        def _search_project_bundle_names(self, query: str, max_results: int = 50) -> list[dict]:
            q = str(query or "").strip()
            if not q:
                return []
            terms = [t.lower() for t in q.split() if t.strip()]
            rows = []
            for pth in self._bundle_paths_for_project_search():
                hay = f"{pth.name} {pth.stem} {pth.parent.name} {pth}"
                if not self._search_terms_match(hay, terms):
                    continue
                rows.append(self._search_make_result(
                    kind="bundle",
                    source="Project bundle file",
                    bundle=str(pth),
                    name=pth.name,
                    type_name="Bundle file",
                    path_id="",
                ))
                if len(rows) >= max_results:
                    break
            return rows

        def _search_project_pathid_index(self, query: str, max_results: int = 120) -> list[dict]:
            folder = getattr(self, "current_project_folder", None)
            if folder is None:
                return []
            q = str(query or "").strip()
            if not q:
                return []
            idx_file = index_path(folder)
            if not idx_file.exists():
                return []

            rows = []
            try:
                exact_pid = int(q)
            except Exception:
                exact_pid = None

            if exact_pid is not None:
                try:
                    entries = lookup_pathid_index_records(folder, exact_pid, max_results=max_results)
                    for e in entries:
                        rows.append(self._search_make_result(
                            kind="asset",
                            source="Project PathID index",
                            bundle=str(e.bundle_path),
                            name=e.name,
                            type_name=e.type_name,
                            path_id=str(e.path_id),
                        ))
                    return rows
                except Exception:
                    return rows

            terms = [t.lower() for t in q.split() if t.strip()]
            current = {}
            try:
                with idx_file.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        stripped = line.strip()
                        if stripped.startswith("{"):
                            current = {}
                        elif stripped.startswith('"path_id"'):
                            val = self._search_json_line_value(line)
                            if val is not None:
                                current["path_id"] = val
                        elif stripped.startswith('"type"'):
                            val = self._search_json_line_value(line)
                            if val is not None:
                                current["type"] = str(val)
                        elif stripped.startswith('"name"'):
                            val = self._search_json_line_value(line)
                            if val is not None:
                                current["name"] = str(val)
                        elif stripped.startswith('"bundle"'):
                            val = self._search_json_line_value(line)
                            if val is not None:
                                current["bundle"] = str(val)
                        elif stripped.startswith("}") and current:
                            try:
                                pid = int(current.get("path_id"))
                                name = str(current.get("name") or f"PathID {pid}")
                                type_name = str(current.get("type") or "Unknown")
                                rel_bundle = str(current.get("bundle") or "")
                                bundle_path = Path(folder) / rel_bundle if rel_bundle else Path("")
                                hay = f"{name} {type_name} {pid} {rel_bundle} {bundle_path.name}"
                                if self._search_terms_match(hay, terms):
                                    rows.append(self._search_make_result(
                                        kind="asset",
                                        source="Project PathID index",
                                        bundle=str(bundle_path),
                                        name=name,
                                        type_name=type_name,
                                        path_id=str(pid),
                                    ))
                                    if len(rows) >= max_results:
                                        break
                            except Exception:
                                pass
                            current = {}
            except Exception:
                return rows
            return rows

        def _run_project_search_results(self, query: str) -> list[dict]:
            rows = []
            rows.extend(self._search_current_bundle_records(query, max_results=120))
            rows.extend(self._search_project_bundle_names(query, max_results=50))
            rows.extend(self._search_project_pathid_index(query, max_results=120))

            out = []
            seen = set()
            for r in rows:
                key = (r.get("kind"), str(r.get("bundle", "")).lower(), str(r.get("path_id", "")), str(r.get("name", "")).lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append(r)
                if len(out) >= 250:
                    break
            return out

        def _project_search_html(self, query: str) -> str:
            rows = []
            for idx, r in enumerate(getattr(self, "project_search_results", []) or []):
                bundle_text = r.get("bundle", "") or "-"
                bundle_name = Path(bundle_text).name if bundle_text and bundle_text != "-" else "-"
                name = r.get("name", "") or "-"
                type_name = friendly_type_name(r.get("type", "")) if r.get("type") else "-"
                pid = r.get("path_id", "") or ""
                owner = r.get("owner", "") or ""
                hierarchy = r.get("hierarchy", "") or ""
                asset_line = f"<a href='ube://project_search/{idx}'>{escape(name)}</a>"
                if pid:
                    asset_line += f"<br><span class='muted'>{escape(type_name)} | PathID {escape(pid)}</span>"
                else:
                    asset_line += f"<br><span class='muted'>{escape(type_name)}</span>"
                context_bits = []
                if owner:
                    context_bits.append(f"Owner: {escape(owner)}")
                if hierarchy:
                    context_bits.append(f"Path: {escape(hierarchy)}")
                context_html = "<br>".join(context_bits) if context_bits else "<span class='muted'>-</span>"
                rows.append(
                    "<tr>"
                    f"<td>{escape(r.get('source', ''))}</td>"
                    f"<td>{asset_line}</td>"
                    f"<td>{escape(bundle_name)}<br><span class='muted'>{escape(bundle_text)}</span></td>"
                    f"<td>{context_html}</td>"
                    "</tr>"
                )
            if not rows:
                rows.append("<tr><td colspan='4'><span class='muted'>No results yet. Try an asset name, partial bundle name, Unity type, owner name, or exact PathID.</span></td></tr>")
            if getattr(self, "current_project_folder", None) is not None:
                p = index_path(self.current_project_folder)
                project_status = f"Project: {escape(str(self.current_project_folder))}<br>PathID index: {escape(p.name)} {'available' if p.exists() else 'missing'}"
            else:
                project_status = "No project folder is open; searching the current bundle only."
            return (
                "<html><body style='font-family: Segoe UI, Arial, sans-serif; font-size:10pt; color:#eee;'>"
                "<style>"
                "a{color:#8ecbff;text-decoration:none;} .muted{color:#aaa;}"
                "table{border-collapse:collapse;width:100%;} th,td{border:1px solid #444;padding:5px;vertical-align:top;}"
                "th{background:#303030;color:#fff;} tr:nth-child(even){background:#252525;}"
                ".hint{color:#ccc;background:#252525;border:1px solid #444;padding:8px;margin:8px 0;}"
                "</style>"
                "<h2>Project Search / PathID Lookup</h2>"
                f"<div class='hint'>Search: <b>{escape(query or '')}</b><br>{project_status}</div>"
                "<table>"
                "<tr><th>Source</th><th>Asset / bundle</th><th>Bundle</th><th>Owner / hierarchy</th></tr>"
                + "".join(rows) +
                "</table></body></html>"
            )

        def _project_search_tsv(self) -> str:
            fields = ["source", "kind", "bundle", "name", "type", "path_id", "owner", "hierarchy"]
            lines = ["\t".join(fields)]
            for r in getattr(self, "project_search_results", []) or []:
                vals = []
                for f in fields:
                    vals.append(str(r.get(f, "")).replace("\t", " ").replace("\r", " ").replace("\n", " "))
                lines.append("\t".join(vals))
            return "\n".join(lines) + "\n"

        def open_project_search_result(self, result_index: int):
            try:
                r = self.project_search_results[int(result_index)]
            except Exception:
                return
            kind = r.get("kind", "")
            bundle_text = r.get("bundle", "") or ""
            pid_text = r.get("path_id", "") or ""
            try:
                if bundle_text:
                    current = str(getattr(getattr(self, "bundle_index", None), "path", "") or "")
                    if kind == "bundle" or current.lower() != bundle_text.lower():
                        self.load_path(Path(bundle_text), from_project=self.current_project_folder is not None)
                if kind != "bundle" and pid_text:
                    self.select_record_by_path_id(int(pid_text), push_history=True)
                self.statusBar().showMessage("Opened search result", 1800)
            except Exception as exc:
                QMessageBox.warning(self, "Project Search", f"Could not open this search result:\n{exc}")

        def show_project_search_dialog(self):
            dlg = QDialog(self)
            dlg.setWindowTitle("UBE Project Search / PathID Lookup")
            dlg.resize(1100, 680)
            layout = QVBoxLayout(dlg)

            top = QHBoxLayout()
            query_edit = QLineEdit(dlg)
            query_edit.setPlaceholderText("Search asset name, bundle name, type, owner, or exact PathID...")
            search_btn = QPushButton("Search")
            top.addWidget(query_edit, 1)
            top.addWidget(search_btn)
            layout.addLayout(top)

            browser = QTextBrowser(dlg)
            browser.setOpenLinks(False)
            browser.setHtml(self._project_search_html(""))
            layout.addWidget(browser)

            buttons = QHBoxLayout()
            copy_btn = QPushButton("Copy TSV")
            export_btn = QPushButton("Export TSV...")
            close_btn = QPushButton("Close")
            buttons.addWidget(copy_btn)
            buttons.addWidget(export_btn)
            buttons.addStretch(1)
            buttons.addWidget(close_btn)
            layout.addLayout(buttons)

            def do_search():
                q = query_edit.text().strip()
                self.project_search_results = self._run_project_search_results(q)
                browser.setHtml(self._project_search_html(q))
                self.statusBar().showMessage(f"Project search: {len(self.project_search_results)} result(s)", 2500)

            def open_link(url):
                text = url.toString()
                prefix = "ube://project_search/"
                if not text.startswith(prefix):
                    return
                try:
                    self.open_project_search_result(int(text[len(prefix):]))
                except Exception:
                    pass

            def copy_tsv():
                QApplication.clipboard().setText(self._project_search_tsv())
                self.statusBar().showMessage("Search results copied as TSV", 1800)

            def export_tsv():
                path, _ = QFileDialog.getSaveFileName(self, "Export Search Results TSV", "UBE_project_search_results.tsv", "TSV files (*.tsv);;All files (*.*)")
                if not path:
                    return
                try:
                    Path(path).write_text(self._project_search_tsv(), encoding="utf-8")
                    self.statusBar().showMessage(f"Search results exported: {path}", 2500)
                except Exception as exc:
                    QMessageBox.warning(self, "Export Search Results", f"Could not export search results:\n{exc}")

            browser.anchorClicked.connect(open_link)
            search_btn.clicked.connect(do_search)
            query_edit.returnPressed.connect(do_search)
            copy_btn.clicked.connect(copy_tsv)
            export_btn.clicked.connect(export_tsv)
            close_btn.clicked.connect(dlg.accept)

            try:
                if self.selected_record is not None:
                    query_edit.setText(str(getattr(self.selected_record, "name", "") or getattr(self.selected_record, "path_id", "") or ""))
                    query_edit.selectAll()
            except Exception:
                pass
            query_edit.setFocus()
            dlg.exec()

        def show_3d_preview_help(self):
            """Scrollable, tidy help for the 3D preview controls."""
            show_preview_help_dialog(self)


        def _preview_focus_shortcut_pressed(self, event):
            """Return True when the pressed key should toggle preview focus."""
            try:
                focus = QApplication.focusWidget()
                # Do not steal typing from the search box.
                if focus is self.search:
                    return False
                key = event.key()
                text = event.text()
                if key == Qt.Key_F11:
                    return True
                if text in ("`", "~"):
                    return True
                # Optional convenience: Tab toggles while a true visual preview
                # is active.  v2.0l extends the same fullscreen/focus behaviour
                # from the 3D viewer to Texture2D previews.
                if key == Qt.Key_Tab and (
                    self.preview_stack.currentWidget() is self.preview_3d
                    or self._texture_preview_active()
                ):
                    return True
            except Exception:
                pass
            return False


        def _texture_preview_active(self) -> bool:
            """True when the 2D QLabel preview is showing a texture pixmap."""
            try:
                return (
                    self.preview_stack.currentWidget() is self.preview
                    and self.texture_preview_base_pixmap is not None
                    and not self.texture_preview_base_pixmap.isNull()
                )
            except Exception:
                return False

        def _event_local_pos(self, event) -> QPointF:
            """Qt 6 uses position(); older/fallback paths may use pos()."""
            try:
                return QPointF(event.position())
            except Exception:
                try:
                    return QPointF(event.pos())
                except Exception:
                    return QPointF(0.0, 0.0)

        def _texture_fit_scale(self) -> float:
            if self.texture_preview_base_pixmap is None or self.texture_preview_base_pixmap.isNull():
                return 1.0
            view_w = max(1, int(self.preview.width()))
            view_h = max(1, int(self.preview.height()))
            pix_w = max(1, int(self.texture_preview_base_pixmap.width()))
            pix_h = max(1, int(self.texture_preview_base_pixmap.height()))
            # Never enlarge a small texture merely because the preview/fullscreen
            # panel is larger.  Fit-to-window is capped at native preview size.
            return max(0.0001, min(1.0, view_w / float(pix_w), view_h / float(pix_h)))

        def _texture_max_zoom(self) -> float:
            """Cap wheel zoom at cached-image 1:1, with a small safety margin."""
            fit = self._texture_fit_scale()
            return max(1.0, min(16.0, 1.0 / fit))

        def _clamp_texture_pan(self):
            """Keep the zoomed texture from drifting completely out of view."""
            if self.texture_preview_base_pixmap is None or self.texture_preview_base_pixmap.isNull():
                self.texture_preview_pan = QPointF(0.0, 0.0)
                return
            if self.texture_preview_zoom <= 1.0001:
                self.texture_preview_pan = QPointF(0.0, 0.0)
                return

            view_w = max(1.0, float(self.preview.width()))
            view_h = max(1.0, float(self.preview.height()))
            fit = self._texture_fit_scale()
            scale = fit * float(self.texture_preview_zoom)
            draw_w = float(self.texture_preview_base_pixmap.width()) * scale
            draw_h = float(self.texture_preview_base_pixmap.height()) * scale

            pan_x = float(self.texture_preview_pan.x())
            pan_y = float(self.texture_preview_pan.y())

            if draw_w <= view_w:
                pan_x = 0.0
            else:
                centred_x = (view_w - draw_w) * 0.5
                min_pan_x = -centred_x
                max_pan_x = -centred_x + (view_w - draw_w)
                lo, hi = sorted((min_pan_x, max_pan_x))
                pan_x = max(lo, min(hi, pan_x))

            if draw_h <= view_h:
                pan_y = 0.0
            else:
                centred_y = (view_h - draw_h) * 0.5
                min_pan_y = -centred_y
                max_pan_y = -centred_y + (view_h - draw_h)
                lo, hi = sorted((min_pan_y, max_pan_y))
                pan_y = max(lo, min(hi, pan_y))

            self.texture_preview_pan = QPointF(pan_x, pan_y)

        def reset_texture_preview_view(self, redraw: bool = True):
            self.texture_preview_zoom = 1.0
            self.texture_preview_pan = QPointF(0.0, 0.0)
            self.texture_preview_panning = False
            if redraw:
                self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)

        def _texture_view_origin_and_scale(self) -> tuple[float, float, float]:
            """Return displayed texture origin x/y in label coords and current scale."""
            if self.texture_preview_base_pixmap is None or self.texture_preview_base_pixmap.isNull():
                return 0.0, 0.0, 1.0
            fit = self._texture_fit_scale()
            zoom = max(1.0, min(float(self.texture_preview_zoom), self._texture_max_zoom()))
            scale = fit * zoom
            draw_w = float(self.texture_preview_base_pixmap.width()) * scale
            draw_h = float(self.texture_preview_base_pixmap.height()) * scale
            x0 = (float(self.preview.width()) - draw_w) * 0.5 + float(self.texture_preview_pan.x())
            y0 = (float(self.preview.height()) - draw_h) * 0.5 + float(self.texture_preview_pan.y())
            return x0, y0, scale

        def _texture_pixel_from_view_pos(self, pos: QPointF):
            """Convert a QLabel/view mouse position to full texture pixel coordinates."""
            if not self._texture_preview_active() or not self.texture_preview_texture_size:
                return None
            try:
                x0, y0, scale = self._texture_view_origin_and_scale()
                if scale <= 0:
                    return None
                base_x = (float(pos.x()) - x0) / scale
                base_y = (float(pos.y()) - y0) / scale
                base_w = float(self.texture_preview_base_pixmap.width())
                base_h = float(self.texture_preview_base_pixmap.height())
                if base_x < 0 or base_y < 0 or base_x > base_w or base_y > base_h:
                    return None
                tex_w, tex_h = self.texture_preview_texture_size
                tex_x = base_x * float(tex_w) / max(1.0, base_w)
                tex_y = base_y * float(tex_h) / max(1.0, base_h)
                tex_x = max(0.0, min(float(tex_w), tex_x))
                tex_y = max(0.0, min(float(tex_h), tex_y))
                return QPointF(tex_x, tex_y)
            except Exception:
                return None

        def _normalised_texture_region(self, a, b):
            """Return x/y/w/h texture-pixel dict from two texture-space points."""
            if a is None or b is None or not self.texture_preview_texture_size:
                return None
            try:
                tex_w, tex_h = self.texture_preview_texture_size
                x1 = max(0, min(int(round(float(a.x()))), int(round(float(b.x())))))
                y1 = max(0, min(int(round(float(a.y()))), int(round(float(b.y())))))
                x2 = min(int(tex_w), max(int(round(float(a.x()))), int(round(float(b.x())))))
                y2 = min(int(tex_h), max(int(round(float(a.y()))), int(round(float(b.y())))))
                w = max(0, x2 - x1)
                h = max(0, y2 - y1)
                return {"x": x1, "y": y1, "w": w, "h": h}
            except Exception:
                return None

        def _texture_selection_overlay(self):
            """Current user-drawn atlas search rectangle, if any."""
            return self._normalised_texture_region(self.texture_region_select_start, self.texture_region_select_current)

        def _start_texture_region_selection(self, pos: QPointF) -> bool:
            tex_pos = self._texture_pixel_from_view_pos(pos)
            if tex_pos is None:
                return False
            self.texture_region_selecting = True
            self.texture_region_select_start = tex_pos
            self.texture_region_select_current = tex_pos
            self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            try:
                self.statusBar().showMessage("Drag to select a texture atlas search region", 2000)
            except Exception:
                pass
            return True

        def _update_texture_region_selection(self, pos: QPointF) -> bool:
            if not self.texture_region_selecting:
                return False
            tex_pos = self._texture_pixel_from_view_pos(pos)
            if tex_pos is None:
                # Keep the last valid point if the mouse leaves the image.
                return True
            self.texture_region_select_current = tex_pos
            self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            return True

        def _finish_texture_region_selection(self) -> bool:
            if not self.texture_region_selecting:
                return False
            self.texture_region_selecting = False
            region = self._texture_selection_overlay()
            if not region or region.get("w", 0) < 4 or region.get("h", 0) < 4:
                self.texture_region_select_start = None
                self.texture_region_select_current = None
                self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
                try:
                    self.statusBar().showMessage("Texture region selection cancelled", 1500)
                except Exception:
                    pass
                return True
            self._run_texture_region_search(region)
            self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            return True

        def _zoom_texture_preview_at(self, pos: QPointF, delta_steps: float):
            if not self._texture_preview_active():
                return False
            old_zoom = max(1.0, float(self.texture_preview_zoom))
            old_x0, old_y0, old_scale = self._texture_view_origin_and_scale()
            if old_scale <= 0:
                return False

            # Texture-pixel coordinate under the mouse before zooming.
            tex_x = (float(pos.x()) - old_x0) / old_scale
            tex_y = (float(pos.y()) - old_y0) / old_scale

            factor = 1.18 ** float(delta_steps)
            new_zoom = max(1.0, min(self._texture_max_zoom(), old_zoom * factor))
            self.texture_preview_zoom = new_zoom

            new_fit = self._texture_fit_scale()
            new_scale = new_fit * new_zoom
            draw_w = float(self.texture_preview_base_pixmap.width()) * new_scale
            draw_h = float(self.texture_preview_base_pixmap.height()) * new_scale
            centred_x = (float(self.preview.width()) - draw_w) * 0.5
            centred_y = (float(self.preview.height()) - draw_h) * 0.5

            # Keep the same texture pixel under the mouse after zooming.
            desired_x0 = float(pos.x()) - tex_x * new_scale
            desired_y0 = float(pos.y()) - tex_y * new_scale
            self.texture_preview_pan = QPointF(desired_x0 - centred_x, desired_y0 - centred_y)
            self._clamp_texture_pan()
            self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            try:
                display_scale = self._texture_fit_scale() * float(self.texture_preview_zoom)
                pct = int(round(display_scale * 100.0))
                self.statusBar().showMessage(
                    f"Texture preview zoom: {pct}% of cached preview.  Mouse wheel zooms, middle-drag pans, double-click resets.",
                    2500,
                )
            except Exception:
                pass
            return True

        def _center_texture_view_on_overlay(self):
            """If already zoomed in, centre the selected atlas box in the preview."""
            if not self.texture_atlas_overlay or not self.texture_preview_texture_size:
                return
            if not self._texture_preview_active() or self.texture_preview_zoom <= 1.0001:
                return
            try:
                tex_w, tex_h = self.texture_preview_texture_size
                base_w = float(self.texture_preview_base_pixmap.width())
                base_h = float(self.texture_preview_base_pixmap.height())
                ox = (float(self.texture_atlas_overlay.get("x", 0)) + float(self.texture_atlas_overlay.get("w", 1)) * 0.5) * base_w / float(tex_w)
                oy = (float(self.texture_atlas_overlay.get("y", 0)) + float(self.texture_atlas_overlay.get("h", 1)) * 0.5) * base_h / float(tex_h)
                fit = self._texture_fit_scale()
                scale = fit * max(1.0, float(self.texture_preview_zoom))
                draw_w = base_w * scale
                draw_h = base_h * scale
                centred_x = (float(self.preview.width()) - draw_w) * 0.5
                centred_y = (float(self.preview.height()) - draw_h) * 0.5
                desired_x0 = float(self.preview.width()) * 0.5 - ox * scale
                desired_y0 = float(self.preview.height()) * 0.5 - oy * scale
                self.texture_preview_pan = QPointF(desired_x0 - centred_x, desired_y0 - centred_y)
                self._clamp_texture_pan()
            except Exception:
                pass


        def _text_entry_has_focus(self) -> bool:
            """Return True while a widget has explicitly claimed normal text input.

            The application-level event filter intentionally makes the 3D viewer
            hotkeys work even when the asset tree owns focus.  A modal editor must
            opt out, otherwise letters such as U, M, W, H, X, etc. are consumed as
            viewer commands before QPlainTextEdit can insert them.
            """
            try:
                widget = QApplication.focusWidget()
                while widget is not None:
                    if bool(widget.property("ube_text_entry")):
                        return True
                    # Numeric spin boxes focus an internal QLineEdit.  Treat all
                    # ordinary editable fields as owners of their keystrokes so
                    # 0-6, U, G, H, X, etc. cannot trigger viewer shortcuts.
                    if isinstance(widget, (QLineEdit, QPlainTextEdit, QAbstractSpinBox)):
                        return True
                    if isinstance(widget, QComboBox) and widget.isEditable():
                        return True
                    widget = widget.parentWidget()
            except Exception:
                pass
            return False

        def eventFilter(self, obj, event):
            # The global QApplication event filter is installed early in __init__.
            # Qt can send menu/window events before the preview widgets exist, so
            # never assume self.preview / self.preview_stack have been created yet.
            if not hasattr(self, "preview") or not hasattr(self, "preview_stack"):
                return super().eventFilter(obj, event)

            # Text editors marked with ube_text_entry own their keyboard input.
            # This check deliberately comes before every global preview shortcut,
            # including ` / ~ / F11 focus handling and the single-key 3D commands.
            if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
                if self._text_entry_has_focus():
                    return False

            # v2.0h: relationship boxes use a width-aware wrapped table.  Rebuild
            # it after the QTextBrowser viewport settles rather than squeezing all
            # cards into a single row.  QTimer avoids resize/setHtml recursion when
            # scrollbars appear or disappear during layout.
            try:
                relationship_view = getattr(self, "relationship_view", None)
                relationship_viewport = relationship_view.viewport() if relationship_view is not None else None
                if (obj is relationship_view or obj is relationship_viewport) and event.type() == QEvent.Type.Resize:
                    current_width = int(relationship_viewport.width()) if relationship_viewport is not None else 0
                    width_changed = abs(current_width - int(getattr(self, "_relationship_flow_last_width", 0) or 0)) >= 24
                    flow_visible = self.preview_stack.currentWidget() is relationship_view
                    flow_record = getattr(self, "_relationship_flow_record", None)
                    if flow_visible and flow_record is not None and width_changed and not self._relationship_flow_refresh_pending:
                        self._relationship_flow_refresh_pending = True
                        QTimer.singleShot(0, self._refresh_relationship_flow_layout)
                    return False
            except Exception:
                pass

            if obj is self.preview and self._texture_preview_active():
                try:
                    etype = event.type()
                    if etype == QEvent.Type.Resize:
                        self.texture_preview_zoom = max(
                            1.0,
                            min(float(self.texture_preview_zoom), self._texture_max_zoom()),
                        )
                        self._clamp_texture_pan()
                        self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
                        return False
                    if etype == QEvent.Type.Wheel:
                        try:
                            steps = event.angleDelta().y() / 120.0
                        except Exception:
                            steps = 0.0
                        if steps:
                            if self._zoom_texture_preview_at(self._event_local_pos(event), steps):
                                event.accept()
                                return True
                    if etype == QEvent.Type.MouseButtonDblClick:
                        self.reset_texture_preview_view(redraw=True)
                        try:
                            self.statusBar().showMessage("Texture preview reset to fit", 1800)
                        except Exception:
                            pass
                        event.accept()
                        return True
                    if etype == QEvent.Type.MouseButtonPress:
                        if event.button() == Qt.MouseButton.LeftButton:
                            if self._start_texture_region_selection(self._event_local_pos(event)):
                                event.accept()
                                return True
                        if event.button() == Qt.MouseButton.MiddleButton:
                            if self.texture_preview_zoom > 1.0001:
                                self.texture_preview_panning = True
                                self.texture_preview_pan_last_pos = self._event_local_pos(event)
                                event.accept()
                                return True
                    if etype == QEvent.Type.MouseMove and self.texture_region_selecting:
                        self._update_texture_region_selection(self._event_local_pos(event))
                        event.accept()
                        return True
                    if etype == QEvent.Type.MouseButtonRelease and self.texture_region_selecting:
                        if event.button() == Qt.MouseButton.LeftButton:
                            self._finish_texture_region_selection()
                            event.accept()
                            return True
                    if etype == QEvent.Type.MouseMove and self.texture_preview_panning:
                        pos = self._event_local_pos(event)
                        delta = pos - self.texture_preview_pan_last_pos
                        self.texture_preview_pan_last_pos = pos
                        self.texture_preview_pan = QPointF(
                            float(self.texture_preview_pan.x()) + float(delta.x()),
                            float(self.texture_preview_pan.y()) + float(delta.y()),
                        )
                        self._clamp_texture_pan()
                        self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
                        event.accept()
                        return True
                    if etype == QEvent.Type.MouseButtonRelease and self.texture_preview_panning:
                        self.texture_preview_panning = False
                        event.accept()
                        return True
                except Exception:
                    pass

            if event.type() == QEvent.Type.MouseButtonPress:
                button = event.button()
                if button == Qt.MouseButton.XButton1:
                    if self.back_action.isEnabled():
                        self.go_back()
                        event.accept()
                        return True
                elif button == Qt.MouseButton.XButton2:
                    if self.forward_action.isEnabled():
                        self.go_forward()
                        event.accept()
                        return True

            # Adobe-style preview focus toggle: ` / ~ / F11, plus Tab for 3D preview.
            if event.type() == QEvent.Type.KeyPress:
                if self._preview_focus_shortcut_pressed(event):
                    self.toggle_preview_focus_mode()
                    event.accept()
                    return True

            # v2.4d: universal media-style play/pause.  The QApplication event
            # filter receives keys even when the tree, inspector, a toolbar control
            # or a modal export notice owns focus.  Text-entry widgets were already
            # excluded above, and auto-repeat is ignored to avoid rapid toggling.
            if event.type() == QEvent.Type.KeyPress:
                try:
                    no_modifiers = event.modifiers() == Qt.NoModifier
                    auto_repeat = bool(event.isAutoRepeat())
                    controls_visible = bool(
                        getattr(self, "animation_controls", None) is not None
                        and self.animation_controls.isVisible()
                    )
                    can_toggle = bool(
                        controls_visible
                        and getattr(self, "animation_tracks", None)
                        and self.animation_play_button.isEnabled()
                    )
                    if event.key() == Qt.Key_Space and no_modifiers and not auto_repeat and can_toggle:
                        self._animation_toggle_play()
                        state = "playing" if self.animation_timer.isActive() else "paused"
                        try:
                            self.statusBar().showMessage(f"Animation {state} — Space toggles play/pause", 2200)
                        except Exception:
                            pass
                        event.accept()
                        return True
                except Exception:
                    pass

            # Number-key quick views for the 3D preview.  This is handled here
            # because the asset tree often keeps keyboard focus after selection.
            # We still let the search box receive normal numeric text input.
            if event.type() == QEvent.Type.KeyPress:
                try:
                    if self.preview_stack.currentWidget() is self.preview_3d:
                        focus = QApplication.focusWidget()
                        if focus is self.search:
                            return False

                        if (
                            event.key() == Qt.Key_A
                            and event.modifiers() == Qt.NoModifier
                            and hasattr(self.preview_3d, "toggle_axis_indicator")
                        ):
                            label = self.preview_3d.toggle_axis_indicator()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_U and hasattr(self.preview_3d, "toggle_uv_channel"):
                            label = self.preview_3d.toggle_uv_channel()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_M and hasattr(self.preview_3d, "toggle_uv_domain_mode"):
                            label = self.preview_3d.toggle_uv_domain_mode()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_W and hasattr(self.preview_3d, "toggle_uv_wrap_mode"):
                            label = self.preview_3d.toggle_uv_wrap_mode()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_T and hasattr(self.preview_3d, "toggle_texture_tint"):
                            label = self.preview_3d.toggle_texture_tint()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_P and hasattr(self.preview_3d, "toggle_group_material_mode"):
                            label = self.preview_3d.toggle_group_material_mode()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 3500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_F and hasattr(self.preview_3d, "toggle_helper_preview"):
                            label = self.preview_3d.toggle_helper_preview()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 3500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_V and hasattr(self.preview_3d, "cycle_group_hidden_child"):
                            try:
                                reset = bool(event.modifiers() & Qt.ShiftModifier)
                            except Exception:
                                reset = False
                            label = self.preview_3d.cycle_group_hidden_child(reset=reset)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 4500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_I and hasattr(self.preview_3d, "cycle_group_solo_child"):
                            try:
                                reset = bool(event.modifiers() & Qt.ShiftModifier)
                            except Exception:
                                reset = False
                            label = self.preview_3d.cycle_group_solo_child(reset=reset)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 5000)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_O:
                            # IMPORTANT: handle Shift+O before plain O.
                            # The main-window event filter sees preview hotkeys even when
                            # focus is in the tree/inspector, so if we always route O to
                            # origin markers here then Shift+O never reaches preview_3d.
                            try:
                                shifted = bool(event.modifiers() & Qt.ShiftModifier)
                            except Exception:
                                shifted = False

                            if shifted and hasattr(self.preview_3d, "toggle_group_origin_offset_mode"):
                                label = self.preview_3d.toggle_group_origin_offset_mode()
                                try:
                                    self.statusBar().showMessage(f"3D preview: {label}", 4500)
                                except Exception:
                                    pass
                                event.accept()
                                return True

                            if hasattr(self.preview_3d, "toggle_group_origin_markers"):
                                label = self.preview_3d.toggle_group_origin_markers()
                                try:
                                    self.statusBar().showMessage(f"3D preview: {label}", 3500)
                                except Exception:
                                    pass
                                event.accept()
                                return True

                        if event.key() == Qt.Key_B and hasattr(self.preview_3d, "toggle_texture_source_mode"):
                            label = self.preview_3d.toggle_texture_source_mode()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_N and hasattr(self.preview_3d, "show_normal_texture_debug"):
                            label = self.preview_3d.show_normal_texture_debug()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 3500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_L and hasattr(self.preview_3d, "toggle_lit_bump_preview"):
                            label = self.preview_3d.toggle_lit_bump_preview()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 3500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_G and hasattr(self.preview_3d, "toggle_normal_green_flip"):
                            label = self.preview_3d.toggle_normal_green_flip()
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() in (Qt.Key_BracketLeft, Qt.Key_BracketRight) and hasattr(self.preview_3d, "adjust_bump_strength"):
                            delta = -0.25 if event.key() == Qt.Key_BracketLeft else 0.25
                            label = self.preview_3d.adjust_bump_strength(delta)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_H:
                            self.show_3d_preview_help()
                            event.accept()
                            return True

                        mapping = {
                            Qt.Key_0: "isometric",
                            Qt.Key_1: "top",
                            Qt.Key_2: "bottom",
                            Qt.Key_3: "front",
                            Qt.Key_4: "back",
                            Qt.Key_5: "left",
                            Qt.Key_6: "right",
                        }
                        view = mapping.get(event.key())
                        if view and hasattr(self.preview_3d, "set_standard_view"):
                            self.preview_3d.set_standard_view(view)
                            event.accept()
                            return True

                        # 3D preview fine orientation controls.
                        # Left mouse stays normal orbit. Right mouse rotates one selected axis.
                        # X/Y/Z choose the right-drag axis; Q/E roll Z by 15 degrees.
                        axis_mapping = {
                            Qt.Key_X: "x",
                            Qt.Key_Y: "y",
                            Qt.Key_Z: "z",
                        }
                        axis = axis_mapping.get(event.key())

                        # Ctrl+X/Y/Z chooses which authored axis should be treated as
                        # preview/export up. Ctrl+Shift chooses the negative axis.
                        try:
                            mods = event.modifiers()
                        except Exception:
                            mods = Qt.NoModifier
                        if axis and (mods & Qt.ControlModifier):
                            sign = "-" if (mods & Qt.ShiftModifier) else "+"
                            self.set_ground_up_axis(sign + axis.upper())
                            event.accept()
                            return True

                        if axis and hasattr(self.preview_3d, "set_right_drag_axis"):
                            label = self.preview_3d.set_right_drag_axis(axis)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}. Hold Shift while dragging for 15° snap.", 2500)
                            except Exception:
                                pass
                            event.accept()
                            return True

                        if event.key() == Qt.Key_Q and hasattr(self.preview_3d, "rotate_view_axis"):
                            label = self.preview_3d.rotate_view_axis("z", -15.0, snap=True)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 1500)
                            except Exception:
                                pass
                            event.accept()
                            return True
                        if event.key() == Qt.Key_E and hasattr(self.preview_3d, "rotate_view_axis"):
                            label = self.preview_3d.rotate_view_axis("z", 15.0, snap=True)
                            try:
                                self.statusBar().showMessage(f"3D preview: {label}", 1500)
                            except Exception:
                                pass
                            event.accept()
                            return True
                except Exception:
                    pass

            return super().eventFilter(obj, event)


        def _read_bool_setting(self, key: str, default: bool) -> bool:
            try:
                value = QSettings("UBE", "UnityBundleExplorer").value(key, default)
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() not in ("0", "false", "no", "off", "")
            except Exception:
                return bool(default)

        def set_tree_column_visible(self, column: int, visible: bool, setting_key: str | None = None) -> None:
            try:
                if hasattr(self, "tree"):
                    self.tree.setColumnHidden(int(column), not bool(visible))
                if setting_key:
                    QSettings("UBE", "UnityBundleExplorer").setValue(setting_key, bool(visible))
            except Exception:
                pass

        def apply_tree_column_visibility(self) -> None:
            """Apply the saved v2.0 asset-tree presentation choices."""
            actions = (
                (1, getattr(self, "show_kind_column_action", None)),
                (2, getattr(self, "show_pathid_column_action", None)),
                (3, getattr(self, "show_comment_column_action", None)),
            )
            for column, action in actions:
                if action is not None:
                    self.tree.setColumnHidden(column, not action.isChecked())

        def load_recent_items(self) -> list[dict]:
            """Load File -> Recent entries from Qt settings.

            Stored entries are dictionaries:
              {"kind": "folder"|"bundle", "path": "..."}
            """
            try:
                settings = QSettings("UBE", "UnityBundleExplorer")
                raw = settings.value("recent_open_items", "")
                if not raw:
                    return []
                items = json.loads(str(raw))
            except Exception:
                return []

            cleaned = []
            seen = set()
            for item in items if isinstance(items, list) else []:
                try:
                    kind = str(item.get("kind", "")).strip().lower()
                    path = str(item.get("path", "")).strip()
                except Exception:
                    continue
                if kind not in ("folder", "bundle") or not path:
                    continue
                key = (kind, path.lower())
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append({"kind": kind, "path": path})
                if len(cleaned) >= 5:
                    break
            return cleaned

        def save_recent_items(self) -> None:
            try:
                settings = QSettings("UBE", "UnityBundleExplorer")
                settings.setValue("recent_open_items", json.dumps(self.recent_items[:5], ensure_ascii=False))
            except Exception:
                pass

        def add_recent_item(self, kind: str, path: Path) -> None:
            kind = str(kind or "").strip().lower()
            if kind not in ("folder", "bundle", "serialized_folder"):
                return
            try:
                path_text = str(Path(path).resolve())
            except Exception:
                path_text = str(path)
            if not path_text:
                return

            new_item = {"kind": kind, "path": path_text}
            kept = []
            for item in getattr(self, "recent_items", []) or []:
                if item.get("kind") == kind and str(item.get("path", "")).lower() == path_text.lower():
                    continue
                kept.append(item)
            self.recent_items = [new_item] + kept
            self.recent_items = self.recent_items[:5]
            self.save_recent_items()
            self.refresh_recent_menu()

        def recent_item_label(self, item: dict) -> str:
            kind = item.get("kind", "bundle")
            path = Path(str(item.get("path", "")))
            prefix = "Serialized Folder" if kind == "serialized_folder" else ("Folder" if kind == "folder" else "Bundle")
            try:
                if kind == "folder":
                    name = path.name or str(path)
                else:
                    parent = path.parent.name
                    name = f"{path.name}  —  {parent}" if parent else path.name
            except Exception:
                name = str(item.get("path", ""))
            return f"{prefix}: {name}"

        def refresh_recent_menu(self) -> None:
            menu = getattr(self, "recent_menu", None)
            if menu is None:
                return
            menu.clear()
            items = getattr(self, "recent_items", []) or []
            if not items:
                empty = menu.addAction("No recent files or folders")
                empty.setEnabled(False)
                return
            for item in items[:5]:
                action = QAction(self.recent_item_label(item), self)
                action.setToolTip(str(item.get("path", "")))
                action.setData(dict(item))
                action.triggered.connect(lambda checked=False, a=action: self.open_recent_item(a.data()))
                menu.addAction(action)
            menu.addSeparator()
            clear_action = menu.addAction("Clear Recent List")
            clear_action.triggered.connect(self.clear_recent_items)

        def clear_recent_items(self) -> None:
            self.recent_items = []
            self.save_recent_items()
            self.refresh_recent_menu()

        def open_recent_item(self, item: dict) -> None:
            try:
                kind = str(item.get("kind", "")).lower()
                path = Path(str(item.get("path", "")))
            except Exception:
                return
            if not path.exists():
                QMessageBox.warning(self, "Recent item not found", f"This recent item no longer exists:\n{path}")
                self.recent_items = [x for x in getattr(self, "recent_items", []) or [] if str(x.get("path", "")).lower() != str(path).lower()]
                self.save_recent_items()
                self.refresh_recent_menu()
                return
            if kind == "folder":
                self.load_project(path, add_recent=True)
            elif kind == "serialized_folder":
                self.load_serialized_assets_folder(path, add_recent=True)
            else:
                self.load_path(path, from_project=False, add_recent=True)

        def show_tree_context_menu(self, pos: QPoint):
            item = self.tree.itemAt(pos)
            menu = QMenu(self)

            return_project = None
            if self.bundle_index is not None:
                if self.current_project_folder is not None:
                    return_project = menu.addAction("Return to project / course list")
                    menu.addSeparator()
                elif getattr(self, "serialized_assets_folder", None) is not None:
                    return_project = menu.addAction("Return to serialized assets folder")
                    menu.addSeparator()

            expand_branch = menu.addAction("Expand this branch")
            collapse_branch = menu.addAction("Collapse this branch")
            menu.addSeparator()
            filter_branch = menu.addAction("Filter this branch by keyword...")
            clear_branch_filter = menu.addAction("Clear branch filter")
            menu.addSeparator()
            isolate_asset_type = menu.addAction("Isolate this asset type")
            isolate_asset_type.setCheckable(True)
            menu.addSeparator()
            collapse_all = menu.addAction("Collapse all")
            expand_all = menu.addAction("Expand all")
            menu.addSeparator()
            edit_comment = menu.addAction("Edit external comment...")
            clear_comment = menu.addAction("Clear external comment")
            menu.addSeparator()
            show_relationship_flow = menu.addAction("Show relationship flow")
            menu.addSeparator()
            export_asset = menu.addAction("Export native asset data...")
            export_branch = menu.addAction("Export native assets in this branch...")
            export_filtered_branch = menu.addAction("Export native filtered results in this branch...")
            export_filtered_tree = menu.addAction("Export all native filtered results...")
            export_bundle = menu.addAction("Export native assets from entire bundle...")
            menu.addSeparator()
            report_menu = menu.addMenu("Export inspector report")
            report_asset = report_menu.addAction("This asset...")
            report_branch = report_menu.addAction("This branch...")
            report_filtered_branch = report_menu.addAction("Filtered results in this branch...")
            report_filtered_tree = report_menu.addAction("All filtered results...")

            rec = item.data(0, Qt.UserRole) if item is not None else None
            clicked_asset_type = self._asset_type_for_group_item(item)
            is_asset_record = rec is not None and not isinstance(rec, tuple)
            branch_records = self.unique_records(self.collect_records_under_item(item)) if item is not None else []
            has_branch_assets = bool(branch_records)
            branch_export_records = [r for r in branch_records if self.export_supported_for_record(r)]
            filter_text = self.current_tree_filter_text()
            filter_active = self.has_active_tree_filter()
            filtered_branch_report_records = self.unique_records(self.collect_visible_records_under_item(item)) if item is not None and filter_active else []
            filtered_tree_report_records = self.collect_visible_records_in_tree() if filter_active else []
            filtered_branch_records = [r for r in filtered_branch_report_records if self.export_supported_for_record(r)]
            filtered_tree_records = [r for r in filtered_tree_report_records if self.export_supported_for_record(r)]

            filter_branch.setEnabled(item is not None and item.childCount() > 0)
            clear_branch_filter.setEnabled(bool(getattr(self, "branch_filter_text", "")))
            isolate_asset_type.setEnabled(bool(clicked_asset_type))
            isolate_asset_type.setChecked(bool(clicked_asset_type and clicked_asset_type == getattr(self, "isolated_asset_type", "")))
            if clicked_asset_type:
                friendly_isolate_name = friendly_type_name(clicked_asset_type)
                isolate_asset_type.setText(f"Isolate asset type: {friendly_isolate_name}")
                if isolate_asset_type.isChecked():
                    isolate_asset_type.setToolTip(f"Untick to restore all asset types. Currently showing only {friendly_isolate_name}.")
                else:
                    isolate_asset_type.setToolTip(f"Hide every other asset type and show only {friendly_isolate_name}.")
            else:
                isolate_asset_type.setToolTip("Right-click a top-level asset-type group such as Mesh, Material, Texture2D, or GameObject.")
            edit_comment.setEnabled(is_asset_record)
            clear_comment.setEnabled(is_asset_record and self.comment_store.has(rec))
            show_relationship_flow.setEnabled(is_asset_record)
            show_relationship_flow.setToolTip(
                "Show a compact clickable diagram of the nearest parent/owner, selected asset, and direct children/references."
            )
            export_asset.setEnabled(is_asset_record and self.export_supported_for_record(rec))
            export_branch.setEnabled(bool(branch_export_records))
            export_filtered_branch.setEnabled(filter_active and bool(filtered_branch_records))
            export_filtered_tree.setEnabled(filter_active and bool(filtered_tree_records))
            export_bundle.setEnabled(self.bundle_index is not None and bool(self.collect_exportable_records_in_bundle()))
            report_asset.setEnabled(is_asset_record)
            report_branch.setEnabled(has_branch_assets)
            report_filtered_branch.setEnabled(filter_active and bool(filtered_branch_report_records))
            report_filtered_tree.setEnabled(filter_active and bool(filtered_tree_report_records))

            if not export_asset.isEnabled():
                export_asset.setToolTip("This asset has no native file exporter. Use Export inspector report instead.")
            else:
                export_asset.setToolTip("Export the selected asset in its supported native/usable format.")
            if not filter_branch.isEnabled():
                filter_branch.setToolTip("Right-click a branch such as Mesh, Material, Texture2D, or a folder-like node to filter only inside that branch.")
            else:
                filter_branch.setToolTip("Prompt for a keyword and show only matching assets inside this branch.")
            if not clear_branch_filter.isEnabled():
                clear_branch_filter.setToolTip("No branch-scoped filter is active.")
            else:
                clear_branch_filter.setToolTip(f"Clear branch filter: {getattr(self, 'branch_filter_label', '')} contains '{getattr(self, 'branch_filter_text', '')}'")
            if not export_branch.isEnabled():
                export_branch.setToolTip("No assets with native file exporters were found in this branch. Inspector reports are still available.")
            else:
                export_branch.setText(f"Export native assets in this branch... ({len(branch_export_records)})")
            if not export_filtered_branch.isEnabled():
                export_filtered_branch.setToolTip("Use a filter first; only visible filtered assets with native exporters are included.")
            else:
                export_filtered_branch.setText(f"Export native filtered results in this branch... ({len(filtered_branch_records)})")
                export_filtered_branch.setToolTip(f"Export native data for the visible/search-matching assets under this branch. Filter: {filter_text}")
            if not export_filtered_tree.isEnabled():
                export_filtered_tree.setToolTip("Use the search box or a branch-scoped filter first to export native data for visible filtered assets.")
            else:
                export_filtered_tree.setText(f"Export all native filtered results... ({len(filtered_tree_records)})")
                export_filtered_tree.setToolTip(f"Export native data for all visible/search-matching assets in the current tree. Filter: {filter_text}")
            if not export_bundle.isEnabled():
                export_bundle.setToolTip("No assets with native file exporters were found in this bundle.")

            report_asset.setToolTip("Write the full inspector display for this asset to a readable HTML report.")
            report_branch.setText(f"This branch... ({len(branch_records)})")
            report_branch.setToolTip("Write the full inspector display for every asset in this branch. Combined HTML is the default.")
            if report_filtered_branch.isEnabled():
                report_filtered_branch.setText(f"Filtered results in this branch... ({len(filtered_branch_report_records)})")
                report_filtered_branch.setToolTip(f"Write reports for all visible/search-matching assets in this branch. Filter: {filter_text}")
            else:
                report_filtered_branch.setToolTip("Use a search or branch filter first.")
            if report_filtered_tree.isEnabled():
                report_filtered_tree.setText(f"All filtered results... ({len(filtered_tree_report_records)})")
                report_filtered_tree.setToolTip(f"Write reports for every visible/search-matching asset in the current tree. Filter: {filter_text}")
            else:
                report_filtered_tree.setToolTip("Use a search or branch filter first.")

            if item is None:
                expand_branch.setEnabled(False)
                collapse_branch.setEnabled(False)
                filter_branch.setEnabled(False)
                isolate_asset_type.setEnabled(False)
                edit_comment.setEnabled(False)
                clear_comment.setEnabled(False)
                show_relationship_flow.setEnabled(False)
                export_asset.setEnabled(False)
                export_branch.setEnabled(False)
                export_filtered_branch.setEnabled(False)
                report_asset.setEnabled(False)
                report_branch.setEnabled(False)
                report_filtered_branch.setEnabled(False)

            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if return_project is not None and action == return_project:
                self.return_to_project_view()
            elif action == expand_branch and item is not None:
                self.set_branch_expanded(item, True)
            elif action == collapse_branch and item is not None:
                self.set_branch_expanded(item, False)
            elif action == filter_branch and item is not None:
                self.prompt_filter_branch(item)
            elif action == clear_branch_filter:
                self.clear_branch_filter(apply_now=True)
            elif action == isolate_asset_type and clicked_asset_type:
                if isolate_asset_type.isChecked():
                    self.set_asset_type_isolation(clicked_asset_type, apply_now=True)
                else:
                    self.clear_asset_type_isolation(apply_now=True)
            elif action == collapse_all:
                self.tree.collapseAll()
            elif action == expand_all:
                self.tree.expandAll()
            elif action == edit_comment and is_asset_record:
                self.edit_comment_for_record(rec)
            elif action == clear_comment and is_asset_record:
                self.clear_comment_for_record(rec)
            elif action == show_relationship_flow and is_asset_record:
                self.preview_relationship_flow(rec, forced=True)
            elif action == report_asset and is_asset_record:
                self.export_inspector_reports([rec], "Export inspector report", report_label=getattr(rec, "name", "asset"))
            elif action == report_branch and item is not None:
                label = friendly_type_name(clicked_asset_type) if clicked_asset_type else "Branch"
                self.export_inspector_reports(branch_records, "Export inspector report for this branch", report_label=label)
            elif action == report_filtered_branch and item is not None:
                label = friendly_type_name(clicked_asset_type) if clicked_asset_type else "Filtered branch"
                self.export_inspector_reports(filtered_branch_report_records, "Export filtered inspector report", report_label=f"{label} filtered")
            elif action == report_filtered_tree:
                self.export_inspector_reports(filtered_tree_report_records, "Export all filtered inspector results", report_label="Filtered results")
            elif action == export_asset and is_asset_record:
                self.export_record(rec)
            elif action == export_branch and item is not None:
                self.export_records(branch_export_records, "Choose export folder for native assets in this branch")
            elif action == export_filtered_branch and item is not None:
                self.export_records(filtered_branch_records, f"Choose export folder for native filtered branch results ({filter_text})")
            elif action == export_filtered_tree:
                self.export_records(filtered_tree_records, f"Choose export folder for native filtered results ({filter_text})")
            elif action == export_bundle:
                self.export_records(self.collect_exportable_records_in_bundle(), "Choose export folder for native assets in entire bundle")

        def set_branch_expanded(self, item, expanded: bool):
            item.setExpanded(expanded)
            for i in range(item.childCount()):
                self.set_branch_expanded(item.child(i), expanded)

        def open_bundle(self):
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Unity bundle",
                "",
                "Unity bundles / Unity files (*.bundle *.unity3d *.obb *.assets);;All files (*.*)",
            )
            if path:
                self.load_path(Path(path), from_project=False, add_recent=True)

        def open_serialized_assets_file(self):
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Unity SerializedFile asset",
                "",
                "Unity SerializedFile assets (globalgamemanagers globalgamemanagers.assets sharedassets*.assets resources.assets level* *.assets);;All files (*.*)",
            )
            if path:
                self.load_path(Path(path), from_project=False, add_recent=True)

        def open_serialized_assets_folder(self):
            folder = QFileDialog.getExistingDirectory(self, "Open folder containing .assets / globalgamemanagers files")
            if folder:
                self.load_serialized_assets_folder(Path(folder), add_recent=True)

        def open_folder(self):
            folder = QFileDialog.getExistingDirectory(self, "Open folder containing bundles")
            if folder:
                self.load_project(Path(folder), add_recent=True)

        def _serialized_assets_candidates(self, folder: Path) -> list[Path]:
            """Find top-level Unity SerializedFile sources in a GameName_Data folder.

            .resS/.resource files are intentionally not listed as openable sources:
            they are sidecar byte warehouses referenced by the .assets file.
            """
            candidates: list[Path] = []
            try:
                files = sorted([p for p in folder.iterdir() if p.is_file()], key=lambda p: p.name.lower())
            except Exception:
                return candidates

            skip_suffixes = {".ress", ".resss", ".ressS", ".resS", ".resource", ".split0", ".split1", ".split2", ".split3"}
            for p in files:
                # Path.suffix is case-sensitive; compare lower-case plus explicit .resS name checks.
                lower_name = p.name.lower()
                if lower_name.endswith(".ress") or lower_name.endswith(".resss") or lower_name.endswith(".ressource"):
                    continue
                if lower_name.endswith(".ress") or lower_name.endswith(".resource") or lower_name.endswith(".ress"):
                    continue
                if ".ress" in lower_name and lower_name.endswith((".ress", ".resss")):
                    continue
                if lower_name.endswith(".ress") or lower_name.endswith(".resss") or lower_name.endswith(".resS".lower()):
                    continue
                if lower_name.endswith(".resource") or ".split" in lower_name:
                    continue
                try:
                    h = read_unityfs_header(p)
                    if getattr(h, "signature", "") == "UnitySerializedFile":
                        candidates.append(p)
                except Exception:
                    pass
            return candidates

        def load_serialized_assets_folder(self, folder: Path, add_recent: bool = False):
            self.tree.clear()
            self.search.clear()
            self.clear_branch_filter(apply_now=False)
            self.clear_asset_type_isolation(apply_now=False)
            self.asset_type_items = {}
            self.bundle_index = None
            self.asset_graph.clear()
            self.item_by_path_id = {}
            self.history = []
            self.history_index = -1
            self.update_navigation_actions()
            self.current_project_folder = None
            self.serialized_assets_folder = folder
            self.project_index = None
            self.update_return_source_action()
            if add_recent:
                self.add_recent_item("serialized_folder", folder)

            files = self._serialized_assets_candidates(folder)
            root = QTreeWidgetItem([
                display_name_with_icon(f"{folder.name}  |  {len(files)} Unity SerializedFile source(s)", "Folder"),
                "Serialized Assets Folder",
                "",
            ])
            self.tree.addTopLevelItem(root)

            for p in files:
                try:
                    h = read_unityfs_header(p)
                    version = h.unity_revision or h.unity_version or "unknown"
                    declared = getattr(h, "declared_file_size", None)
                    size_note = f"{p.stat().st_size:,} bytes"
                    if declared and int(declared) != p.stat().st_size:
                        size_note += f" / declared {int(declared):,}"
                    label = f"{p.name}  |  Unity {version}  |  {size_note}"
                except Exception:
                    label = p.name
                item = QTreeWidgetItem([display_name_with_icon(label, "AssetBundle"), "UnitySerializedFile", ""])
                item.setData(0, Qt.UserRole, ("serialized_asset_path", str(p)))
                root.addChild(item)

            root.setExpanded(True)
            self.tree.resizeColumnToContents(0)
            self.info.setPlainText(
                f"Folder: {folder}\n"
                f"Unity SerializedFile sources found: {len(files)}\n\n"
                "These are .assets/globalgamemanagers/sharedassets/resources style Unity files.\n"
                ".resS and .resource files are sidecar byte stores and are not opened directly.\n\n"
                "Select a file to load it through the normal UBE inspectors.\n"
                "When inside a source file, use File → Return to Serialized Assets Folder, Alt+Left, "
                "or right-click the tree to return to this list.\n"
                "When a SerializedFile is opened from this folder, UBE will also try a capped sibling resolver "
                "so external Mesh/Material/Texture references can become clickable/previewable where possible."
            )
            self.preview.setText("Serialized assets folder loaded")
            self.setWindowTitle(full_title(f"Serialized folder: {folder.name}"))

        def load_project(self, folder: Path, add_recent: bool = False):
            self.tree.clear()
            self.search.clear()
            self.clear_branch_filter(apply_now=False)
            self.clear_asset_type_isolation(apply_now=False)
            self.asset_type_items = {}
            self.bundle_index = None
            self.asset_graph.clear()
            self.item_by_path_id = {}
            self.history = []
            self.history_index = -1
            self.update_navigation_actions()
            self.current_project_folder = folder
            self.serialized_assets_folder = None
            if add_recent:
                self.add_recent_item("folder", folder)
            self.update_return_source_action()
            self.project_index = scan_project_folder(folder)
            # Build 136: do not load/parse the global PathID JSON in the UI.
            # A full Walkabout index can describe millions of objects, and parsing
            # it while opening a level makes the app feel frozen.  Keep the fast
            # course-local resolver in the UI; use the command-line --pathID lookup
            # for rare global hunts.
            self.pathid_index = None
            self.pathid_lookup_cache = {}
            idx_file = index_path(folder)
            self.pathid_index_status = f"Available: {idx_file.name} (manual --pathID lookup)" if idx_file.exists() else f"Missing ({idx_file.name})"
            self.setWindowTitle(full_title(f"Project: {folder.name}"))
            self.populate_project_tree()

        def update_return_source_action(self) -> None:
            """Update the back-to-list action for project and SerializedFile folder modes."""
            try:
                if getattr(self, "current_project_folder", None) is not None and getattr(self, "bundle_index", None) is not None:
                    self.return_project_action.setText("Return to Project / Course List")
                    self.return_project_action.setToolTip("Go back to the opened project/folder bundle list. Shortcut: Alt+Left")
                    self.return_project_action.setEnabled(True)
                    return
                if getattr(self, "serialized_assets_folder", None) is not None and getattr(self, "bundle_index", None) is not None:
                    self.return_project_action.setText("Return to Serialized Assets Folder")
                    self.return_project_action.setToolTip("Go back to the opened .assets/globalgamemanagers source list. Shortcut: Alt+Left")
                    self.return_project_action.setEnabled(True)
                    return
                self.return_project_action.setText("Return to Source List")
                self.return_project_action.setToolTip("Return to an opened project/folder list when available. Shortcut: Alt+Left")
                self.return_project_action.setEnabled(False)
            except Exception:
                pass


        def return_to_project_view(self):
            if self.current_project_folder is not None:
                self.load_project(self.current_project_folder, add_recent=False)
                return
            if getattr(self, "serialized_assets_folder", None) is not None:
                self.load_serialized_assets_folder(self.serialized_assets_folder, add_recent=False)
                return
            self.update_return_source_action()

        def populate_project_tree(self):
            project = self.project_index
            if not project:
                return

            root = QTreeWidgetItem([
                display_name_with_icon(f"{project.folder.name}  |  {len(project.courses)} course groups  |  {project.bundle_count} bundles", "Project"),
                "Project",
                "",
            ])
            self.tree.addTopLevelItem(root)

            courses_root = QTreeWidgetItem([display_name_with_icon(f"Course Groups ({len(project.courses)})", "Folder"), "Folder", ""])
            root.addChild(courses_root)

            for _, course in sorted(project.courses.items(), key=lambda kv: kv[1].display_name.lower()):
                course_item = QTreeWidgetItem([display_name_with_icon(f"{course.display_name} ({course.bundle_count})", "Course"), "Course", course.prefix])
                courses_root.addChild(course_item)

                if course.assets_bundle:
                    item = QTreeWidgetItem([display_name_with_icon(course.assets_bundle.name, "AssetBundle"), "Assets Bundle", ""])
                    item.setData(0, Qt.UserRole, ("bundle_path", str(course.assets_bundle)))
                    course_item.addChild(item)

                if course.scenes:
                    scenes_item = QTreeWidgetItem([display_name_with_icon(f"Scenes ({len(course.scenes)})", "Folder"), "Folder", ""])
                    course_item.addChild(scenes_item)
                    for scene in course.scenes:
                        label = f"{scene.scene_name}  [{scene.variant}]"
                        item = QTreeWidgetItem([display_name_with_icon(label, "AssetBundle"), "Scene Bundle", ""])
                        item.setData(0, Qt.UserRole, ("bundle_path", str(scene.path)))
                        scenes_item.addChild(item)

                for extra in course.extras:
                    item = QTreeWidgetItem([display_name_with_icon(extra.name, "AssetBundle"), "Extra Bundle", ""])
                    item.setData(0, Qt.UserRole, ("bundle_path", str(extra)))
                    course_item.addChild(item)

            if project.loose_bundles:
                loose = QTreeWidgetItem([display_name_with_icon(f"Loose / Global Bundles ({len(project.loose_bundles)})", "Folder"), "Folder", ""])
                root.addChild(loose)
                for p in project.loose_bundles:
                    item = QTreeWidgetItem([display_name_with_icon(p.name, "AssetBundle"), "Loose Bundle", ""])
                    item.setData(0, Qt.UserRole, ("bundle_path", str(p)))
                    loose.addChild(item)

            if project.obb_files:
                obb = QTreeWidgetItem([display_name_with_icon(f"Android Expansion / OBB ({len(project.obb_files)})", "Folder"), "Folder", ""])
                root.addChild(obb)
                for p in project.obb_files:
                    item = QTreeWidgetItem([display_name_with_icon(p.name, "OBB"), "OBB", f"{p.stat().st_size:,} bytes"])
                    obb.addChild(item)

            root.setExpanded(True)
            courses_root.setExpanded(True)
            self.tree.resizeColumnToContents(0)
            self.info.setPlainText(
                f"Folder: {project.folder}\n"
                f"Course groups: {len(project.courses)}\n"
                f"Bundles: {project.bundle_count}\n"
                f"Loose/global bundles: {len(project.loose_bundles)}\n"
                f"OBB files: {len(project.obb_files)}\n"
                f"PathID index: {getattr(self, 'pathid_index_status', '') or '-'}\n\n"
                "Select a bundle item to load it."
            )
            self.preview.setText("Project loaded")


        def _loading_event_flags(self):
            try:
                return QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
            except Exception:
                try:
                    return QEventLoop.ExcludeUserInputEvents
                except Exception:
                    return QEventLoop.AllEvents

        def _pump_loading_events(self, max_time_ms: int = 40) -> None:
            """Let Qt/Windows repaint while excluding clicks and shortcuts."""
            try:
                QApplication.processEvents(self._loading_event_flags(), int(max_time_ms))
            except TypeError:
                QApplication.processEvents()
            except Exception:
                pass

        def _pump_modal_work_events(self, max_time_ms: int = 40) -> None:
            """Repaint a modal work notice while still accepting safe keyboard input.

            The parent window remains blocked by the application-modal dialog, so
            clicks cannot change the selected asset mid-operation.  Processing all
            events allows the global Space shortcut and animation timer to continue
            while an animated GLB export is running.
            """
            try:
                flags = QEventLoop.ProcessEventsFlag.AllEvents
            except Exception:
                try:
                    flags = QEventLoop.AllEvents
                except Exception:
                    flags = None
            try:
                if flags is None:
                    QApplication.processEvents()
                else:
                    QApplication.processEvents(flags, int(max_time_ms))
            except TypeError:
                QApplication.processEvents()
            except Exception:
                pass

        def _show_loading_notice(self, path: Path) -> None:
            """Show a simple modal wait notice without a misleading progress bar."""
            try:
                if self._loading_dialog is None:
                    dlg = QDialog(self)
                    dlg.setWindowTitle("Opening Unity bundle")
                    dlg.setWindowModality(Qt.ApplicationModal)
                    try:
                        dlg.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                        dlg.setWindowFlag(Qt.WindowCloseButtonHint, False)
                    except Exception:
                        pass
                    layout = QVBoxLayout(dlg)
                    layout.setContentsMargins(24, 20, 24, 20)
                    layout.setSpacing(10)

                    heading = QLabel("<b>Loading bundle — please wait…</b>")
                    detail = QLabel("")
                    detail.setWordWrap(True)
                    note = QLabel(
                        "Large bundles can contain tens of thousands of Unity objects. "
                        "UBE is still working and will open the asset tree automatically."
                    )
                    note.setWordWrap(True)
                    try:
                        note.setStyleSheet("color: palette(mid);")
                    except Exception:
                        pass
                    layout.addWidget(heading)
                    layout.addWidget(detail)
                    layout.addWidget(note)
                    dlg.setMinimumWidth(470)
                    self._loading_dialog = dlg
                    self._loading_heading_label = heading
                    self._loading_detail_label = detail

                if self._loading_heading_label is not None:
                    self._loading_heading_label.setText("<b>Loading bundle — please wait…</b>")
                self._update_loading_notice(f"Preparing {Path(path).name}…", pump=False)
                self._loading_dialog.adjustSize()
                self._loading_dialog.show()
                self._loading_dialog.raise_()
                self._loading_dialog.activateWindow()
                self._pump_loading_events(80)
            except Exception:
                try:
                    self.statusBar().showMessage("Loading bundle — please wait…")
                except Exception:
                    pass

        def _update_loading_notice(self, detail: str, pump: bool = True) -> None:
            text = str(detail or "Loading bundle — please wait…")
            try:
                if self._loading_detail_label is not None:
                    self._loading_detail_label.setText(text)
                if self._loading_dialog is not None and self._loading_dialog.isVisible():
                    self._loading_dialog.adjustSize()
            except Exception:
                pass
            try:
                self.statusBar().showMessage(text)
            except Exception:
                pass
            if pump:
                self._pump_loading_events()

        def _hide_loading_notice(self, success: bool = True) -> None:
            try:
                if self._loading_dialog is not None:
                    self._loading_dialog.hide()
            except Exception:
                pass
            try:
                if success:
                    self.statusBar().showMessage("Bundle loaded", 2500)
                else:
                    self.statusBar().clearMessage()
            except Exception:
                pass
            self._pump_loading_events(40)

        def _load_bundle_responsive(self, path: Path, include_objects: bool = True):
            """Run UnityPy decoding off the GUI thread while keeping the wait notice alive."""
            state = {
                "message": f"Opening {Path(path).name}…",
                "result": None,
                "error": None,
            }
            lock = threading.Lock()

            def report(message: str) -> None:
                with lock:
                    state["message"] = str(message or state["message"])

            def worker() -> None:
                try:
                    result = load_bundle(path, include_objects=include_objects, progress_callback=report)
                    with lock:
                        state["result"] = result
                except BaseException as exc:
                    with lock:
                        state["error"] = exc

            thread = threading.Thread(
                target=worker,
                name=f"UBE bundle loader: {Path(path).name}",
                daemon=True,
            )
            thread.start()

            last_message = ""
            while thread.is_alive():
                with lock:
                    message = str(state.get("message") or "Loading bundle — please wait…")
                if message != last_message:
                    self._update_loading_notice(message, pump=False)
                    last_message = message
                self._pump_loading_events(50)
                thread.join(0.04)

            thread.join()
            with lock:
                error = state.get("error")
                result = state.get("result")
            if error is not None:
                raise error
            return result

        def _run_loading_task_responsive(self, detail: str, work):
            """Run a non-Qt loading/finalisation task away from the GUI thread.

            Bundle decoding was already moved off-thread in v2.0k, but large
            bundles can still spend several seconds sorting records or building
            the summary dashboard.  This helper keeps the real Qt event loop
            servicing Windows messages while those CPU/data tasks run.

            ``work`` receives ``report(message)`` and returns its result.  It must
            not create or modify Qt widgets; the caller applies the result back
            on the GUI thread.
            """
            state = {"message": str(detail or "Working…"), "result": None, "error": None}
            lock = threading.Lock()

            def report(message: str) -> None:
                with lock:
                    state["message"] = str(message or state["message"])

            def worker() -> None:
                try:
                    result = work(report)
                    with lock:
                        state["result"] = result
                except BaseException as exc:
                    with lock:
                        state["error"] = exc

            thread = threading.Thread(target=worker, name="UBE bundle finaliser", daemon=True)
            thread.start()
            last_message = ""
            while thread.is_alive():
                with lock:
                    message = str(state.get("message") or detail or "Working…")
                if message != last_message:
                    self._update_loading_notice(message, pump=False)
                    last_message = message
                self._pump_loading_events(35)
                thread.join(0.025)

            thread.join()
            with lock:
                error = state.get("error")
                result = state.get("result")
            if error is not None:
                raise error
            return result

        def _animation_work_elapsed_seconds(self) -> float:
            try:
                started = float(getattr(self, "_animation_work_started", 0.0) or 0.0)
                return max(0.0, time.monotonic() - started) if started > 0.0 else 0.0
            except Exception:
                return 0.0

        def _show_animation_work_notice(self, clip_name: str) -> None:
            """Show honest stage feedback while one AnimationClip preview is built."""
            self._animation_work_started = time.monotonic()
            try:
                if self._animation_work_dialog is None:
                    dlg = QDialog(self)
                    dlg.setWindowTitle("Preparing animation preview")
                    dlg.setWindowModality(Qt.ApplicationModal)
                    try:
                        dlg.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                        dlg.setWindowFlag(Qt.WindowCloseButtonHint, False)
                    except Exception:
                        pass
                    layout = QVBoxLayout(dlg)
                    layout.setContentsMargins(24, 20, 24, 20)
                    layout.setSpacing(9)

                    heading = QLabel("<b>Preparing animation preview — please wait…</b>")
                    detail_label = QLabel("")
                    detail_label.setWordWrap(True)
                    elapsed_label = QLabel("Elapsed: 0.0 s")
                    note = QLabel(
                        "UBE reports substantial stages and bounded renderer/pose checks only. "
                        "It does not update for every vertex or every authored frame."
                    )
                    note.setWordWrap(True)
                    try:
                        elapsed_label.setStyleSheet("color: palette(mid);")
                        note.setStyleSheet("color: palette(mid);")
                    except Exception:
                        pass
                    layout.addWidget(heading)
                    layout.addWidget(detail_label)
                    layout.addWidget(elapsed_label)
                    layout.addWidget(note)
                    dlg.setMinimumWidth(520)
                    self._animation_work_dialog = dlg
                    self._animation_work_heading_label = heading
                    self._animation_work_detail_label = detail_label
                    self._animation_work_elapsed_label = elapsed_label

                if self._animation_work_heading_label is not None:
                    safe_name = escape(str(clip_name or "AnimationClip"))
                    self._animation_work_heading_label.setText(
                        f"<b>Preparing animation preview — {safe_name}</b>"
                    )
                self._update_animation_work_notice("Reading AnimationClip data…", pump=False)
                self._animation_work_dialog.adjustSize()
                self._animation_work_dialog.show()
                self._animation_work_dialog.raise_()
                self._animation_work_dialog.activateWindow()
                self._pump_modal_work_events(80)
            except Exception:
                try:
                    self.statusBar().showMessage("Preparing animation preview — please wait…")
                except Exception:
                    pass

        def _update_animation_work_notice(self, detail: str, pump: bool = True) -> None:
            text = str(detail or "Preparing animation preview…")
            elapsed = self._animation_work_elapsed_seconds()
            try:
                if self._animation_work_detail_label is not None:
                    self._animation_work_detail_label.setText(text)
                if self._animation_work_elapsed_label is not None:
                    self._animation_work_elapsed_label.setText(f"Elapsed: {elapsed:.1f} s")
                if self._animation_work_dialog is not None and self._animation_work_dialog.isVisible():
                    self._animation_work_dialog.adjustSize()
            except Exception:
                pass
            try:
                if getattr(self, "animation_controls", None) is not None and self.animation_controls.isVisible():
                    self.animation_status_label.setText(text)
                self.statusBar().showMessage(text)
            except Exception:
                pass
            if pump:
                self._pump_modal_work_events(45)

        def _hide_animation_work_notice(self, success: bool = True) -> None:
            try:
                if self._animation_work_dialog is not None:
                    self._animation_work_dialog.hide()
            except Exception:
                pass
            self._pump_modal_work_events(30)

        def _show_export_work_notice(self, detail: str = "Preparing export…") -> None:
            """Show a simple responsive wait notice for native asset exports."""
            try:
                if self._export_work_dialog is None:
                    dlg = QDialog(self)
                    dlg.setWindowTitle("Exporting Unity assets")
                    dlg.setWindowModality(Qt.ApplicationModal)
                    try:
                        dlg.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                        dlg.setWindowFlag(Qt.WindowCloseButtonHint, False)
                    except Exception:
                        pass
                    layout = QVBoxLayout(dlg)
                    layout.setContentsMargins(24, 20, 24, 20)
                    layout.setSpacing(10)

                    heading = QLabel("<b>Exporting — please wait…</b>")
                    detail_label = QLabel("")
                    detail_label.setWordWrap(True)
                    note = QLabel(
                        "Large parent groups can require many child meshes, materials and textures to be decoded. "
                        "UBE is still working and will show the result automatically."
                    )
                    note.setWordWrap(True)
                    try:
                        note.setStyleSheet("color: palette(mid);")
                    except Exception:
                        pass
                    layout.addWidget(heading)
                    layout.addWidget(detail_label)
                    layout.addWidget(note)
                    dlg.setMinimumWidth(500)
                    self._export_work_dialog = dlg
                    self._export_work_heading_label = heading
                    self._export_work_detail_label = detail_label

                if self._export_work_heading_label is not None:
                    self._export_work_heading_label.setText("<b>Exporting — please wait…</b>")
                self._update_export_work_notice(detail, pump=False)
                self._export_work_dialog.adjustSize()
                self._export_work_dialog.show()
                self._export_work_dialog.raise_()
                self._export_work_dialog.activateWindow()
                self._pump_modal_work_events(80)
            except Exception:
                try:
                    self.statusBar().showMessage("Exporting — please wait…")
                except Exception:
                    pass

        def _update_export_work_notice(self, detail: str, pump: bool = True) -> None:
            text = str(detail or "Exporting — please wait…")
            try:
                if self._export_work_detail_label is not None:
                    self._export_work_detail_label.setText(text)
                if self._export_work_dialog is not None and self._export_work_dialog.isVisible():
                    self._export_work_dialog.adjustSize()
            except Exception:
                pass
            try:
                self.statusBar().showMessage(text)
            except Exception:
                pass
            if pump:
                self._pump_modal_work_events(40)

        def _hide_export_work_notice(self, success: bool = True) -> None:
            try:
                if self._export_work_dialog is not None:
                    self._export_work_dialog.hide()
            except Exception:
                pass
            try:
                if success:
                    self.statusBar().showMessage("Export completed", 2500)
                else:
                    self.statusBar().showMessage("Export stopped", 3500)
            except Exception:
                pass
            self._pump_modal_work_events(40)

        def _run_export_task_responsive(self, detail: str, work):
            """Run one expensive export operation off the GUI thread.

            ``work`` receives a small report(message) callback and returns the
            normal exporter result.  The calling method remains synchronous, but
            Qt/Windows keeps repainting and the application remains responsive.
            """
            state = {"message": str(detail or "Exporting…"), "result": None, "error": None}
            lock = threading.Lock()

            def report(message: str) -> None:
                with lock:
                    state["message"] = str(message or state["message"])

            def worker() -> None:
                try:
                    result = work(report)
                    with lock:
                        state["result"] = result
                except BaseException as exc:
                    with lock:
                        state["error"] = exc

            thread = threading.Thread(target=worker, name="UBE native asset exporter", daemon=True)
            thread.start()
            last_message = ""
            while thread.is_alive():
                with lock:
                    message = str(state.get("message") or detail or "Exporting…")
                if message != last_message:
                    self._update_export_work_notice(message, pump=False)
                    last_message = message
                self._pump_modal_work_events(50)
                thread.join(0.04)

            thread.join()
            with lock:
                error = state.get("error")
                result = state.get("result")
            if error is not None:
                raise error
            return result

        def _safe_preflight_bundle_load(self, path: Path) -> tuple[bool, str]:
            """Run UnityPy bundle parsing in a child process before opening in the UI.

            A few third-party bundles can make UnityPy or a native decompressor end
            the Python process instead of raising a normal exception. If that
            happens inside the main Qt app, UBE simply disappears. This preflight
            isolates that risk: if the child process crashes, the UI opens a
            header-only bundle page with a useful error instead of quitting.
            """
            code = r"""
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
try:
    import UnityPy  # type: ignore
    env = UnityPy.load(str(p))
    count = 0
    read_ok = 0
    read_fail = 0
    # Walk the same broad path as UBE's normal loader: enumerate objects and
    # try a lightweight read, because some failures happen only when records
    # are decoded rather than when the UnityFS container is opened.
    for obj in env.objects:
        count += 1
        try:
            data = obj.read()
            # Touch the common name fields but do not keep decoded data.
            _ = getattr(data, 'name', None) or getattr(data, 'm_Name', None)
            read_ok += 1
        except Exception:
            read_fail += 1
    print(json.dumps({'ok': True, 'objects': count, 'read_ok': read_ok, 'read_fail': read_fail}))
except BaseException as exc:
    print(json.dumps({'ok': False, 'error': repr(exc), 'type': type(exc).__name__}))
    sys.exit(3)
"""
            kwargs = {}
            try:
                if sys.platform.startswith("win") and hasattr(subprocess, "CREATE_NO_WINDOW"):
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            except Exception:
                pass
            self._update_loading_notice(f"Safety-checking {path.name} in an isolated loader…")
            try:
                process = subprocess.Popen(
                    [sys.executable, "-c", code, str(path)],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    **kwargs,
                )
            except Exception as exc:
                return False, f"UnityPy preflight could not be started: {exc}"

            started = time.monotonic()
            timed_out = False
            while process.poll() is None:
                if time.monotonic() - started >= 90.0:
                    timed_out = True
                    try:
                        process.kill()
                    except Exception:
                        pass
                    break
                self._pump_loading_events(40)
                time.sleep(0.035)

            try:
                stdout_raw, stderr_raw = process.communicate(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
                stdout_raw, stderr_raw = process.communicate()

            if timed_out:
                return False, "UnityPy preflight timed out after 90 seconds; opened header-only to avoid freezing/quitting the UI."

            stdout = (stdout_raw or "").strip()
            stderr = (stderr_raw or "").strip()
            returncode = int(process.returncode or 0)
            parsed = None
            if stdout:
                # Use the last JSON-looking line; native libraries may print warnings first.
                for line in reversed(stdout.splitlines()):
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            parsed = json.loads(line)
                            break
                        except Exception:
                            pass
            if returncode != 0:
                detail = ""
                if parsed and parsed.get("error"):
                    detail = str(parsed.get("error"))
                elif stderr:
                    detail = stderr[-1200:]
                elif stdout:
                    detail = stdout[-1200:]
                else:
                    detail = f"child process exited with code {returncode}"
                return False, f"UnityPy preflight failed or crashed before UI load: {detail}"
            if parsed and parsed.get("ok") is True:
                return True, f"preflight ok: {parsed.get('objects', '?')} objects, {parsed.get('read_fail', 0)} read warning(s)"
            return True, "preflight completed"

        def _open_header_only_after_preflight_failure(self, path: Path, reason: str):
            self._hide_loading_notice(success=False)
            idx = load_bundle(path, include_objects=False)
            idx.error = (
                "Safe open guard blocked full object loading. "
                "The file header was read, but UnityPy/object decoding failed in a child process. "
                f"Reason: {reason}"
            )
            idx.safe_open_state = "header_only"
            idx.safe_open_detail = reason
            self.bundle_index = idx
            self.comment_store.load_for_bundle(idx)
            self.asset_graph = AssetGraph()
            self.item_by_path_id = {}
            self.item_by_comment_key = {}
            self.history = []
            self.history_index = -1
            self.update_navigation_actions()
            self.setWindowTitle(full_title(f"{path.name} (header only)"))
            self.populate_bundle_tree()
            try:
                QMessageBox.warning(
                    self,
                    "Bundle opened header-only",
                    "UBE stopped this bundle from being fully decoded because the loader failed in a safe child process.\n\n"
                    "The app has stayed open and the UnityFS header/details are shown.\n\n"
                    f"{reason}",
                )
            except Exception:
                pass

        def load_path(self, path: Path, from_project: bool = False, add_recent: bool = False):
            self._show_loading_notice(path)
            succeeded = False
            try:
                result = self._load_path_impl(path, from_project=from_project, add_recent=add_recent)
                succeeded = True
                return result
            finally:
                self._hide_loading_notice(success=succeeded)

        def _load_path_impl(self, path: Path, from_project: bool = False, add_recent: bool = False):
            self.tree.clear()
            self.search.clear()
            self.clear_branch_filter(apply_now=False)
            self.clear_asset_type_isolation(apply_now=False)
            self.asset_type_items = {}
            self.preview.setText("Loading…")
            self._update_loading_notice(f"Preparing {path.name}…")
            ok, preflight_note = self._safe_preflight_bundle_load(path)
            if not ok:
                if add_recent and not from_project:
                    self.add_recent_item("bundle", path)
                if not from_project:
                    self.pathid_index = None
                    idx_file = index_path(path.parent)
                    self.pathid_index_status = f"Available: {idx_file.name} (manual --pathID lookup)" if idx_file.exists() else f"Missing ({idx_file.name})"
                    self.project_index = None
                    self.current_project_folder = None
                    self.serialized_assets_folder = None
                    self.update_return_source_action()
                else:
                    self.update_return_source_action()
                self._open_header_only_after_preflight_failure(path, preflight_note)
                return

            self._update_loading_notice(f"Decoding {path.name}…")
            self.bundle_index = self._load_bundle_responsive(path)
            try:
                self.bundle_index.safe_open_state = "full_load"
                self.bundle_index.safe_open_detail = preflight_note
            except Exception:
                pass
            if add_recent and not from_project:
                self.add_recent_item("bundle", path)
            if not from_project:
                # Direct source open: never parse the global PathID index here.
                self.pathid_index = None
                idx_file = index_path(path.parent)
                self.pathid_index_status = f"Available: {idx_file.name} (manual --pathID lookup)" if idx_file.exists() else f"Missing ({idx_file.name})"
            # When the user has opened a project/folder, or even a single bundle
            # from a folder of course bundles, try to resolve external references
            # against likely sibling bundles.  This turns "External asset" into
            # a named, clickable relationship where possible.
            self._update_loading_notice("Finding related course bundles…")
            resolver_project = self.project_index
            if resolver_project is None:
                try:
                    resolver_project = scan_project_folder(path.parent)
                except Exception:
                    resolver_project = None
            self.attach_project_external_references(resolver_project, path)

            # v1.8q: SerializedFile folder mode.  .assets/globalgamemanagers/level
            # files often point to sibling SerializedFiles such as
            # "unity default resources" by FileID + PathID.  We keep the first
            # pass deliberately simple: load nearby SerializedFile sources and
            # attach their records as external PathID candidates, just like the
            # existing related-bundle resolver does for AssetBundles.
            try:
                if getattr(self.bundle_index.header, "source_kind", "") == "unity_serialized_file":
                    self.attach_serialized_folder_external_references(path)
            except Exception as exc:
                try:
                    if self.bundle_index is not None:
                        old_error = getattr(self.bundle_index, "external_error", "") or ""
                        self.bundle_index.external_error = (old_error + "; " if old_error else "") + f"Serialized sibling resolver failed: {exc}"
                except Exception:
                    pass

            self._update_loading_notice("Loading external comments…")
            comment_result = self.comment_store.load_for_bundle(self.bundle_index)
            self.asset_graph = AssetGraph()
            self.item_by_path_id = {}
            self.item_by_comment_key = {}
            self.history = []
            self.history_index = -1
            self.update_navigation_actions()
            if not from_project:
                self.project_index = None
                self.current_project_folder = None
                self.serialized_assets_folder = None
                self.update_return_source_action()
            else:
                self.update_return_source_action()
            self.setWindowTitle(full_title(path.name))
            self._update_loading_notice("Building the asset tree…")
            self.populate_bundle_tree()
            self._show_comment_load_status(comment_result)

        def _same_file_path(self, a: Path, b: Path) -> bool:
            try:
                return Path(a).resolve() == Path(b).resolve()
            except Exception:
                return Path(a).absolute() == Path(b).absolute()

        def _serialized_resolver_folder_for(self, current_path: Path) -> Path | None:
            """Return the folder to use for SerializedFile sibling resolution."""
            try:
                if getattr(self, "serialized_assets_folder", None) is not None:
                    folder = Path(self.serialized_assets_folder)
                    if folder.exists():
                        return folder
            except Exception:
                pass
            try:
                return Path(current_path).parent
            except Exception:
                return None

        def attach_serialized_folder_external_references(self, current_path: Path):
            """Attach sibling Unity SerializedFile sources as external maps.

            This is for older/desktop Unity layouts such as:

                Game_Data/
                  level0
                  globalgamemanagers
                  sharedassets0.assets
                  resources.assets
                  unity default resources
                  sharedassets0.assets.resS

            The .assets/level file is the object database.  .resS/.resource files
            are sidecar byte stores and are not opened directly.  Sibling
            SerializedFiles can still contain real Mesh/Material/Texture objects
            referenced by FileID + PathID, so we load a capped set and add them to
            the current index's external maps.

            First pass note: UBE's existing external maps are PathID-keyed, so
            this is a practical resolver rather than a perfect FileID table.
            PathID collisions are detected and reported.
            """
            if self.bundle_index is None:
                return

            folder = self._serialized_resolver_folder_for(current_path)
            if folder is None or not Path(folder).exists():
                return

            try:
                candidates = self._serialized_assets_candidates(Path(folder))
            except Exception as exc:
                self.bundle_index.external_error = f"Could not scan SerializedFile siblings: {exc}"
                return

            paths = []
            for p in candidates:
                try:
                    if self._same_file_path(Path(p), Path(current_path)):
                        continue
                except Exception:
                    pass
                # Avoid loading split fragments directly.
                if ".split" in Path(p).name.lower():
                    continue
                paths.append(Path(p))

            if not paths:
                old_error = getattr(self.bundle_index, "external_error", "") or ""
                note = "No sibling Unity SerializedFile sources found for external references"
                self.bundle_index.external_error = (old_error + "; " if old_error else "") + note
                return

            current_ids = set(getattr(self.bundle_index, "record_by_path_id", {}).keys())
            external_records = dict(getattr(self.bundle_index, "external_record_by_path_id", {}) or {})
            external_records_by_type = {
                str(type_name): list(records)
                for type_name, records in (getattr(self.bundle_index, "external_records_by_type", {}) or {}).items()
            }
            external_bundles = dict(getattr(self.bundle_index, "external_bundle_by_path_id", {}) or {})
            cache = getattr(self, "external_bundle_cache", {})
            loaded = 0
            loaded_objects = 0
            errors = []
            collisions = 0

            # Older Steam/desktop folders can contain many scene/asset files.
            # Keep this first pass friendly and safe.
            max_related_paths = 24

            for p in paths[:max_related_paths]:
                try:
                    key = self._cache_key_for_bundle(Path(p))
                except Exception:
                    key = str(p)

                try:
                    ext_idx = cache.get(key)
                    if ext_idx is None:
                        ok, preflight_note = self._safe_preflight_bundle_load(p)
                        if not ok:
                            errors.append(f"{p.name}: safe preflight blocked load: {preflight_note}")
                            continue
                        self._update_loading_notice(f"Loading related source {p.name}…")
                        ext_idx = self._load_bundle_responsive(p)
                        cache[key] = ext_idx
                except Exception as exc:
                    errors.append(f"{p.name}: {exc}")
                    continue

                if getattr(ext_idx, "error", ""):
                    errors.append(f"{p.name}: {ext_idx.error}")

                loaded += 1
                loaded_objects += getattr(ext_idx, "object_count", 0)

                for type_name, records in getattr(ext_idx, "objects_by_type", {}).items():
                    bucket = external_records_by_type.setdefault(str(type_name), [])
                    known = {
                        (str(getattr(x, "source_file", "") or ""), str(getattr(x, "source_name", "") or ""), int(getattr(x, "path_id", 0) or 0))
                        for x in bucket
                    }
                    for rec in records:
                        key_rec = (
                            str(getattr(rec, "source_file", "") or ""),
                            str(getattr(rec, "source_name", "") or ""),
                            int(getattr(rec, "path_id", 0) or 0),
                        )
                        if key_rec not in known:
                            bucket.append(rec)
                            known.add(key_rec)

                for pid, rec in getattr(ext_idx, "record_by_path_id", {}).items():
                    try:
                        ipid = int(pid)
                    except Exception:
                        continue

                    if ipid in current_ids:
                        # Local object wins.
                        continue

                    existing = external_records.get(ipid)
                    if existing is None:
                        external_records[ipid] = rec
                        external_bundles[ipid] = Path(p)
                        continue

                    # Prefer a real loaded object over a metadata-only lazy index record.
                    if getattr(existing, "object", None) is None and getattr(rec, "object", None) is not None:
                        external_records[ipid] = rec
                        external_bundles[ipid] = Path(p)
                        continue

                    # Otherwise keep first match and report possible ambiguity.
                    old_path = external_bundles.get(ipid)
                    try:
                        same_old = old_path is not None and self._same_file_path(Path(old_path), Path(p))
                    except Exception:
                        same_old = False
                    if not same_old:
                        collisions += 1

            if len(paths) > max_related_paths:
                errors.append(f"Skipped {len(paths) - max_related_paths} extra SerializedFile sibling(s) after safety cap")
            if collisions:
                errors.append(f"{collisions} external PathID collision(s) kept first match; true FileID table is future work")

            self.external_bundle_cache = cache
            self.bundle_index.external_record_by_path_id = external_records
            self.bundle_index.external_records_by_type = external_records_by_type
            self.bundle_index.external_bundle_by_path_id = external_bundles
            self.bundle_index.external_bundle_count = loaded
            self.bundle_index.external_object_count = loaded_objects

            old_error = getattr(self.bundle_index, "external_error", "") or ""
            note = (
                f"Serialized sibling resolver loaded {loaded} source file(s), "
                f"{loaded_objects:,} external object(s). "
                ".resS/.resource sidecars are used indirectly by UnityPy where available."
            )
            combined = [x for x in [old_error, note, "; ".join(errors[:6])] if x]
            self.bundle_index.external_error = "; ".join(combined)


        def attach_project_external_references(self, project, current_path: Path):
            """Attach external reference candidates without loading the whole game.

            Build 134 tried to resolve references by opening every indexed bundle.
            That is too expensive for a full Walkabout install.  This version does:

            1. Load only the obvious course/sibling bundles, e.g. scene -> common.
            2. Do NOT auto-parse the whole-project PathID JSON.  Large games can
               have millions of objects, so global PathID searches are now a
               manual/lazy single-PathID lookup instead of UI startup work.
            """
            if self.bundle_index is None or project is None:
                return

            try:
                related = related_bundle_paths(project, current_path)
            except Exception as e:
                self.bundle_index.external_error = f"Could not find related bundles: {e}"
                related = []

            def _same_path(a: Path, b: Path) -> bool:
                try:
                    return a.resolve() == b.resolve()
                except Exception:
                    return a.absolute() == b.absolute()

            paths = []
            for p in list(related):
                if _same_path(Path(p), current_path):
                    continue
                if not any(_same_path(Path(p), existing) for existing in paths):
                    paths.append(Path(p))

            current_ids = set(getattr(self.bundle_index, "record_by_path_id", {}).keys())
            external_records = {}
            external_records_by_type = {}
            external_bundles = {}
            loaded = 0
            loaded_objects = 0
            errors = []

            # Cache the small course-local bundle indexes while the project stays open.
            cache = getattr(self, "external_bundle_cache", {})

            # Course-local only.  No full-project bundle loading here.
            max_related_paths = 12
            for p in paths[:max_related_paths]:
                try:
                    key = str(Path(p).resolve())
                except Exception:
                    key = str(p)
                try:
                    ext_idx = cache.get(key)
                    if ext_idx is None:
                        ok, preflight_note = self._safe_preflight_bundle_load(p)
                        if not ok:
                            errors.append(f"{p.name}: safe preflight blocked external resolver load: {preflight_note}")
                            continue
                        self._update_loading_notice(f"Loading related source {p.name}…")
                        ext_idx = self._load_bundle_responsive(p)
                        cache[key] = ext_idx
                except Exception as e:
                    errors.append(f"{p.name}: {e}")
                    continue
                if getattr(ext_idx, "error", ""):
                    errors.append(f"{p.name}: {ext_idx.error}")
                loaded += 1
                loaded_objects += getattr(ext_idx, "object_count", 0)
                for type_name, records in getattr(ext_idx, "objects_by_type", {}).items():
                    bucket = external_records_by_type.setdefault(str(type_name), [])
                    bucket.extend(records)
                for pid, rec in getattr(ext_idx, "record_by_path_id", {}).items():
                    if pid in current_ids:
                        continue
                    if pid not in external_records:
                        external_records[pid] = rec
                        external_bundles[pid] = p

            if len(paths) > max_related_paths:
                errors.append(f"Skipped {len(paths) - max_related_paths} extra related bundle(s) after safety cap")

            # Build 136: no automatic global JSON expansion here.
            # It was accurate, but far too slow with multi-million-object games.
            if getattr(project, "folder", None) is not None and index_path(project.folder).exists():
                errors.append("Global PathID index available; UI uses fast course-local references plus lazy single-PathID lookup")
            elif getattr(project, "folder", None) is not None:
                errors.append(f"No project PathID index; using course-local references only. Optional: python -m unity_bundle_explorer.build_pathid_index \"{project.folder}\"")

            self.external_bundle_cache = cache
            self.bundle_index.external_record_by_path_id = external_records
            self.bundle_index.external_records_by_type = external_records_by_type
            self.bundle_index.external_bundle_by_path_id = external_bundles
            self.bundle_index.external_bundle_count = loaded
            self.bundle_index.external_object_count = loaded_objects
            self.bundle_index.external_error = "; ".join(errors[:6])

        def _asset_tree_label(self, rec, has_comment: bool | None = None) -> str:
            if has_comment is None:
                has_comment = bool(self.comment_store.get(rec).strip())
            label = display_name_with_icon(rec.name, rec.type_name)
            return f"{label}  💬" if has_comment else label

        def _comment_tree_text(self, comment: str) -> str:
            """Keep the full comment searchable while presenting it as one tree row."""
            return re.sub(r"\s+", " ", str(comment or "")).strip()

        def _show_comment_load_status(self, result) -> None:
            try:
                if result is None:
                    return
                if getattr(result, "matched_existing", False):
                    self.statusBar().showMessage(getattr(result, "message", "Comments loaded"), 5000)
                elif str(getattr(result, "message", "")).startswith("Could not read"):
                    self.statusBar().showMessage(getattr(result, "message", "Comment JSON error"), 7000)
            except Exception:
                pass

        def _refresh_comment_tree_item(self, rec) -> None:
            try:
                key = self.comment_store.record_key(rec)
                item = self.item_by_comment_key.get(key)
                if item is None:
                    return
                comment = self.comment_store.get(rec)
                item.setText(0, self._asset_tree_label(rec, bool(comment.strip())))
                item.setText(3, self._comment_tree_text(comment))
                if self.has_active_tree_filter():
                    self.apply_tree_filter(self.search.text())
            except Exception:
                pass

        def _external_comment_html(self, rec) -> list[str]:
            comment = self.comment_store.get(rec)
            filename = ""
            try:
                if self.comment_store.file_path is not None:
                    filename = self.comment_store.file_path.name
            except Exception:
                filename = ""
            if comment.strip():
                return [
                    "<div class='card'>",
                    "<div class='head'>💬 External comment "
                    "<span class='badge'><a href='ube://comment/edit'>Edit</a></span></div>",
                    f"<pre>{escape(comment)}</pre>",
                    (f"<div class='muted' style='margin-top:6px'>JSON: {escape(filename)}</div>" if filename else ""),
                    "</div>",
                ]
            return [
                "<div class='card'>",
                "<div class='head'>💬 External comment</div>",
                "<a href='ube://comment/edit'>Click here to add a descriptive comment…</a>",
                (f"<div class='muted' style='margin-top:6px'>Will be stored in UBE_Comments/{escape(filename)}</div>" if filename else ""),
                "</div>",
            ]

        def edit_comment_for_record(self, rec=None) -> None:
            rec = rec or self.selected_record
            if rec is None or isinstance(rec, tuple):
                return

            dlg = QDialog(self)
            dlg.setWindowTitle(f"External comment — {getattr(rec, 'name', 'Asset')}")
            dlg.resize(760, 420)
            layout = QVBoxLayout(dlg)

            identity = QLabel(
                f"{friendly_type_name(getattr(rec, 'type_name', ''))}  |  "
                f"Path ID {getattr(rec, 'path_id', '')}  |  "
                f"SerializedFile: {getattr(rec, 'source_name', '') or '-'}"
            )
            identity.setWordWrap(True)
            layout.addWidget(identity)

            editor = QPlainTextEdit(dlg)
            # Tell the application-level preview shortcut filter that this widget
            # must receive normal keyboard input without single-key interception.
            editor.setProperty("ube_text_entry", True)
            editor.setPlaceholderText("Enter any useful description, identification note, location, or research comment…")
            editor.setPlainText(self.comment_store.get(rec))
            layout.addWidget(editor, 1)

            note = QLabel(
                "Saved as readable JSON and loaded automatically the next time this exact bundle/file is opened. "
                "There is no imposed comment length limit."
            )
            note.setWordWrap(True)
            layout.addWidget(note)

            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=dlg)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)
            editor.setFocus()

            if dlg.exec() != QDialog.Accepted:
                return

            new_text = editor.toPlainText()
            try:
                self.comment_store.set(rec, new_text)
                saved_path = self.comment_store.save()
                self._refresh_comment_tree_item(rec)
                if self.selected_record is rec or self.comment_store.record_key(self.selected_record) == self.comment_store.record_key(rec):
                    self.show_record_in_inspector(rec, push_history=False)
                action = "Cleared" if not new_text.strip() else "Saved"
                self.statusBar().showMessage(
                    f"{action} external comment — {saved_path.name} ({self.comment_store.count()} total)",
                    4500,
                )
            except Exception as exc:
                QMessageBox.warning(self, "External Comment", f"Could not save the comment JSON:\n{exc}")

        def clear_comment_for_record(self, rec=None) -> None:
            rec = rec or self.selected_record
            if rec is None or not self.comment_store.has(rec):
                return
            answer = QMessageBox.question(
                self,
                "Clear External Comment",
                f"Clear the external comment for:\n\n{getattr(rec, 'name', 'Asset')}\nPath ID {getattr(rec, 'path_id', '')}?",
            )
            if answer != QMessageBox.Yes:
                return
            try:
                self.comment_store.set(rec, "")
                saved_path = self.comment_store.save()
                self._refresh_comment_tree_item(rec)
                if self.selected_record is not None:
                    self.show_record_in_inspector(self.selected_record, push_history=False)
                self.statusBar().showMessage(f"Comment cleared — {saved_path.name}", 3000)
            except Exception as exc:
                QMessageBox.warning(self, "External Comment", f"Could not update the comment JSON:\n{exc}")

        def populate_bundle_tree(self):
            """Build the asset tree without starving the native Qt event loop.

            v2.0k pumped events every 500 rows, but the final QTreeWidget layout,
            column auto-sizing and bundle dashboard were still synchronous.
            Windows could therefore label the loading window Not Responding during
            the final stage.  This version sorts off-thread and inserts rows in
            short QTimer slices so Qt returns to its real event loop continuously.
            """
            idx = self.bundle_index
            if not idx:
                return
            exact_version = idx.header.unity_revision or idx.header.unity_version or "unknown"
            source_kind = getattr(idx.header, "source_kind", "") or ""
            source_label = "Unity SerializedFile" if source_kind == "unity_serialized_file" else "Bundle"
            comment_count = self.comment_store.count()
            comment_suffix = f"  |  {comment_count} comment{'s' if comment_count != 1 else ''}" if comment_count else ""
            root_text = f"{idx.path.name}  |  {source_label}  |  Unity {exact_version}  |  {idx.object_count} objects{comment_suffix}"
            root = QTreeWidgetItem([display_name_with_icon(root_text, "Bundle"), source_label, "", ""])
            self.tree.addTopLevelItem(root)

            self.item_by_comment_key = {}
            self.asset_type_items = {}

            def prepare_tree_plan(report):
                report("Sorting assets for the tree…")
                plan = []
                for type_name, records in sorted(idx.objects_by_type.items()):
                    plan.append((str(type_name), sorted(records, key=lambda r: str(getattr(r, "name", "")).lower())))
                return plan

            type_plan = self._run_loading_task_responsive("Sorting assets for the tree…", prepare_tree_plan)
            tree_total = max(1, sum(len(records) for _type_name, records in type_plan))
            tree_built = 0

            # Create the small type-heading layer first.  The expensive individual
            # records are inserted in short timer-driven batches below.
            parent_plan = []
            self.tree.setUpdatesEnabled(False)
            for type_name, records in type_plan:
                parent = QTreeWidgetItem([
                    display_name_with_icon(f"{friendly_type_name(type_name)} ({len(records)})", type_name),
                    friendly_type_name(type_name),
                    "",
                    "",
                ])
                root.addChild(parent)
                parent.setData(0, Qt.UserRole, ("asset_type", str(type_name)))
                self.asset_type_items[str(type_name)] = parent
                parent_plan.append((parent, records))

            state = {"type_index": 0, "record_index": 0, "error": None, "done": False}
            local_loop = QEventLoop()
            batch_timer = QTimer(self)
            batch_timer.setSingleShot(True)
            last_notice_time = [0.0]

            def finish_batches() -> None:
                state["done"] = True
                try:
                    local_loop.quit()
                except Exception:
                    pass

            def build_tree_slice() -> None:
                nonlocal tree_built
                try:
                    # A time budget is safer than a fixed item count: both cheap
                    # and unusually expensive records yield back to Windows before
                    # it reaches the hung-window timeout.
                    deadline = time.perf_counter() + 0.014
                    made = 0
                    while time.perf_counter() < deadline and made < 300:
                        ti = int(state["type_index"])
                        if ti >= len(parent_plan):
                            finish_batches()
                            return
                        parent, records = parent_plan[ti]
                        ri = int(state["record_index"])
                        if ri >= len(records):
                            state["type_index"] = ti + 1
                            state["record_index"] = 0
                            continue

                        rec = records[ri]
                        comment = self.comment_store.get(rec)
                        child = QTreeWidgetItem([
                            self._asset_tree_label(rec, bool(comment.strip())),
                            friendly_type_name(rec.type_name),
                            str(rec.path_id),
                            self._comment_tree_text(comment),
                        ])
                        child.setData(0, Qt.UserRole, rec)
                        parent.addChild(child)
                        self.item_by_path_id[rec.path_id] = child
                        self.item_by_comment_key[self.comment_store.record_key(rec)] = child
                        state["record_index"] = ri + 1
                        tree_built += 1
                        made += 1

                    now = time.monotonic()
                    if now - last_notice_time[0] >= 0.15 or tree_built >= tree_total:
                        self._update_loading_notice(
                            f"Building asset tree — {tree_built:,} / {tree_total:,} objects",
                            pump=False,
                        )
                        last_notice_time[0] = now
                    batch_timer.start(0)
                except BaseException as exc:
                    state["error"] = exc
                    finish_batches()

            batch_timer.timeout.connect(build_tree_slice)
            batch_timer.start(0)
            local_loop.exec()
            try:
                batch_timer.stop()
                batch_timer.timeout.disconnect(build_tree_slice)
            except Exception:
                pass
            if state.get("error") is not None:
                self.tree.setUpdatesEnabled(True)
                raise state["error"]

            self._update_loading_notice("Laying out the asset tree…", pump=False)
            root.setExpanded(True)
            self.apply_tree_column_visibility()

            # resizeColumnToContents scans every row.  It is convenient for small
            # bundles but can lock Qt for many seconds on a 100k-row tree.  Large
            # trees receive a sensible starting width and remain user-resizable.
            if tree_total <= 5000:
                self.tree.resizeColumnToContents(0)
            else:
                try:
                    self.tree.setColumnWidth(0, max(360, min(560, int(self.tree.columnWidth(0) or 0))))
                except Exception:
                    pass

            self.tree.setUpdatesEnabled(True)
            try:
                self.tree.viewport().update()
            except Exception:
                pass
            self._pump_loading_events(80)

            # The dashboard reads many Mesh/Material/Renderer records.  Build its
            # HTML in a worker and only assign the finished text to QTextBrowser
            # on the Qt thread.
            def build_dashboard(report):
                report("Analysing bundle summary…")
                return self._bundle_summary_html()

            dashboard_html = self._run_loading_task_responsive("Analysing bundle summary…", build_dashboard)
            self._update_loading_notice("Finalizing the bundle view…", pump=False)
            self.show_bundle_info(dashboard_html)
            self._pump_loading_events(80)

        def _bundle_dash_bytes(self, value) -> str:
            try:
                n = int(value or 0)
            except Exception:
                return "-"
            if n >= 1024 ** 3:
                return f"{n / (1024 ** 3):.2f} GB"
            if n >= 1024 ** 2:
                return f"{n / (1024 ** 2):.2f} MB"
            if n >= 1024:
                return f"{n / 1024:.1f} KB"
            return f"{n:,} B"

        def _bundle_dash_int(self, value, default: int = 0) -> int:
            try:
                return int(value if value is not None else default)
            except Exception:
                return default

        def _bundle_dash_record_link(self, rec, label: str | None = None) -> str:
            if rec is None:
                return "-"
            title = label or getattr(rec, "name", "") or f"PathID {getattr(rec, 'path_id', '-') }"
            return f"<a href='ube://asset/{int(getattr(rec, 'path_id', 0))}'>{escape(str(title))}</a>"

        def _bundle_dash_ref_link(self, path_id, fallback_type: str = "Asset") -> str:
            """Pretty dashboard link for local, course-local external, and lazy-index assets.

            The dashboard often sees material/texture references before the user
            has opened the referenced object.  Returning only "PathID ..." is
            technically correct but not very helpful, so this uses the same
            local/external/lazy resolver as the object inspector.
            """
            try:
                pid = int(path_id)
            except Exception:
                return f"<span class='unresolved'>PathID {escape(str(path_id))}</span>"
            if pid in (0, None):
                return "<span class='muted'>-</span>"
            return self._ov_asset_link(pid, fallback_type=fallback_type)

        def _bundle_dash_value_or_unavailable(self, value: int, known_count: int = 0) -> str:
            try:
                n = int(value or 0)
            except Exception:
                n = 0
            if known_count <= 0:
                return "unavailable"
            return f"{n:,}"

        def _bundle_dash_vertex_count_from_data(self, data) -> tuple[int, bool]:
            candidates = [
                self._ov_get(data, "m_VertexCount", "vertex_count", "vertexCount", default=None),
            ]
            vdata = self._ov_get(data, "m_VertexData", "vertex_data", "vertexData", default=None)
            if vdata is not None:
                candidates.append(self._ov_get(vdata, "m_VertexCount", "vertex_count", "vertexCount", default=None))
            for value in candidates:
                try:
                    if value is not None:
                        n = int(value)
                        if n > 0:
                            return n, True
                except Exception:
                    pass

            # Some older UnityPy layouts expose decoded arrays rather than an explicit count.
            for name in ("vertices", "m_Vertices", "Vertices"):
                seq = self._ov_get(data, name, default=None)
                try:
                    n = len(seq)
                    if n > 0:
                        return int(n), True
                except Exception:
                    pass
            return 0, False

        def _bundle_dash_mesh_stats(self, rec):
            data = self._ov_read(rec)
            if data is None:
                return 0, 0, 0, False
            verts, verts_known = self._bundle_dash_vertex_count_from_data(data)
            submeshes = self._ov_get(data, "m_SubMeshes", "sub_meshes", default=None)
            indices = 0
            if isinstance(submeshes, list):
                for sm in submeshes:
                    indices += self._bundle_dash_int(self._ov_get(sm, "indexCount", "m_IndexCount", "index_count", default=0))
            tris = indices // 3 if indices else 0
            return verts, tris, indices, verts_known

        def _bundle_dash_material_texture_slots(self, mat_rec):
            out = []
            data = self._ov_read(mat_rec)
            if data is None:
                return out
            saved = self._ov_get(data, "m_SavedProperties", "saved_properties", default=None)
            if saved is None:
                return out
            for item in self._ov_as_list(self._ov_get(saved, "m_TexEnvs", "tex_envs", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                texture = self._ov_get(value, "m_Texture", "texture", default=value)
                pid = self._ov_pptr_path_id(texture)
                if pid in (None, 0):
                    continue
                out.append((str(key), int(pid)))
            return out

        def _bundle_dash_renderer_material_pids(self, renderer_rec):
            data = self._ov_read(renderer_rec)
            if data is None:
                return []
            pids = []
            for item in self._ov_as_list(self._ov_get(data, "m_Materials", "materials", default=None)):
                pid = self._ov_pptr_path_id(item)
                if pid not in (None, 0):
                    pids.append(int(pid))
            return pids

        def _bundle_summary_html(self) -> str:
            idx = self.bundle_index
            if not idx:
                return ""

            type_counts = {name: len(records) for name, records in getattr(idx, "objects_by_type", {}).items()}
            records_by_pid = getattr(idx, "record_by_path_id", {})
            texture_rows = []
            texture_total_gpu = 0
            texture_total_decoded = 0
            texture_format_counts = {}
            for rec in getattr(idx, "objects_by_type", {}).get("Texture2D", []):
                try:
                    td = texture_details(rec)
                except Exception:
                    td = None
                if not td:
                    continue
                gpu = self._bundle_dash_int(td.stream_size, 0) or self._bundle_dash_int(td.complete_image_size, 0)
                decoded = 0
                if td.width and td.height:
                    decoded = self._bundle_dash_int(td.width) * self._bundle_dash_int(td.height) * 4
                texture_total_gpu += gpu
                texture_total_decoded += decoded
                fmt = td.texture_format or td.texture_format_raw or "unknown"
                texture_format_counts[fmt] = texture_format_counts.get(fmt, 0) + 1
                pixels = self._bundle_dash_int(td.width) * self._bundle_dash_int(td.height)
                texture_rows.append((gpu, pixels, rec, td, decoded))
            texture_rows.sort(key=lambda r: (r[0], r[1]), reverse=True)

            mesh_rows = []
            mesh_total_verts = 0
            mesh_total_verts_known = 0
            mesh_total_tris = 0
            mesh_read_errors = 0
            for rec in getattr(idx, "objects_by_type", {}).get("Mesh", []):
                try:
                    verts, tris, indices, verts_known = self._bundle_dash_mesh_stats(rec)
                except Exception:
                    verts = tris = indices = 0
                    verts_known = False
                    mesh_read_errors += 1
                if verts_known:
                    mesh_total_verts += verts
                    mesh_total_verts_known += 1
                mesh_total_tris += tris
                mesh_rows.append((tris, verts, rec, indices, verts_known))
            mesh_rows.sort(key=lambda r: (r[0], r[1]), reverse=True)

            # Allow a few dashboard rows to turn bare external PathIDs into names.
            # This keeps the dashboard readable without expanding the full global index.
            self._pathid_lookup_render_budget = 12

            # Material usage and texture usage are measured through renderer material slots.
            material_texture_slots = {}
            for mat in getattr(idx, "objects_by_type", {}).get("Material", []):
                try:
                    material_texture_slots[int(mat.path_id)] = self._bundle_dash_material_texture_slots(mat)
                except Exception:
                    material_texture_slots[int(mat.path_id)] = []

            material_use_counts = {}
            texture_use_counts = {}
            renderer_count = 0
            for type_name in ("MeshRenderer", "SkinnedMeshRenderer", "ParticleSystemRenderer", "SpriteRenderer", "TrailRenderer"):
                for renderer in getattr(idx, "objects_by_type", {}).get(type_name, []):
                    renderer_count += 1
                    try:
                        mat_pids = self._bundle_dash_renderer_material_pids(renderer)
                    except Exception:
                        mat_pids = []
                    seen_textures_for_renderer = set()
                    for mpid in mat_pids:
                        material_use_counts[mpid] = material_use_counts.get(mpid, 0) + 1
                        for slot, tpid in material_texture_slots.get(mpid, []):
                            seen_textures_for_renderer.add((tpid, slot))
                    for tpid, slot in seen_textures_for_renderer:
                        texture_use_counts[tpid] = texture_use_counts.get(tpid, 0) + 1

            top_materials = sorted(material_use_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
            top_textures = sorted(texture_use_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]

            important_types = [
                "GameObject", "Transform", "Mesh", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer",
                "Material", "Shader", "Texture2D", "Cubemap", "AudioClip", "AudioSource", "LODGroup", "Light", "ReflectionProbe",
                "LightProbeGroup", "LightingSettings", "LightmapSettings", "ParticleSystem", "ParticleSystemRenderer",
                "BoxCollider", "SphereCollider", "CapsuleCollider", "MeshCollider", "Rigidbody", "PhysicMaterial",
                "LineRenderer", "TrailRenderer", "SpriteMask", "TextAsset", "PlayableDirector",
                "NavMeshData", "NavMeshSettings", "NavMeshProjectSettings", "Canvas", "RectTransform", "MonoBehaviour",
            ]
            helper_counts = [(name, type_counts.get(name, 0)) for name in important_types if type_counts.get(name, 0)]

            largest_texture_items = []
            for gpu, pixels, rec, td, decoded in texture_rows[:10]:
                dims = f"{td.width or '?'}×{td.height or '?'}"
                fmt = td.texture_format or td.texture_format_raw or "-"
                largest_texture_items.append(
                    f"<li>{self._bundle_dash_record_link(rec)} <span class='muted'>— {dims}, {escape(fmt)}, GPU {self._bundle_dash_bytes(gpu)}, RGBA {self._bundle_dash_bytes(decoded)}</span></li>"
                )
            if not largest_texture_items:
                largest_texture_items.append("<li><span class='muted'>No Texture2D records found.</span></li>")

            largest_mesh_items = []
            for tris, verts, rec, indices, verts_known in mesh_rows[:10]:
                detail = []
                if verts_known:
                    detail.append(f"{verts:,} verts")
                if tris:
                    detail.append(f"~{tris:,} tris")
                if not detail:
                    detail.append("mesh stats not exposed")
                largest_mesh_items.append(f"<li>{self._bundle_dash_record_link(rec)} <span class='muted'>— {', '.join(detail)}</span></li>")
            if not largest_mesh_items:
                largest_mesh_items.append("<li><span class='muted'>No Mesh records found.</span></li>")

            top_texture_items = []
            for tpid, count in top_textures:
                link = self._bundle_dash_ref_link(tpid, fallback_type="Texture2D")
                top_texture_items.append(f"<li>{link} <span class='muted'>— used by about {count:,} renderer(s)</span></li>")
            if not top_texture_items:
                top_texture_items.append("<li><span class='muted'>No texture usage could be resolved through renderer materials.</span></li>")

            top_material_items = []
            for mpid, count in top_materials:
                link = self._bundle_dash_ref_link(mpid, fallback_type="Material")
                top_material_items.append(f"<li>{link} <span class='muted'>— used by about {count:,} renderer slot(s)</span></li>")
            if not top_material_items:
                top_material_items.append("<li><span class='muted'>No material usage could be resolved.</span></li>")

            type_count_items = []
            for name, count in sorted(type_counts.items(), key=lambda kv: kv[0].lower()):
                type_count_items.append(f"<tr><td>{escape(friendly_type_name(name))}</td><td style='text-align:right'>{count:,}</td></tr>")

            helper_badges = "".join(
                f"<span class='badge'>{escape(friendly_type_name(name))}: {count:,}</span>" for name, count in helper_counts
            ) or "<span class='muted'>No key object/component counts found.</span>"

            texture_formats = "".join(
                f"<span class='badge'>{escape(fmt)}: {count:,}</span>"
                for fmt, count in sorted(texture_format_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
            ) or "<span class='muted'>No texture formats found.</span>"

            exact_version = idx.header.unity_revision or idx.header.unity_version or "unknown"
            source_kind = getattr(idx.header, "source_kind", "") or ""
            source_label = "Unity SerializedFile" if source_kind == "unity_serialized_file" else "UnityFS Bundle"
            source_explain = (
                ".assets/globalgamemanagers/sharedassets/resources style Unity object database. "
                ".resS/.resource files are sidecar byte stores and are not opened directly. "
                "Sibling SerializedFiles may be loaded as external reference sources."
                if source_kind == "unity_serialized_file"
                else "UnityFS/UnityWeb/UnityRaw AssetBundle-style container."
            )
            errors = escape(getattr(idx, "error", "") or "-")
            ext_warn = escape(getattr(idx, "external_error", "") or "-")

            # A tiny classification hint. Keep this educational rather than authoritative.
            role_hints = []
            if type_counts.get("GameObject", 0) > 1000 and renderer_count > 500:
                role_hints.append("scene/object-heavy bundle")
            if texture_total_gpu > 100 * 1024 * 1024 or type_counts.get("Texture2D", 0) > 100:
                role_hints.append("texture-heavy/shared-assets bundle")
            if type_counts.get("AudioClip", 0) > 50:
                role_hints.append("audio-heavy bundle")
            if type_counts.get("LODGroup", 0) > 0:
                role_hints.append("uses LOD optimisation")
            if type_counts.get("ParticleSystem", 0) > 0:
                role_hints.append("contains VFX/particle setup")
            role_text = ", ".join(role_hints) if role_hints else "general Unity asset bundle"

            # Safe-open / header-only status.  This is deliberately shown near
            # the top of the dashboard because it explains why a problem bundle
            # may have a readable UnityFS header but zero decoded objects.
            safe_state = escape(getattr(idx, "safe_open_state", "") or "")
            safe_detail = escape(getattr(idx, "safe_open_detail", "") or "")
            header_readable = "yes" if str(getattr(idx.header, "signature", "")) in {"UnityFS", "UnityWeb", "UnityRaw", "UnitySerializedFile"} else "unknown/no"
            open_status_card = ""
            if safe_state == "header_only":
                open_status_card = f"""
<div class='card warn'>
  <div class='title'>⚠ Open status: header-only safe mode</div>
  <div><b>Header readable:</b> {header_readable}</div>
  <div><b>Full object decoding:</b> blocked by safe preflight</div>
  <div><b>Reason:</b> {safe_detail or '-'}</div>
  <div class='muted'>UBE kept the app open and showed the UnityFS header instead of letting a bad/problem bundle close the program.</div>
</div>
"""
            elif errors != "-":
                open_status_card = f"""
<div class='card warn'>
  <div class='title'>⚠ Open status: loaded with warnings</div>
  <div><b>Header readable:</b> {header_readable}</div>
  <div><b>Loader note:</b> {errors}</div>
</div>
"""
            elif safe_detail:
                open_status_card = f"""
<div class='card ok'>
  <div class='title'>✅ Open status: full load passed safe preflight</div>
  <div>{safe_detail}</div>
</div>
"""

            html = f"""
<html><body style='font-family: Segoe UI, Arial, sans-serif; font-size:10.5pt; color:#eee;'>
<style>
  a {{ color:#8ecbff; text-decoration:none; }}
  .card {{ border:1px solid #404040; border-radius:7px; margin:8px 0; padding:9px 11px; background:#252525; }}
  .title {{ font-weight:700; color:#fff; margin-bottom:6px; }}
  .muted {{ color:#aaa; }}
  .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; }}
  .metric {{ border:1px solid #3b3b3b; border-radius:6px; padding:8px; background:#2b2b2b; }}
  .num {{ font-size:15pt; font-weight:700; color:#fff; }}
  .label {{ color:#aaa; font-size:9pt; }}
  .badge {{ display:inline-block; border:1px solid #555; border-radius:9px; padding:1px 6px; margin:2px 4px 2px 0; color:#ddd; background:#303030; font-size:9pt; }}
  .external {{ color:#ffd27d; font-size:9pt; }}
  .unresolved {{ color:#ffad8e; }}
  .warn {{ border-color:#8a5a22; background:#2c261d; }}
  .ok {{ border-color:#38683e; background:#1f2b22; }}
  table {{ border-collapse:collapse; width:100%; }}
  td {{ border-bottom:1px solid #383838; padding:2px 6px; }}
  ul {{ margin-top:4px; padding-left:20px; }}
</style>
<div class='card'>
  <div class='title'>📦 Unity Source Summary Dashboard</div>
  <div><b>File:</b> {escape(str(idx.path))}</div>
  <div><b>Source type:</b> {escape(source_label)}</div>
  <div><b>Signature:</b> {escape(str(idx.header.signature))}</div>
  <div><b>Unity version string:</b> {escape(str(idx.header.unity_version))}</div>
  <div><b>Unity revision:</b> {escape(str(idx.header.unity_revision))}</div>
  <div><b>Detected role:</b> {escape(role_text)}</div>
  <div class='muted'>{escape(source_explain)}</div>
</div>
{open_status_card}
<div class='card grid'>
  <div class='metric'><div class='num'>{idx.object_count:,}</div><div class='label'>objects</div></div>
  <div class='metric'><div class='num'>{self._bundle_dash_bytes(idx.header.file_size)}</div><div class='label'>file size</div></div>
  <div class='metric'><div class='num'>{type_counts.get('Texture2D', 0):,}</div><div class='label'>Texture2D</div></div>
  <div class='metric'><div class='num'>{self._bundle_dash_bytes(texture_total_gpu)}</div><div class='label'>texture GPU/stream size</div></div>
  <div class='metric'><div class='num'>{type_counts.get('Mesh', 0):,}</div><div class='label'>meshes</div></div>
  <div class='metric'><div class='num'>{self._bundle_dash_value_or_unavailable(mesh_total_verts, mesh_total_verts_known)}</div><div class='label'>approx vertices</div></div>
  <div class='metric'><div class='num'>{mesh_total_tris:,}</div><div class='label'>approx triangles</div></div>
  <div class='metric'><div class='num'>{renderer_count:,}</div><div class='label'>renderers checked</div></div>
</div>
<div class='card'>
  <div class='title'>🧭 Scene / asset indicators</div>
  {helper_badges}
</div>
<div class='card'>
  <div class='title'>🖼 Texture overview</div>
  <div><b>Total compressed/GPU texture size:</b> {self._bundle_dash_bytes(texture_total_gpu)}</div>
  <div><b>Approx decoded RGBA size:</b> {self._bundle_dash_bytes(texture_total_decoded)}</div>
  <div style='margin-top:5px'>{texture_formats}</div>
  <div class='title' style='margin-top:10px'>Largest textures</div>
  <ol>{''.join(largest_texture_items)}</ol>
</div>
<div class='card'>
  <div class='title'>🧊 Mesh overview</div>
  <div><b>Total approximate vertices:</b> {self._bundle_dash_value_or_unavailable(mesh_total_verts, mesh_total_verts_known)}</div>
  <div><b>Total approximate triangles:</b> {mesh_total_tris:,}</div>
  <div class='muted'>Vertex totals use the explicit mesh vertex count when Unity exposes it; otherwise they show unavailable rather than a misleading zero.</div>
  <div class='muted'>Triangle totals are estimated from exposed submesh index counts; some Unity versions expose less detail.</div>
  <div class='title' style='margin-top:10px'>Largest meshes</div>
  <ol>{''.join(largest_mesh_items)}</ol>
</div>
<div class='card'>
  <div class='title'>🔗 Most-used visual assets</div>
  <div class='title'>Textures used by the most renderers</div>
  <ol>{''.join(top_texture_items)}</ol>
  <div class='title' style='margin-top:10px'>Materials used by the most renderers</div>
  <ol>{''.join(top_material_items)}</ol>
</div>
<div class='card'>
  <div class='title'>🌐 External resolver</div>
  <div>Related bundles loaded: {getattr(idx, 'external_bundle_count', 0):,}</div>
  <div>External PathIDs known: {len(getattr(idx, 'external_record_by_path_id', {})):,}</div>
  <div>Project PathID JSON: manual --pathID lookup only; not auto-expanded in UI</div>
  <div class='muted'>Warnings: {ext_warn}</div>
</div>
<div class='card'>
  <div class='title'>📋 Object counts</div>
  <table>{''.join(type_count_items)}</table>
</div>
<div class='card'>
  <div class='title'>🧾 Technical header</div>
  <div>Size: {idx.header.file_size:,} bytes</div>
  <div>SerializedFile version: {escape(str(getattr(idx.header, 'serialized_file_version', '') or '-'))}</div>
  <div>Metadata size: {escape(str(getattr(idx.header, 'metadata_size', '') or '-'))}</div>
  <div>Declared file size: {escape(str(getattr(idx.header, 'declared_file_size', '') or '-'))}</div>
  <div>Data offset: {escape(str(getattr(idx.header, 'data_offset', '') or '-'))}</div>
  <div>Header layout: {escape(str(getattr(idx.header, 'header_layout', '') or '-'))}</div>
  <div>Sidecar hint: {escape(str(getattr(idx.header, 'sidecar_hint', '') or '-'))}</div>
  <div>SHA256: {escape(str(idx.sha256))}</div>
  <div>Error: {errors}</div>
</div>
</body></html>
"""
            return html

        def show_bundle_info(self, dashboard_html: str | None = None):
            idx = self.bundle_index
            if not idx:
                return
            self.info.setHtml(dashboard_html if dashboard_html is not None else self._bundle_summary_html())
            self.preview_stack.setCurrentWidget(self.preview)
            if getattr(idx, "safe_open_state", "") == "header_only":
                self.preview.setText(
                    "Header-only safe mode\n\n"
                    "The Unity source header was readable, but full object decoding was blocked by the safe-open guard.\n\n"
                    f"Reason: {getattr(idx, 'safe_open_detail', '') or getattr(idx, 'error', '-') }"
                )
            else:
                self.preview.setText(
                    "Unity source summary dashboard\n\n"
                    "Select a 🖼 Texture for atlas/zoom tools, a 🧊 Mesh for 3D preview, "
                    "or click any blue asset link in the dashboard."
                )

        def _multi_preview_supported_type(self, rec) -> bool:
            return getattr(rec, "type_name", "") in (
                "GameObject", "Transform", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer", "Mesh"
            )

        def _selected_multi_preview_records(self) -> list:
            """Return selected renderable asset records for Ctrl/Shift multi preview."""
            out = []
            seen = set()
            try:
                current = self.tree.currentItem()
                if current is not None:
                    data = current.data(0, Qt.UserRole)
                    if data is not None and not isinstance(data, tuple) and self._multi_preview_supported_type(data):
                        key = (
                            str(getattr(data, "source_name", "") or ""),
                            str(getattr(data, "type_name", "") or ""),
                            getattr(data, "path_id", None),
                        )
                        seen.add(key)
                        out.append(data)
            except Exception:
                pass
            try:
                selected = self.tree.selectedItems()
            except Exception:
                selected = []
            for item in selected:
                try:
                    data = item.data(0, Qt.UserRole)
                except Exception:
                    continue
                if data is None or isinstance(data, tuple):
                    continue
                if not self._multi_preview_supported_type(data):
                    continue
                key = (
                    str(getattr(data, "source_name", "") or ""),
                    str(getattr(data, "type_name", "") or ""),
                    getattr(data, "path_id", None),
                )
                if key in seen:
                    continue
                seen.add(key)
                out.append(data)
            return out

        def preview_multi_selection_records(self, records: list, active_rec=None) -> bool:
            if not records or len(records) < 2:
                return False
            records = self.unique_records(records)[:4]
            for r in records:
                try:
                    self._hydrate_object_external_render_assets(r)
                except Exception:
                    pass

            assembly = self._ov_multi_selection_render_items(records)
            items = assembly.get("items", [])
            rendered_selection_count = int(assembly.get("rendered_selection_count", 0) or 0)
            selection_count = int(assembly.get("selection_count", len(records)) or len(records))
            skipped = list(assembly.get("skipped", []) or [])
            common_name = str(assembly.get("common_name", "Shared authored coordinates") or "Shared authored coordinates")

            self.preview_stack.setCurrentWidget(self.preview_3d)
            names = [str(getattr(r, "name", "")) for r in records]
            label = " + ".join(names[:2]) + (f" + {len(names)-2} more" if len(names) > 2 else "")

            if rendered_selection_count < 2 or not items:
                detail = "\n".join(skipped[:8]) or "The selected records did not resolve to two visible renderer instances."
                if hasattr(self.preview_3d, "show_multi_selection_unavailable"):
                    result_label = self.preview_3d.show_multi_selection_unavailable(detail)
                else:
                    self.preview_3d.message = f"Multi-select preview unavailable\nNeed at least two renderable selections.\n{detail}"
                    self.preview_3d.update()
                    result_label = "Multi-select preview: unavailable"
            elif hasattr(self.preview_3d, "load_object_group_records"):
                uv_channel = int(getattr(self.preview_3d, "uv_channel", 0) or 0)
                self.preview_3d.load_object_group_records(
                    label,
                    items,
                    self.bundle_index,
                    self.asset_graph,
                    uv_channel=uv_channel,
                    preview_mode="multi_select",
                    selection_count=selection_count,
                    context_label=f"Common parent: {common_name}",
                )
                result_label = f"Multi-select hierarchy preview: {rendered_selection_count} selection(s), {len(items)} render instance(s)"
            else:
                result_label = "Multi-select preview unavailable in this build"

            try:
                skipped_note = f"; {len(skipped)} selection issue(s)" if skipped else ""
                self.statusBar().showMessage(
                    f"3D preview: {result_label}; {common_name}{skipped_note}; O shows origins, V/I isolate instances",
                    7500,
                )
            except Exception:
                pass
            return True


        # ------------------------------------------------------------------
        # v2.2: Basic Transform AnimationClip preview.
        # ------------------------------------------------------------------
        def _animation_leave_preview(self) -> None:
            try:
                self.animation_timer.stop()
            except Exception:
                pass
            self.animation_clip_record = None
            self.animation_clip_data = None
            self.animation_tracks = []
            self.animation_root_transform = None
            self.animation_render_items = []
            self.animation_transform_by_key = {}
            self.animation_skinning_descriptors = []
            self.animation_constraint_descriptors = []
            self.animation_export_eligible = False
            self.animation_export_reason = ""
            self.animation_export_warnings = []
            self.animation_unsupported_property_bindings = 0
            self.animation_export_sample_rate = 0.0
            self.animation_export_context = {}
            self.animation_status_base_text = ""
            self.animation_target_instance_summary = ""
            self.animation_render_variant_info = {}
            self.animation_root_lock_keys = set()
            self.animation_in_place_baseline = {}
            self.animation_in_place_anchor_key = None
            self.animation_in_place_anchor_transform = None
            self.animation_in_place_anchor_name = ""
            self.animation_in_place_anchor_baseline_matrix = None
            # v2.3n: final rendered-geometry fallback anchor.  Some imported
            # controller rigs duplicate/flatten motion across several branches,
            # so no single Transform reliably represents what the user sees.
            # This anchor is measured after CPU skinning and final renderer
            # transforms, guaranteeing that In place holds the visible asset.
            self.animation_in_place_preview_center = None
            self.animation_in_place_preview_child_index = None
            self.animation_root_motion_summary = ""
            self.animation_streamed_meta = {}
            self.animation_binding_hint_paths = []
            self.animation_binding_hint_summary = ""
            self.animation_owner_gameobject = None
            self.animation_owner_resolution_summary = ""
            self.animation_owner_clip_key = None
            self.animation_duration = 0.0
            self.animation_current_time = 0.0
            self.animation_last_clock = 0.0
            # Continuous wall-clock position used during playback.  The live
            # pose is sampled on authored frame boundaries, while this value
            # preserves sub-frame elapsed time so 30 fps clips do not stall on
            # a faster UI timer.
            self.animation_playback_time = 0.0
            self.animation_pose_is_default = True
            try:
                self.animation_play_button.setText("Play")
                self.animation_export_glb_button.setVisible(False)
                self.animation_export_glb_button.setEnabled(False)
                self.animation_in_place_check.setChecked(False)
                self.animation_duration_limit_spin.blockSignals(True)
                self.animation_duration_limit_spin.setValue(0.001)
                self.animation_duration_limit_spin.blockSignals(False)
                self.animation_duration_limit_spin.setEnabled(False)
                self.animation_duration_full_button.setEnabled(False)
                self.animation_slider.setRange(0, 1)
                self.animation_slider.setValue(0)
                self.animation_controls.setVisible(False)
            except Exception:
                pass

        @staticmethod
        def _animation_float(value, default=0.0) -> float:
            try:
                return float(value)
            except Exception:
                return float(default)

        def _animation_streamed_storage(self, data):
            """Return the nested MuscleClip StreamedClip record, when present."""
            muscle = self._ov_get(data, "m_MuscleClip", "muscleClip", default=None)
            clip_ptr = self._ov_get(muscle, "m_Clip", "clip", default=None) if muscle is not None else None
            clip = self._ov_get(clip_ptr, "data", default=clip_ptr) if clip_ptr is not None else None
            if clip is None:
                return None
            return self._ov_get(clip, "m_StreamedClip", "streamedClip", default=None)

        def _animation_resolve_streamed_path(self, path_hash: int, clip_rec=None) -> str | None:
            hash_index = _anim_build_path_hash_index(self.bundle_index)
            candidates = list(hash_index.get(int(path_hash) & 0xFFFFFFFF, []) or [])
            if not candidates:
                return None
            clip_source = str(getattr(clip_rec, "source_name", "") or "") if clip_rec is not None else ""
            if clip_source:
                local = [row for row in candidates if str(row[2] or "") == clip_source]
                if local:
                    candidates = local
            # Prefer the shortest relative path.  It is normally the binding's
            # authored path rather than a longer absolute scene suffix.
            candidates.sort(key=lambda row: (len([p for p in str(row[0]).split("/") if p]), len(str(row[0])), str(row[0])))
            return str(candidates[0][0] or "").strip("/") or None

        def _animation_curve_tracks_from_clip(self, data, clip_rec=None, progress_callback=None) -> list[dict]:
            tracks: list[dict] = []
            self.animation_streamed_meta = {}
            self.animation_root_promotion_summary = ""
            self.animation_root_promotion_guard_summary = ""
            self.animation_controller_context_summary = ""
            specs = (
                ("position", "m_PositionCurves", 3),
                ("rotation", "m_RotationCurves", 4),
                ("euler", "m_EulerCurves", 3),
                ("scale", "m_ScaleCurves", 3),
            )
            for kind, field_name, component_count in specs:
                for curve_item in self._ov_as_list(self._ov_get(data, field_name, default=None)):
                    path = str(self._ov_get(curve_item, "path", "m_Path", default="") or "").strip("/")
                    curve = self._ov_get(curve_item, "curve", "m_Curve", default=None)
                    key_items = self._ov_as_list(self._ov_get(curve, "m_Curve", "keys", "keyframes", default=None))
                    keys: list[tuple[float, tuple[float, ...]]] = []
                    for key in key_items:
                        time_value = self._animation_float(self._ov_get(key, "time", "m_Time", default=None), float("nan"))
                        if math.isnan(time_value):
                            continue
                        raw_value = self._ov_get(key, "value", "m_Value", default=None)
                        if component_count == 4:
                            value = self._ov_quat_tuple(raw_value, (0.0, 0.0, 0.0, 1.0))
                        else:
                            value = self._ov_vec3_tuple(raw_value, (0.0, 0.0, 0.0))
                        keys.append((float(time_value), tuple(float(v) for v in value)))
                    keys.sort(key=lambda row: row[0])
                    if keys:
                        tracks.append({
                            "kind": kind,
                            "path": path,
                            "keys": keys,
                            "target_transform": None,
                            "storage": "ordinary",
                        })

            # v2.2f: generic Transform channels can be stored in the nested
            # MuscleClip StreamedClip instead of ordinary curve arrays.  Decode
            # those scalar channels and map them through the binding constant.
            streamed = self._animation_streamed_storage(data)
            binding_const = self._ov_get(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
            generic_bindings = self._ov_as_list(
                self._ov_get(binding_const, "genericBindings", "m_GenericBindings", default=None)
            ) if binding_const is not None else []

            # v2.2i: even when UBE cannot preview a binding property (for
            # example a SkinnedMeshRenderer blend-shape/property hash), its
            # hierarchy path is still valuable context.  Some clips expose only
            # one playable Transform track with a very generic target name, while
            # the unsupported renderer bindings uniquely identify the correct
            # character/object hierarchy.  Keep those paths as root-selection
            # hints so an unrelated duplicate such as MeshCollider_7381 does not
            # win merely because it was the first/shortest match.
            hint_paths: list[str] = []
            unsupported_property_bindings = 0
            for binding in generic_bindings:
                try:
                    path_hash = int(self._ov_get(binding, "path", "m_Path", default=0) or 0) & 0xFFFFFFFF
                except Exception:
                    path_hash = 0
                if path_hash:
                    hint = self._animation_resolve_streamed_path(path_hash, clip_rec)
                    hint = str(hint or "").strip("/")
                    if hint and hint != "<root>" and hint not in hint_paths:
                        hint_paths.append(hint)
                try:
                    type_value = self._ov_get(binding, "typeID", "typeId", "m_TypeID", "classID", "m_ClassID", default=0)
                    type_id = int(getattr(type_value, "value", type_value) or 0)
                except Exception:
                    type_id = 0
                try:
                    attribute = int(self._ov_get(binding, "attribute", "m_Attribute", default=0) or 0)
                except Exception:
                    attribute = 0
                if not (type_id == 4 and attribute in (1, 2, 3, 4)):
                    unsupported_property_bindings += 1

            self.animation_binding_hint_paths = hint_paths
            self.animation_unsupported_property_bindings = int(unsupported_property_bindings or 0)
            if unsupported_property_bindings:
                self.animation_binding_hint_summary = (
                    f"property bindings used for target context: {unsupported_property_bindings} "
                    f"(property playback unsupported)"
                )
            else:
                self.animation_binding_hint_summary = ""

            if streamed is not None and generic_bindings:
                streamed_tracks, meta = decode_streamed_transform_tracks(
                    streamed,
                    generic_bindings,
                    lambda path_hash: self._animation_resolve_streamed_path(path_hash, clip_rec),
                    progress_callback=progress_callback,
                )
                self.animation_streamed_meta = dict(meta or {})
                existing = {(str(track.get("kind")), str(track.get("path"))) for track in tracks}
                for track in streamed_tracks:
                    identity = (str(track.get("kind")), str(track.get("path")))
                    if identity in existing:
                        continue
                    tracks.append(track)
                    existing.add(identity)
            return tracks

        def _animation_ascend_transform(self, transform_rec, steps: int):
            current = transform_rec
            for _ in range(max(0, int(steps))):
                if current is None:
                    return None
                current = self._ov_parent_transform_record(current)
            return current

        @staticmethod
        def _animation_promotion_name_tokens(name: str) -> set[str]:
            """Return stable family tokens for render-owner promotion.

            Imported FBX hierarchies commonly pair names such as
            ``Hoggle_JNT_GRP`` and ``Hoggle_MESH_GRP``.  Course-wide animation
            aggregate roots instead contain unrelated branches such as
            ``H01_Gate``, ``H06_Teeth`` and ``Hole17_Birds``.  Removing generic
            rig/export words leaves the useful family evidence without relying
            on one game's exact naming convention.
            """
            text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(name or ""))
            words = re.findall(r"[a-zA-Z0-9]+", text.lower())
            ignored = {
                "anim", "animation", "armature", "bone", "bones", "child",
                "easy", "geo", "geometry", "grp", "group", "hard", "jnt",
                "joint", "lod", "mesh", "meshes", "object", "offset", "rig",
                "root", "skeleton", "transform", "visual", "visuals",
            }
            out = set()
            for word in words:
                word = re.sub(r"\d+$", "", word)
                if len(word) >= 3 and word not in ignored:
                    out.add(word)
            return out

        def _animation_immediate_child_below(self, ancestor_tr, descendant_tr):
            """Return the direct child branch of *ancestor_tr* containing descendant."""
            if ancestor_tr is None or descendant_tr is None:
                return None
            ancestor_key = self._ov_record_key(ancestor_tr)
            current = descendant_tr
            seen = set()
            while current is not None:
                key = self._ov_record_key(current)
                if key in seen:
                    return None
                seen.add(key)
                parent = self._ov_parent_transform_record(current)
                if parent is None:
                    return None
                if self._ov_record_key(parent) == ancestor_key:
                    return current
                current = parent
            return None

        def _animation_promotion_branch_is_near(self, reference_tr, candidate_tr) -> bool:
            """Test whether two imported sibling branches share an authored anchor.

            Skeleton and render branches are commonly siblings at the same local
            origin, even when their names are generic.  Scene-level animation
            modules are normally placed at very different local coordinates.
            """
            if reference_tr is None or candidate_tr is None:
                return False
            ref_data = self._ov_read(reference_tr)
            candidate_data = self._ov_read(candidate_tr)
            if ref_data is None or candidate_data is None:
                return False
            ref_pos = self._ov_vec3_tuple(
                self._ov_get(ref_data, "m_LocalPosition", "localPosition", default=None),
                (0.0, 0.0, 0.0),
            )
            candidate_pos = self._ov_vec3_tuple(
                self._ov_get(candidate_data, "m_LocalPosition", "localPosition", default=None),
                (0.0, 0.0, 0.0),
            )
            distance = math.sqrt(sum((float(ref_pos[i]) - float(candidate_pos[i])) ** 2 for i in range(3)))
            position_scale = max(
                1.0,
                math.sqrt(sum(float(ref_pos[i]) ** 2 for i in range(3))),
                math.sqrt(sum(float(candidate_pos[i]) ** 2 for i in range(3))),
            )
            if distance > max(0.075, position_scale * 0.0025):
                return False

            ref_scale = self._ov_vec3_tuple(
                self._ov_get(ref_data, "m_LocalScale", "localScale", default=None),
                (1.0, 1.0, 1.0),
            )
            candidate_scale = self._ov_vec3_tuple(
                self._ov_get(candidate_data, "m_LocalScale", "localScale", default=None),
                (1.0, 1.0, 1.0),
            )
            for i in range(3):
                denominator = max(1.0, abs(float(ref_scale[i])), abs(float(candidate_scale[i])))
                if abs(float(ref_scale[i]) - float(candidate_scale[i])) > denominator * 0.05:
                    return False
            return True

        def _animation_promote_root_to_renderable_owner(
            self,
            root_tr,
            *,
            max_parent_steps: int = 12,
            render_limit: int = 240,
            render_depth: int = 16,
        ):
            """Return a nearby, coherent render owner for a transform-only root.

            Promotion is useful when a skeleton/helper branch and its visible
            mesh are siblings beneath one imported object owner.  It is unsafe
            when the next ancestor is a course-wide aggregate containing several
            unrelated animation modules: selecting that ancestor makes one clip
            display the geometry from neighbouring clips.  v2.4b scopes promoted
            items to matching/colocated sibling branches and stops at ambiguous
            aggregate boundaries.
            """
            self.animation_root_promotion_guard_summary = ""
            origin_tr = root_tr
            current = root_tr
            seen = set()
            for parent_steps in range(max(0, int(max_parent_steps)) + 1):
                if current is None:
                    break
                key = self._ov_record_key(current)
                if key in seen:
                    break
                seen.add(key)

                go_rec = self._ov_gameobject_for_transform(current)
                if go_rec is not None:
                    items = self._ov_renderable_items_from_selection(
                        go_rec,
                        limit=max(1, int(render_limit)),
                        max_depth=max(1, int(render_depth)),
                        include_root=True,
                    )
                    if items and parent_steps == 0:
                        return current, items, parent_steps
                    if items:
                        origin_branch = self._animation_immediate_child_below(current, origin_tr)
                        origin_branch_key = self._ov_record_key(origin_branch) if origin_branch is not None else None
                        origin_go = self._ov_gameobject_for_transform(origin_branch) if origin_branch is not None else None
                        origin_name = str(getattr(origin_go, "name", "") or "")
                        origin_tokens = self._animation_promotion_name_tokens(origin_name)

                        branch_items: dict[tuple | None, list[dict]] = {}
                        branch_records: dict[tuple, object] = {}
                        for item in items:
                            item_tr = item.get("transform") if isinstance(item, dict) else None
                            branch = self._animation_immediate_child_below(current, item_tr) if item_tr is not None else None
                            branch_key = self._ov_record_key(branch) if branch is not None else None
                            branch_items.setdefault(branch_key, []).append(item)
                            if branch is not None:
                                branch_records[branch_key] = branch

                        selected_keys: set[tuple | None] = set()
                        # A renderer directly on the promoted owner is strong
                        # evidence that this is an object owner rather than a
                        # folder-like aggregate root.
                        if branch_items.get(None):
                            selected_keys.add(None)
                        if origin_branch_key in branch_items:
                            selected_keys.add(origin_branch_key)

                        for branch_key, branch in branch_records.items():
                            if branch_key == origin_branch_key:
                                continue
                            branch_go = self._ov_gameobject_for_transform(branch)
                            branch_name = str(getattr(branch_go, "name", "") or "")
                            branch_tokens = self._animation_promotion_name_tokens(branch_name)
                            same_family = bool(origin_tokens and branch_tokens and (origin_tokens & branch_tokens))
                            same_anchor = self._animation_promotion_branch_is_near(origin_branch, branch)
                            if same_family or same_anchor:
                                selected_keys.add(branch_key)

                        if selected_keys:
                            selected = [
                                item
                                for branch_key, rows in branch_items.items()
                                if branch_key in selected_keys
                                for item in rows
                            ]
                            if selected:
                                return current, selected, parent_steps

                        render_branch_keys = [branch_key for branch_key, rows in branch_items.items() if branch_key is not None and rows]
                        direct_children = self._ov_child_transform_records(current)
                        # A small owner with one visible sibling is the classic
                        # skeleton + mesh arrangement, even when the names and
                        # authored offsets are generic.
                        if len(render_branch_keys) == 1 and len(direct_children) <= 3:
                            return current, list(branch_items.get(render_branch_keys[0], [])), parent_steps

                        if len(render_branch_keys) > 1:
                            branch_names = []
                            for branch_key in render_branch_keys[:8]:
                                branch = branch_records.get(branch_key)
                                branch_go = self._ov_gameobject_for_transform(branch) if branch is not None else None
                                branch_names.append(str(getattr(branch_go, "name", "render branch") or "render branch"))
                            ancestor_name = str(getattr(go_rec, "name", "ancestor") or "ancestor")
                            origin_label = origin_name or str(getattr(self._ov_gameobject_for_transform(origin_tr), "name", "animation branch") or "animation branch")
                            listed = ", ".join(branch_names)
                            self.animation_root_promotion_guard_summary = (
                                f"{origin_label} has no renderers; promotion stopped at {ancestor_name} because it contains "
                                f"unrelated renderable sibling branches: {listed}"
                            )
                            return root_tr, [], 0

                current = self._ov_parent_transform_record(current)

            return root_tr, [], 0

        def _animation_transform_path_index_below(
            self,
            root_tr,
            *,
            max_nodes: int = 1200,
            max_depth: int = 96,
        ):
            """Return relative Transform paths beneath one candidate Animator root.

            Unity animation binding paths are authored relative to the Animator
            GameObject. Building this small, bounded local index avoids choosing
            unrelated duplicate names from another prefab/sharedAssets hierarchy.
            """
            if root_tr is None:
                return {}
            out: dict[str, list] = {"": [root_tr], "<root>": [root_tr]}
            stack = [(root_tr, "", 0)]
            seen = set()
            while stack and len(seen) < max(1, int(max_nodes)):
                tr_rec, rel_path, depth = stack.pop()
                if tr_rec is None or depth > max(1, int(max_depth)):
                    continue
                key = self._ov_record_key(tr_rec)
                if key in seen:
                    continue
                seen.add(key)
                for child_tr in self._ov_child_transform_records(tr_rec):
                    child_go = self._ov_gameobject_for_transform(child_tr)
                    child_name = str(getattr(child_go, "name", getattr(child_tr, "name", "")) or "").strip()
                    if not child_name:
                        continue
                    child_path = f"{rel_path}/{child_name}".strip("/")
                    out.setdefault(child_path, []).append(child_tr)
                    stack.append((child_tr, child_path, depth + 1))
            return out

        @staticmethod
        def _animation_local_path_matches(path_index: dict, authored_path: str):
            path = str(authored_path or "").strip("/")
            if path in ("", "<root>"):
                return list(path_index.get("", []) or path_index.get("<root>", []) or [])
            exact = list(path_index.get(path, []) or [])
            if exact:
                return exact
            suffix = "/" + path
            matches = []
            for candidate_path, rows in path_index.items():
                if candidate_path == path or candidate_path.endswith(suffix):
                    matches.extend(rows or [])
            return matches

        def _animation_legacy_preview_context(self, clip_rec, tracks: list[dict]):
            """Resolve a Legacy clip through Animation component ownership.

            Legacy AnimationClip paths are authored relative to the GameObject
            carrying the Animation component.  Repeated child names such as
            ``flagRaiser`` can otherwise resolve to every colour/prefab variant
            in the bundle.  The explicit Animation -> clip reference is the
            authoritative owner and keeps preview selection inside one object.
            """
            if clip_rec is None:
                return None, {}, [], ""
            clip_key = self._flow_record_key(clip_rec)

            playable_paths = []
            for track in tracks or []:
                path = str(track.get("path") or "").strip("/")
                if path not in playable_paths:
                    playable_paths.append(path)
            if not playable_paths:
                return None, {}, [], ""

            hint_paths = []
            for path in list(getattr(self, "animation_binding_hint_paths", []) or []):
                path = str(path or "").strip("/")
                if path and path not in playable_paths and path not in hint_paths:
                    hint_paths.append(path)

            clip_name = str(getattr(clip_rec, "name", "") or "").lower()
            clip_source = str(getattr(clip_rec, "source_name", "") or "")
            ranked = []
            for animation in self._flow_all_records("Animation"):
                data = self._ov_read(animation)
                if data is None:
                    continue
                refs = [self._ov_get(data, "m_Animation", "animation", default=None)]
                refs.extend(self._ov_as_list(self._ov_get(data, "m_Animations", "animations", default=None)))
                owns_clip = False
                for pptr in refs:
                    candidate = _resolve_record(self.bundle_index, pptr)
                    if candidate is not None and self._flow_record_key(candidate) == clip_key:
                        owns_clip = True
                        break
                if not owns_clip:
                    continue

                owner_go = self._ov_owning_gameobject(animation)
                root_tr = self._ov_transform_for_gameobject(owner_go) if owner_go is not None else None
                if root_tr is None:
                    continue
                path_index = self._animation_transform_path_index_below(root_tr)
                targets = {}
                playable_hits = 0
                for path in playable_paths:
                    matches = self._animation_local_path_matches(path_index, path)
                    if matches:
                        targets[path] = matches[0]
                        playable_hits += 1
                if playable_hits <= 0:
                    continue
                hint_hits = sum(1 for path in hint_paths if self._animation_local_path_matches(path_index, path))
                items = self._ov_renderable_items_from_selection(
                    owner_go,
                    limit=320,
                    max_depth=32,
                    include_root=True,
                )
                if not items:
                    continue

                owner_name = str(getattr(owner_go, "name", "") or "")
                owner_low = owner_name.lower()
                name_affinity = 0
                if owner_low and owner_low in clip_name:
                    name_affinity = len(owner_low)
                elif clip_name and any(token and token in owner_low for token in clip_name.replace("_", " ").split()[:4]):
                    name_affinity = 1
                source_local = 1 if str(getattr(animation, "source_name", "") or "") == clip_source else 0
                score = (playable_hits, hint_hits, name_affinity, source_local, -len(items))
                ranked.append((score, animation, owner_go, root_tr, targets, items))

            if not ranked:
                return None, {}, [], ""
            ranked.sort(key=lambda row: row[0], reverse=True)
            _score, animation, owner_go, root_tr, targets, items = ranked[0]
            owner_name = str(getattr(owner_go, "name", "Legacy Animation owner") or "Legacy Animation owner")
            summary = f"preview resolved through legacy Animation owner {owner_name}"
            return root_tr, targets, items, summary

        @staticmethod
        def _animation_normalized_owner_name(value: str) -> str:
            """Return a conservative alphanumeric key for clip/owner affinity."""
            return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())

        def _animation_named_owner_preview_context(self, clip_rec, tracks: list[dict]):
            """Resolve repeated Legacy paths through an owner named by the clip.

            Some exported WAM Legacy clips are not directly referenced by the
            serialized ``Animation`` component copy available in the bundle.
            Their names still carry the prefab owner, for example::

                flagStopper_pink_FlagRaise_WAM_Legacy

            A bundle-global ``flagRaiser`` lookup then incorrectly gathers all
            colour variants.  This bounded fallback considers only GameObjects
            whose normalized name is a *prefix* of the clip name, requires the
            playable paths below that owner, and prefers the longest owner name
            and smallest renderable subtree.
            """
            if clip_rec is None:
                return None, {}, [], ""

            clip_name = str(getattr(clip_rec, "name", "") or "")
            clip_key = self._animation_normalized_owner_name(clip_name)
            if not clip_key:
                return None, {}, [], ""

            playable_paths: list[str] = []
            for track in tracks or []:
                path = str(track.get("path") or "").strip("/")
                if path not in playable_paths:
                    playable_paths.append(path)
            if not playable_paths:
                return None, {}, [], ""

            hint_paths: list[str] = []
            for path in list(getattr(self, "animation_binding_hint_paths", []) or []):
                path = str(path or "").strip("/")
                if path and path not in playable_paths and path not in hint_paths:
                    hint_paths.append(path)

            clip_source = str(getattr(clip_rec, "source_name", "") or "")
            ranked = []
            for owner_go in self._flow_all_records("GameObject"):
                owner_name = str(getattr(owner_go, "name", "") or "").strip()
                owner_key = self._animation_normalized_owner_name(owner_name)
                # Very short names (for example "Char") are too ambiguous to
                # use as a naming authority.
                if len(owner_key) < 5 or not clip_key.startswith(owner_key):
                    continue

                root_tr = self._ov_transform_for_gameobject(owner_go)
                if root_tr is None:
                    continue
                path_index = self._animation_transform_path_index_below(root_tr)
                targets = {}
                playable_hits = 0
                for path in playable_paths:
                    matches = self._animation_local_path_matches(path_index, path)
                    if matches:
                        targets[path] = matches[0]
                        playable_hits += 1
                # The named owner is authoritative only when it contains every
                # playable Transform path.
                if playable_hits != len(playable_paths):
                    continue

                items = self._ov_renderable_items_from_selection(
                    owner_go,
                    limit=160,
                    max_depth=24,
                    include_root=True,
                )
                if not items:
                    continue

                hint_hits = sum(1 for path in hint_paths if self._animation_local_path_matches(path_index, path))
                same_source = 1 if str(getattr(owner_go, "source_name", "") or "") == clip_source else 0
                # Longest matching owner wins; smaller subtrees beat broad scene
                # roots when names are otherwise equally persuasive.
                score = (len(owner_key), hint_hits, same_source, -len(items))
                ranked.append((score, owner_go, root_tr, targets, items))

            if not ranked:
                return None, {}, [], ""
            ranked.sort(key=lambda row: row[0], reverse=True)
            _score, owner_go, root_tr, targets, items = ranked[0]
            owner_name = str(getattr(owner_go, "name", "named Legacy owner") or "named Legacy owner")
            summary = f"preview resolved through clip-named owner {owner_name}"
            return root_tr, targets, items, summary

        def _animation_variant_named_owner_preview_context(self, clip_rec, tracks: list[dict]):
            """Resolve repeated Legacy targets through a numbered clip-owner branch.

            Some WAM clips identify a particular duplicated prefab instance in
            the clip name, for example::

                CupSheepAnim (4)_sheepMove1_WAM_Legacy

            while their playable paths remain generic (``CupSheep`` and
            ``CupSheep/Flag``).  A bundle-global path lookup can therefore climb
            to a broad course owner and assemble every sheep/flag variant.

            This target-first fallback examines the ancestor chain of each
            matching playable target, scores ancestors whose normalized name is
            a prefix of the clip name, and strongly prefers the same parenthesized
            instance number.  All playable paths must resolve beneath one owner.
            """
            if clip_rec is None:
                return None, {}, [], ""

            clip_name = str(getattr(clip_rec, "name", "") or "")
            clip_key = self._animation_normalized_owner_name(clip_name)
            if not clip_key:
                return None, {}, [], ""

            variant_match = re.search(r"\((\d+)\)", clip_name)
            variant_number = variant_match.group(1) if variant_match else ""
            playable_paths: list[str] = []
            for track in tracks or []:
                path = str(track.get("path") or "").strip("/")
                if path and path not in playable_paths:
                    playable_paths.append(path)
            if not playable_paths:
                return None, {}, [], ""

            path_index = _anim_build_path_record_index(self.bundle_index)
            clip_source = str(getattr(clip_rec, "source_name", "") or "")
            grouped: dict[tuple, dict] = {}

            for path in playable_paths:
                candidates = list(path_index.get(path, []) or [])
                for candidate in candidates[:160]:
                    go_rec = candidate if getattr(candidate, "type_name", "") == "GameObject" else self._ov_owning_gameobject(candidate)
                    target_tr = self._ov_transform_for_gameobject(go_rec) if go_rec is not None else None
                    if target_tr is None:
                        continue

                    current = target_tr
                    seen = set()
                    for depth in range(20):
                        if current is None:
                            break
                        current_key = self._ov_record_key(current)
                        if current_key in seen:
                            break
                        seen.add(current_key)
                        owner_go = self._ov_gameobject_for_transform(current)
                        owner_name = str(getattr(owner_go, "name", "") or "").strip() if owner_go is not None else ""
                        owner_key = self._animation_normalized_owner_name(owner_name)
                        if owner_key:
                            prefix_affinity = len(owner_key) if clip_key.startswith(owner_key) else 0
                            owner_variant = ""
                            owner_variant_match = re.search(r"\((\d+)\)", owner_name)
                            if owner_variant_match:
                                owner_variant = owner_variant_match.group(1)
                            same_variant = 1 if variant_number and owner_variant == variant_number else 0

                            # Ignore generic target names unless their ancestor
                            # carries the numbered clip identity.  This keeps a
                            # plain CupSheep node from winning over CupSheepAnim (4).
                            if prefix_affinity > 0 or same_variant:
                                entry = grouped.setdefault(current_key, {
                                    "root": current,
                                    "owner": owner_go,
                                    "paths": {},
                                    "prefix_affinity": prefix_affinity,
                                    "same_variant": same_variant,
                                    "depth": depth,
                                })
                                entry["paths"].setdefault(path, []).append(target_tr)
                                entry["prefix_affinity"] = max(entry["prefix_affinity"], prefix_affinity)
                                entry["same_variant"] = max(entry["same_variant"], same_variant)
                                entry["depth"] = min(entry["depth"], depth)
                        current = self._ov_parent_transform_record(current)

            ranked = []
            for entry in grouped.values():
                if any(path not in entry["paths"] for path in playable_paths):
                    continue
                owner_go = entry["owner"]
                if owner_go is None:
                    continue
                items = self._ov_renderable_items_from_selection(
                    owner_go,
                    limit=160,
                    max_depth=24,
                    include_root=True,
                )
                if not items:
                    continue
                same_source = 1 if str(getattr(owner_go, "source_name", "") or "") == clip_source else 0
                score = (
                    entry["same_variant"],
                    entry["prefix_affinity"],
                    same_source,
                    -entry["depth"],
                    -len(items),
                )
                ranked.append((score, entry, items))

            if not ranked:
                return None, {}, [], ""
            ranked.sort(key=lambda row: row[0], reverse=True)
            _score, entry, items = ranked[0]
            targets = {path: entry["paths"][path][0] for path in playable_paths}
            owner_name = str(getattr(entry["owner"], "name", "numbered Legacy owner") or "numbered Legacy owner")
            summary = f"preview resolved through numbered clip owner {owner_name}"
            return entry["root"], targets, items, summary

        def _animation_controller_preview_context(self, clip_rec, tracks: list[dict]):
            """Resolve a clip through AnimatorController -> Animator ownership.

            Some clips mix one playable Transform channel with renderer property
            bindings. Bundle-global path hashes can then pick an unrelated prefab.
            Controller and Animator wiring identifies the actual character owner.
            """
            if clip_rec is None:
                return None, {}, [], ""
            clip_key = self._flow_record_key(clip_rec)

            controllers = []
            for controller in self._flow_all_records("AnimatorController", "AnimatorOverrideController"):
                data = self._ov_read(controller)
                if data is None:
                    continue
                try:
                    refs = _animctrl_unique_clip_refs(data, self.bundle_index)
                except Exception:
                    refs = []
                if any(candidate is not None and self._flow_record_key(candidate) == clip_key for _pptr, candidate in refs):
                    controllers.append(controller)
            if not controllers:
                return None, {}, [], ""

            controller_keys = {self._flow_record_key(controller) for controller in controllers}
            playable_paths = []
            for track in tracks or []:
                path = str(track.get("path") or "").strip("/")
                if path not in playable_paths:
                    playable_paths.append(path)
            hint_paths = []
            for path in list(getattr(self, "animation_binding_hint_paths", []) or []):
                path = str(path or "").strip("/")
                if path and path not in playable_paths and path not in hint_paths:
                    hint_paths.append(path)

            ranked = []
            for animator in self._flow_all_records("Animator"):
                data = self._ov_read(animator)
                if data is None:
                    continue
                controller = _resolve_record(
                    self.bundle_index,
                    self._ov_get(data, "m_Controller", "controller", default=None),
                )
                if controller is None or self._flow_record_key(controller) not in controller_keys:
                    continue
                owner_go = self._ov_owning_gameobject(animator)
                root_tr = self._ov_transform_for_gameobject(owner_go) if owner_go is not None else None
                if root_tr is None:
                    continue
                path_index = self._animation_transform_path_index_below(root_tr)
                targets = {}
                playable_hits = 0
                for path in playable_paths:
                    matches = self._animation_local_path_matches(path_index, path)
                    if matches:
                        targets[path] = matches[0]
                        playable_hits += 1
                hint_hits = sum(1 for path in hint_paths if self._animation_local_path_matches(path_index, path))
                if playable_hits <= 0:
                    continue
                items = self._ov_renderable_items_from_selection(
                    owner_go,
                    limit=320,
                    max_depth=32,
                    include_root=True,
                )
                if not items:
                    continue
                skinned_hits = 0
                for item in items:
                    item_go = self._ov_owning_gameobject(item.get("record"))
                    if item_go is None:
                        continue
                    if any(comp.type_name == "SkinnedMeshRenderer" for comp in self._ov_component_records_for_gameobject(item_go)):
                        skinned_hits += 1
                source_local = 1 if str(getattr(animator, "source_name", "") or "") == str(getattr(clip_rec, "source_name", "") or "") else 0
                score = (playable_hits, hint_hits, skinned_hits, source_local, -len(items))
                ranked.append((score, animator, owner_go, root_tr, targets, items, controller))

            if not ranked:
                return None, {}, [], ""
            ranked.sort(key=lambda row: row[0], reverse=True)
            _score, animator, owner_go, root_tr, targets, items, controller = ranked[0]
            owner_name = str(getattr(owner_go, "name", "Animator owner") or "Animator owner")
            controller_name = str(getattr(controller, "name", "controller") or "controller")
            summary = f"preview resolved through Animator owner {owner_name} ({controller_name})"
            return root_tr, targets, items, summary

        def _animation_resolve_root_and_targets(self, tracks: list[dict], clip_rec, *, use_binding_hints: bool = True):
            """Resolve curve paths to one coherent animation hierarchy.

            Playable Transform tracks determine what UBE can animate.  Generic
            binding paths for unsupported properties are also used as context
            when choosing between duplicate hierarchy instances, but they never
            become animation tracks themselves.

            ``use_binding_hints=False`` preserves the v2.2h playable-track-only
            fallback. It is used only when richer context identifies a valid
            animation family but cannot locate its renderable owner.
            """
            path_index = _anim_build_path_record_index(self.bundle_index)
            playable_paths = []
            for track in tracks:
                path = str(track.get("path") or "")
                if path and path not in playable_paths:
                    playable_paths.append(path)

            hint_paths = []
            if use_binding_hints:
                for path in list(getattr(self, "animation_binding_hint_paths", []) or []):
                    path = str(path or "").strip("/")
                    if path and path not in playable_paths and path not in hint_paths:
                        hint_paths.append(path)

            all_paths = playable_paths + hint_paths
            roots: dict[tuple, dict] = {}
            unresolved: list[str] = []
            playable_set = set(playable_paths)
            for path in all_paths:
                parts = [part for part in path.split("/") if part]
                candidates = list(path_index.get(path, []) or [])
                if not candidates:
                    if path in playable_set:
                        unresolved.append(path)
                    continue
                found_for_path = False
                for candidate in candidates[:80]:
                    go_rec = candidate if getattr(candidate, "type_name", "") == "GameObject" else self._ov_owning_gameobject(candidate)
                    tr_rec = self._ov_transform_for_gameobject(go_rec) if go_rec is not None else None
                    if tr_rec is None:
                        continue
                    root_tr = self._animation_ascend_transform(tr_rec, len(parts))
                    if root_tr is None:
                        continue
                    root_key = self._ov_record_key(root_tr)
                    entry = roots.setdefault(root_key, {"root": root_tr, "paths": {}})
                    entry["paths"].setdefault(path, []).append(tr_rec)
                    found_for_path = True
                if not found_for_path and path in playable_set and path not in unresolved:
                    unresolved.append(path)

            if not roots:
                return None, {}, unresolved

            clip_source = str(getattr(clip_rec, "source_name", "") or "")

            # Prefer live hierarchy instances referenced by constraints when a
            # scene also contains an inert prefab/sharedAssets duplicate.
            constraint_source_keys = set()
            examined = 0
            for _constraint_kind, candidates in self._animation_constraint_records().items():
                for constraint_rec in candidates:
                    if examined >= 4096:
                        break
                    examined += 1
                    cdata = self._ov_read(constraint_rec)
                    if cdata is None:
                        continue
                    source_rows = self._ov_as_list(self._ov_get(cdata, "m_Sources", "sources", default=None))
                    for source_row in source_rows[:32]:
                        source_pptr = self._ov_get(
                            source_row,
                            "sourceTransform", "m_SourceTransform", "transform", "m_Transform", "source", "m_Source",
                            default=None,
                        )
                        source_rec = self._ov_resolve(source_pptr)
                        if source_rec is not None and getattr(source_rec, "type_name", "") in ("Transform", "RectTransform"):
                            constraint_source_keys.add(self._ov_record_key(source_rec))
                    direct_pptr = self._ov_get(cdata, "m_Source", "source", "m_SourceTransform", default=None)
                    direct_rec = self._ov_resolve(direct_pptr)
                    if direct_rec is not None and getattr(direct_rec, "type_name", "") in ("Transform", "RectTransform"):
                        constraint_source_keys.add(self._ov_record_key(direct_rec))
                if examined >= 4096:
                    break

            ranked = []
            for key, entry in roots.items():
                root = entry["root"]
                playable_matched = sum(1 for path in playable_paths if path in entry["paths"])
                total_matched = len(entry["paths"])
                local = 1 if str(getattr(root, "source_name", "") or "") == clip_source else 0
                target_keys = {
                    self._ov_record_key(target)
                    for path_candidates in entry["paths"].values()
                    for target in path_candidates
                    if target is not None
                }
                constraint_hits = len(target_keys & constraint_source_keys)
                # Playable coverage is mandatory.  Unsupported binding paths are
                # only a tie-break/context signal after that.
                ranked.append((playable_matched, total_matched, constraint_hits, local, str(key), entry))
            ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]), reverse=True)
            chosen = ranked[0][-1]
            if ranked[0][0] <= 0:
                return None, {}, unresolved

            targets = {}
            for path in playable_paths:
                path_candidates = list(chosen["paths"].get(path, []) or [])
                if not path_candidates:
                    continue
                constrained = [candidate for candidate in path_candidates if self._ov_record_key(candidate) in constraint_source_keys]
                targets[path] = constrained[0] if constrained else path_candidates[0]
            for path in playable_paths:
                if path not in targets and path not in unresolved:
                    unresolved.append(path)
            return chosen["root"], targets, unresolved

        @staticmethod
        def _animation_quat_mul(a, b):
            ax, ay, az, aw = a
            bx, by, bz, bw = b
            return (
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            )

        def _animation_euler_quaternion(self, value):
            """Convert degrees to a practical Unity-style Z-X-Y Euler quaternion."""
            x, y, z = (math.radians(float(v)) * 0.5 for v in value)
            qx = (math.sin(x), 0.0, 0.0, math.cos(x))
            qy = (0.0, math.sin(y), 0.0, math.cos(y))
            qz = (0.0, 0.0, math.sin(z), math.cos(z))
            # Unity's Euler display order is commonly represented as Z, X, Y.
            return self._animation_quat_mul(qy, self._animation_quat_mul(qx, qz))

        @staticmethod
        def _animation_quat_slerp(a, b, amount: float):
            amount = max(0.0, min(1.0, float(amount)))
            dot = sum(float(a[i]) * float(b[i]) for i in range(4))
            if dot < 0.0:
                b = tuple(-float(v) for v in b)
                dot = -dot
            if dot > 0.9995:
                out = tuple(float(a[i]) + amount * (float(b[i]) - float(a[i])) for i in range(4))
                length = math.sqrt(sum(v * v for v in out))
                return tuple(v / length for v in out) if length > 1e-10 else (0.0, 0.0, 0.0, 1.0)
            dot = max(-1.0, min(1.0, dot))
            theta = math.acos(dot)
            sin_theta = math.sin(theta)
            if abs(sin_theta) < 1e-10:
                return tuple(float(v) for v in a)
            wa = math.sin((1.0 - amount) * theta) / sin_theta
            wb = math.sin(amount * theta) / sin_theta
            return tuple(wa * float(a[i]) + wb * float(b[i]) for i in range(4))

        def _animation_sample_track(self, track: dict, time_seconds: float):
            keys = track.get("keys") or []
            if not keys:
                return None
            if len(keys) == 1 or time_seconds <= keys[0][0]:
                return keys[0][1]
            if time_seconds >= keys[-1][0]:
                return keys[-1][1]
            low = 0
            high = len(keys) - 1
            while low + 1 < high:
                mid = (low + high) // 2
                if keys[mid][0] <= time_seconds:
                    low = mid
                else:
                    high = mid
            t0, v0 = keys[low]
            t1, v1 = keys[high]
            amount = 0.0 if abs(t1 - t0) < 1e-12 else (time_seconds - t0) / (t1 - t0)
            if track.get("kind") == "rotation":
                return self._animation_quat_slerp(v0, v1, amount)
            return tuple(float(v0[i]) + amount * (float(v1[i]) - float(v0[i])) for i in range(len(v0)))

        def _animation_base_trs(self, transform_rec):
            data = self._ov_read(transform_rec)
            if data is None:
                return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)
            pos = self._ov_vec3_tuple(self._ov_get(data, "m_LocalPosition", "localPosition", default=None), (0.0, 0.0, 0.0))
            rot = self._ov_quat_tuple(self._ov_get(data, "m_LocalRotation", "localRotation", default=None), (0.0, 0.0, 0.0, 1.0))
            scale = self._ov_vec3_tuple(self._ov_get(data, "m_LocalScale", "localScale", default=None), (1.0, 1.0, 1.0))
            return pos, rot, scale

        def _animation_transform_depth_from_root(self, transform_rec):
            root = self.animation_root_transform
            if transform_rec is None or root is None:
                return None
            root_key = self._ov_record_key(root)
            current = transform_rec
            depth = 0
            seen = set()
            while current is not None and depth <= 256:
                key = self._ov_record_key(current)
                if key == root_key:
                    return depth
                if key in seen:
                    break
                seen.add(key)
                current = self._ov_parent_transform_record(current)
                depth += 1
            return None

        def _animation_is_descendant_or_self(self, transform_rec, ancestor_rec) -> bool:
            if transform_rec is None or ancestor_rec is None:
                return False
            ancestor_key = self._ov_record_key(ancestor_rec)
            current = transform_rec
            seen = set()
            for _ in range(257):
                if current is None:
                    return False
                key = self._ov_record_key(current)
                if key == ancestor_key:
                    return True
                if key in seen:
                    return False
                seen.add(key)
                current = self._ov_parent_transform_record(current)
            return False

        def _animation_configure_root_motion(self, tracks: list[dict]) -> None:
            """Offer a manual in-place preview for top animated branches.

            v2.2b/v2.2c automatically enabled this option when position or
            scale ranges looked suspicious.  That broke valid rigid animations
            such as RingLoc, where position/scale are the animation rather than
            unwanted scene/root motion.  v2.2d therefore never forces the mode.

            Position/scale tracks identify the topmost world-motion controller
            in each independent hierarchy branch.  When the user enables In
            place, hold the controller's complete authored first-frame TRS
            (position, rotation and scale).  Root rotation must also be held:
            rotating an offset child beneath a travel controller otherwise
            swings the visible character through a huge world-space arc even
            though its position channel is frozen.  Ordinary descendant/bone
            rotations continue normally.
            """
            candidates = {}
            for track in tracks or []:
                kind = str(track.get("kind"))
                if kind not in ("position", "scale"):
                    continue
                target = track.get("target_transform")
                depth = self._animation_transform_depth_from_root(target)
                if target is None or depth is None:
                    continue
                key = self._ov_record_key(target)
                row = candidates.setdefault(key, {
                    "target": target,
                    "depth": int(depth),
                    "kinds": set(),
                    "tracks": [],
                })
                row["kinds"].add(kind)
                row["tracks"].append(track)

            self.animation_root_lock_keys = set()
            self.animation_in_place_baseline = {}
            self.animation_in_place_anchor_key = None
            self.animation_in_place_anchor_transform = None
            self.animation_in_place_anchor_name = ""
            self.animation_in_place_anchor_baseline_matrix = None
            # v2.3n: final rendered-geometry fallback anchor.  Some imported
            # controller rigs duplicate/flatten motion across several branches,
            # so no single Transform reliably represents what the user sees.
            # This anchor is measured after CPU skinning and final renderer
            # transforms, guaranteeing that In place holds the visible asset.
            self.animation_in_place_preview_center = None
            self.animation_in_place_preview_child_index = None
            self.animation_root_motion_summary = ""
            try:
                self.animation_in_place_check.blockSignals(True)
                self.animation_in_place_check.setChecked(False)
            finally:
                self.animation_in_place_check.blockSignals(False)

            if not candidates:
                self.animation_in_place_check.setEnabled(False)
                return

            candidate_keys = set(candidates)
            top_keys = set()
            for key, row in candidates.items():
                current = self._ov_parent_transform_record(row["target"])
                seen = set()
                has_candidate_ancestor = False
                for _ in range(257):
                    if current is None:
                        break
                    parent_key = self._ov_record_key(current)
                    if parent_key in seen:
                        break
                    seen.add(parent_key)
                    if parent_key in candidate_keys:
                        has_candidate_ancestor = True
                        break
                    current = self._ov_parent_transform_record(current)
                if not has_candidate_ancestor:
                    top_keys.add(key)

            # Defensive fallback for malformed/cyclic hierarchies.
            if not top_keys:
                min_depth = min(row["depth"] for row in candidates.values())
                top_keys = {key for key, row in candidates.items() if row["depth"] == min_depth}

            self.animation_root_lock_keys = top_keys

            # v2.3h/v2.3j: hold in-place roots at their *authored first-frame*
            # complete TRS, not at the serialized/rest pose.  Position/scale
            # tracks above identify a world-motion controller; once identified,
            # its rotation/euler channel must also be held.  Otherwise a changing
            # parent heading rotates any offset child around the controller and
            # the visible creature still travels a huge distance despite a
            # frozen position channel.  Sampling t=0 keeps preview and GLB export
            # identical while leaving all descendant skeletal motion untouched.
            baseline = {}
            for track in tracks or []:
                target = track.get("target_transform")
                if target is None:
                    continue
                target_key = self._ov_record_key(target)
                kind = str(track.get("kind") or "")
                if target_key not in top_keys or kind not in ("position", "rotation", "euler", "scale"):
                    continue
                sampled = self._animation_sample_track(track, 0.0)
                if sampled is not None:
                    baseline.setdefault(target_key, {})[kind] = tuple(float(v) for v in sampled)
            self.animation_in_place_baseline = baseline

            names = []
            all_kinds = set()
            suspicious = False
            for key in sorted(top_keys, key=lambda value: candidates[value]["depth"]):
                row = candidates[key]
                target = row["target"]
                # Report the complete set of channels that In place will hold,
                # including root rotation/euler discovered after the motion-root
                # candidate was selected from its position/scale tracks.
                all_kinds.update((baseline.get(key) or {}).keys())
                go = self._ov_gameobject_for_transform(target)
                name = str(getattr(go, "name", getattr(target, "name", "root")) or "root")
                if name not in names:
                    names.append(name)
                for track in row["tracks"]:
                    values = [tuple(float(v) for v in value) for _time, value in (track.get("keys") or [])]
                    if not values:
                        continue
                    if track.get("kind") == "position":
                        base = self._animation_base_trs(target)[0]
                        distances = [math.sqrt(sum((value[i] - base[i]) ** 2 for i in range(3))) for value in values]
                        span = max(
                            (math.sqrt(sum((value[i] - values[0][i]) ** 2 for i in range(3))) for value in values),
                            default=0.0,
                        )
                        if max(distances, default=0.0) > 5.0 or span > 2.0:
                            suspicious = True
                    elif track.get("kind") == "scale":
                        flat = [component for value in values for component in value]
                        if flat and (min(flat) < 0.75 or max(flat) > 1.25):
                            suspicious = True

            kind_order = {"position": 0, "rotation": 1, "euler": 1, "scale": 2}
            kind_text = "/".join(sorted(all_kinds, key=lambda value: (kind_order.get(value, 99), value)))
            hint = "root motion detected; " if suspicious else ""
            self.animation_root_motion_summary = (
                f"{hint}in-place available: {', '.join(names[:4])} ({kind_text})"
            )
            self.animation_in_place_check.setEnabled(True)

        def _animation_configure_in_place_world_anchor(self) -> None:
            """Choose the visible character branch used for true In-place motion.

            Freezing a few authored local channels is not sufficient for rigs
            where hidden parents, sibling controls or nested non-uniform scale
            combine into a large effective world-space movement.  Instead, pick
            the detected motion root that actually owns the visible renderers,
            remember its fully evaluated frame-zero matrix, and later cancel the
            complete world-space delta of that branch.
            """
            self.animation_in_place_anchor_key = None
            self.animation_in_place_anchor_transform = None
            self.animation_in_place_anchor_name = ""
            self.animation_in_place_anchor_baseline_matrix = None

            if not self.animation_root_lock_keys:
                return

            references = []
            for desc in self.animation_skinning_descriptors or []:
                for field in ("root_bone", "renderer_transform"):
                    transform = desc.get(field) if isinstance(desc, dict) else None
                    if transform is not None and transform not in references:
                        references.append(transform)
            for item in self.animation_render_items or []:
                transform = item.get("transform") if isinstance(item, dict) else None
                if transform is not None and transform not in references:
                    references.append(transform)

            candidates = []
            for key in self.animation_root_lock_keys:
                transform = self.animation_transform_by_key.get(key)
                if transform is None:
                    continue
                coverage = sum(
                    1 for ref in references
                    if self._animation_is_descendant_or_self(ref, transform)
                )
                depth = self._animation_transform_depth_from_root(transform)
                candidates.append((int(coverage), int(depth or 0), str(key), transform))

            # Prefer the detected travel root containing the visible render
            # branch.  A separate Maya/controller branch such as RayMover_CTRL
            # can have many animated channels but zero render descendants; it
            # must not become the visual world anchor.
            candidates.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
            anchor = candidates[0][3] if candidates and candidates[0][0] > 0 else None

            if anchor is None:
                for desc in self.animation_skinning_descriptors or []:
                    anchor = desc.get("root_bone") or desc.get("renderer_transform")
                    if anchor is not None:
                        break
            if anchor is None and references:
                anchor = references[0]
            if anchor is None:
                return

            key = self._ov_record_key(anchor)
            baseline_map = self._animation_uncorrected_matrix_map_for_time(0.0)
            baseline = baseline_map.get(key)
            if baseline is None:
                return

            self.animation_in_place_anchor_key = key
            self.animation_in_place_anchor_transform = anchor
            self.animation_in_place_anchor_baseline_matrix = baseline
            go = self._ov_gameobject_for_transform(anchor)
            self.animation_in_place_anchor_name = str(
                getattr(go, "name", getattr(anchor, "name", "render branch")) or "render branch"
            )
            if self.animation_root_motion_summary:
                self.animation_root_motion_summary += f"; world anchor: {self.animation_in_place_anchor_name}"

        def _animation_in_place_correction_matrix(self, matrix_by_key: dict):
            """Return a matrix cancelling the anchor's complete world delta."""
            key = self.animation_in_place_anchor_key
            baseline = self.animation_in_place_anchor_baseline_matrix
            if key is None or baseline is None:
                return None
            current = matrix_by_key.get(key)
            if current is None:
                return None
            inverse_current = self._ov_mat_inverse_affine(current)
            if inverse_current is None:
                return None
            return self._ov_mat_mul(baseline, inverse_current)

        def _animation_apply_in_place_world_lock(self, matrix_by_key: dict) -> None:
            """Hold the effective visible render branch at its frame-zero TRS."""
            correction = self._animation_in_place_correction_matrix(matrix_by_key)
            if correction is None:
                return
            for key, matrix in list(matrix_by_key.items()):
                matrix_by_key[key] = self._ov_mat_mul(correction, matrix)

        def _animation_configure_preview_geometry_anchor(self) -> None:
            """Choose the largest actual rendered part for final In-place anchoring.

            This deliberately uses Preview3D's cached render parts rather than
            inferred Unity hierarchy ownership.  It therefore survives duplicated
            rig instances, helper/controller branches and unusual parent layouts.
            """
            self.animation_in_place_preview_center = None
            self.animation_in_place_preview_child_index = None
            parts = list(getattr(self.preview_3d, "group_dynamic_parts", []) or [])
            if not parts:
                return
            best = None
            best_count = -1
            for part in parts:
                try:
                    count = len(part.get("source_vertices") or [])
                    child_index = int(part.get("child_index", -1))
                except Exception:
                    continue
                if child_index >= 0 and count > best_count:
                    best = child_index
                    best_count = count
            self.animation_in_place_preview_child_index = best

        def _animation_capture_preview_geometry_anchor(self) -> None:
            try:
                center = self.preview_3d.group_geometry_center(
                    self.animation_in_place_preview_child_index
                )
            except Exception:
                center = None
            self.animation_in_place_preview_center = center

        def _animation_apply_preview_geometry_anchor(self) -> None:
            """Final visual safety net for true In-place playback.

            The correction is applied after skinning and after every hierarchy
            matrix has been evaluated.  Unlike Transform guessing, this operates
            on the exact vertices currently shown to the user, so hidden parents
            or duplicated controller branches cannot move the asset off-screen.
            """
            target = self.animation_in_place_preview_center
            if target is None:
                return
            try:
                self.preview_3d.lock_group_geometry_center(
                    target,
                    self.animation_in_place_preview_child_index,
                )
            except Exception:
                pass

        @staticmethod
        def _animation_quat_inverse(value):
            x, y, z, w = (float(v) for v in value)
            length_sq = x*x + y*y + z*z + w*w
            if length_sq <= 1e-12:
                return (0.0, 0.0, 0.0, 1.0)
            return (-x/length_sq, -y/length_sq, -z/length_sq, w/length_sq)

        @staticmethod
        def _animation_matrix_quaternion(matrix):
            """Extract a normalized rotation quaternion from an affine matrix."""
            try:
                m = [[float(matrix[r][c]) for c in range(3)] for r in range(3)]
                scales = []
                for c in range(3):
                    scales.append(math.sqrt(sum(m[r][c] * m[r][c] for r in range(3))))
                for c in range(3):
                    scale = scales[c] if scales[c] > 1e-12 else 1.0
                    for r in range(3):
                        m[r][c] /= scale
                trace = m[0][0] + m[1][1] + m[2][2]
                if trace > 0.0:
                    s = math.sqrt(trace + 1.0) * 2.0
                    q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, 0.25 * s)
                elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
                    s = math.sqrt(max(0.0, 1.0 + m[0][0] - m[1][1] - m[2][2])) * 2.0
                    q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
                elif m[1][1] > m[2][2]:
                    s = math.sqrt(max(0.0, 1.0 + m[1][1] - m[0][0] - m[2][2])) * 2.0
                    q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
                else:
                    s = math.sqrt(max(0.0, 1.0 + m[2][2] - m[0][0] - m[1][1])) * 2.0
                    q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s, (m[1][0] - m[0][1]) / s)
                length = math.sqrt(sum(v*v for v in q))
                return tuple(v / length for v in q) if length > 1e-12 else (0.0, 0.0, 0.0, 1.0)
            except Exception:
                return (0.0, 0.0, 0.0, 1.0)

        def _animation_matrix_trs(self, matrix):
            try:
                pos = (float(matrix[0][3]), float(matrix[1][3]), float(matrix[2][3]))
                scale = tuple(math.sqrt(sum(float(matrix[r][c]) ** 2 for r in range(3))) for c in range(3))
                rot = self._animation_matrix_quaternion(matrix)
                return pos, rot, scale
            except Exception:
                return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)

        def _animation_hierarchy_components(self, max_nodes: int = 640, max_depth: int = 32):
            """Return bounded (Transform, GameObject, components) rows for the animation root.

            v2.2b originally searched every MonoBehaviour in the bundle and all
            loaded sibling indexes whenever a clip was selected.  Large courses
            can contain thousands of script records, so that synchronous scan
            made the UI appear permanently frozen.  Constraints that affect an
            isolated animation preview should normally be components on the
            selected hierarchy itself, so walk only that subtree and keep hard
            cycle/node/depth guards.
            """
            root = self.animation_root_transform
            if root is None:
                return []
            rows = []
            stack = [(root, 0)]
            seen = set()
            while stack and len(rows) < max_nodes:
                transform_rec, depth = stack.pop()
                if transform_rec is None or depth > max_depth:
                    continue
                key = self._ov_record_key(transform_rec)
                if key in seen:
                    continue
                seen.add(key)
                go = self._ov_gameobject_for_transform(transform_rec)
                components = self._ov_component_records_for_gameobject(go) if go is not None else []
                rows.append((transform_rec, go, components))
                children = self._ov_child_transform_records(transform_rec)
                for child in reversed(children):
                    stack.append((child, depth + 1))
            return rows

        def _animation_constraint_kind(self, rec, data=None) -> str:
            """Return a built-in constraint kind, including hashed Unity 6 types.

            Some Unity 6 SerializedFiles store constraints with a hashed class
            ID (for example 1818360609) rather than the familiar engine class
            name.  UnityPy may therefore expose the record as an unknown type
            even though its embedded type-tree root is ``RotationConstraint``.
            Inspect the cheap serialized-type metadata first, then fall back to
            distinctive field signatures only for candidate records.
            """
            built_in = {"RotationConstraint", "PositionConstraint", "ScaleConstraint", "ParentConstraint"}
            direct = str(getattr(rec, "type_name", "") or "")
            if direct in built_in:
                return direct

            obj = getattr(rec, "object", None)
            serialized_type = getattr(obj, "serialized_type", None)
            node_collections = []
            if serialized_type is not None:
                for attr in ("nodes", "type_tree", "m_Nodes"):
                    value = getattr(serialized_type, attr, None)
                    if value is not None:
                        node_collections.append(value)
                tree = getattr(serialized_type, "type_tree", None)
                if tree is not None:
                    for attr in ("nodes", "m_Nodes"):
                        value = getattr(tree, attr, None)
                        if value is not None:
                            node_collections.append(value)
            for collection in node_collections:
                try:
                    nodes = list(collection)
                except Exception:
                    continue
                if not nodes:
                    continue
                root = nodes[0]
                for attr in ("type", "m_Type", "type_name", "name"):
                    value = getattr(root, attr, None)
                    text = str(value or "")
                    if text in built_in:
                        return text

            # Only unknown/hashed-looking groups reach this read fallback in
            # normal operation.  The signatures are deliberately strict.
            if data is None:
                lower = direct.lower()
                if "unknown" not in lower and not direct.lstrip("-").isdigit() and not any(ch.isdigit() for ch in direct):
                    return ""
                data = self._ov_read(rec)
            if data is None:
                return ""
            sources = self._ov_get(data, "m_Sources", "sources", default=None)
            if sources is None:
                return ""
            if self._ov_get(data, "m_RotationAtRest", "rotationAtRest", default=None) is not None:
                if self._ov_get(data, "m_TranslationAtRest", "translationAtRest", default=None) is not None:
                    return "ParentConstraint"
                return "RotationConstraint"
            if self._ov_get(data, "m_TranslationAtRest", "translationAtRest", default=None) is not None:
                return "PositionConstraint"
            if self._ov_get(data, "m_ScaleAtRest", "scaleAtRest", default=None) is not None:
                return "ScaleConstraint"
            return ""

        def _animation_constraint_records(self) -> dict[str, list]:
            """Group local/external constraint records by their real type-tree kind."""
            kinds = {"RotationConstraint": [], "PositionConstraint": [], "ScaleConstraint": [], "ParentConstraint": []}
            seen = set()
            for mapping in (
                getattr(self.bundle_index, "objects_by_type", {}) or {},
                getattr(self.bundle_index, "external_records_by_type", {}) or {},
            ):
                for _group_name, records in mapping.items():
                    records = list(records or [])
                    if not records:
                        continue
                    kind = self._animation_constraint_kind(records[0])
                    if not kind:
                        continue
                    for rec in records:
                        key = self._ov_record_key(rec)
                        if key in seen:
                            continue
                        seen.add(key)
                        kinds[kind].append(rec)
            return kinds

        def _animation_prepare_constraints(self) -> tuple[int, int]:
            """Discover constraints that are relevant to the selected clip.

            Normal discovery remains bounded to the selected animation hierarchy.
            v2.2g adds a second *targeted reverse pass* over built-in constraint
            records only.  This is needed for scene rigs such as Meow Wolf Hole
            16, where the animated ``Constraint`` helper Transforms live in one
            hierarchy while RotationConstraint components are attached to the
            visible windmills in another hierarchy.

            The reverse pass never decodes every MonoBehaviour in the course; it
            examines only Rotation/Position/Scale/ParentConstraint records and
            keeps only records whose source Transform is animated by this clip.
            """
            supported = []
            unsupported = 0
            empty_cache = {}
            hierarchy_rows = self._animation_hierarchy_components()
            if not hierarchy_rows:
                self.animation_constraint_descriptors = []
                return 0, 0

            built_in_types = {"RotationConstraint", "PositionConstraint", "ScaleConstraint", "ParentConstraint"}
            seen_components = set()
            descriptor_keys = set()
            animated_keys = {
                self._ov_record_key(track.get("target_transform"))
                for track in (self.animation_tracks or [])
                if track.get("target_transform") is not None
            }

            def _try_add_builtin(rec, driven) -> tuple[bool, bool]:
                """Return (added, limited_or_unsupported)."""
                if rec is None or driven is None:
                    return False, False
                rec_key = self._ov_record_key(rec)
                if rec_key in seen_components:
                    return False, False
                seen_components.add(rec_key)
                data = self._ov_read(rec)
                type_name = self._animation_constraint_kind(rec, data)
                if type_name not in built_in_types:
                    return False, False
                if data is None:
                    return False, True

                enabled = self._ov_get(data, "m_Enabled", "enabled", default=True)
                active = self._ov_get(data, "m_IsConstraintActive", "m_IsContraintActive", "m_Active", "isActive", default=True)
                try:
                    if not bool(enabled) or not bool(active):
                        return False, False
                except Exception:
                    pass

                source_rows = self._ov_as_list(self._ov_get(data, "m_Sources", "sources", default=None))
                parsed_sources = []
                for source_row in source_rows[:32]:
                    pptr = self._ov_get(
                        source_row,
                        "sourceTransform", "m_SourceTransform", "transform", "m_Transform", "source", "m_Source",
                        default=None,
                    )
                    source = self._ov_resolve(pptr)
                    if source is None or getattr(source, "type_name", "") not in ("Transform", "RectTransform"):
                        continue
                    weight = self._animation_float(self._ov_get(source_row, "weight", "m_Weight", default=1.0), 1.0)
                    parsed_sources.append((max(0.0, weight), source))
                if not parsed_sources:
                    direct = self._ov_resolve(self._ov_get(data, "m_Source", "source", "m_SourceTransform", default=None))
                    if direct is not None and getattr(direct, "type_name", "") in ("Transform", "RectTransform"):
                        parsed_sources.append((1.0, direct))
                if not parsed_sources:
                    return False, True

                # A constraint is relevant only when at least one of its source
                # Transforms is animated by the selected clip.  This is what
                # keeps the reverse pass cheap and prevents unrelated scene
                # constraints from changing the holding pose.
                relevant_sources = [row for row in parsed_sources if self._ov_record_key(row[1]) in animated_keys]
                if not relevant_sources:
                    return False, False
                relevant_sources.sort(key=lambda row: row[0], reverse=True)
                source_weight, source = relevant_sources[0]

                dkey = (rec_key, self._ov_record_key(source), self._ov_record_key(driven))
                if dkey in descriptor_keys:
                    return False, False
                descriptor_keys.add(dkey)

                overall_weight = max(0.0, min(1.0, self._animation_float(self._ov_get(data, "m_Weight", "weight", default=1.0), 1.0)))
                weight = max(0.0, min(1.0, source_weight * overall_weight))
                self.animation_transform_by_key[self._ov_record_key(source)] = source
                self.animation_transform_by_key[self._ov_record_key(driven)] = driven
                supported.append({
                    "type": type_name,
                    "record": rec,
                    "source": source,
                    "target": driven,
                    "source_default": self._animation_relative_matrix(source, {}, empty_cache),
                    "target_default": self._animation_relative_matrix(driven, {}, empty_cache),
                    "weight": weight,
                    "multi_source": len(parsed_sources) > 1,
                    "reverse_discovered": False,
                })
                return True, len(parsed_sources) > 1

            # Fast normal pass: components attached inside the selected hierarchy.
            for driven, _go, components in hierarchy_rows:
                if driven is None:
                    continue
                for rec in components:
                    if rec is None:
                        continue
                    type_name = str(getattr(rec, "type_name", "") or "")
                    constraint_kind = self._animation_constraint_kind(rec)
                    if constraint_kind in built_in_types:
                        _added, limited = _try_add_builtin(rec, driven)
                        if limited:
                            unsupported += 1
                        continue
                    if type_name != "MonoBehaviour":
                        continue

                    rec_key = self._ov_record_key(rec)
                    if rec_key in seen_components:
                        continue
                    seen_components.add(rec_key)
                    data = self._ov_read(rec)
                    if data is None:
                        continue

                    # WAM/custom Transform driver.  Only MonoBehaviours attached
                    # to this bounded hierarchy are decoded; unrelated scripts
                    # elsewhere in the course are never touched.
                    position_flag = self._ov_get(data, "position", "copyPosition", default=None)
                    rotation_flag = self._ov_get(data, "rotation", "copyRotation", default=None)
                    scale_flag = self._ov_get(data, "scale", "copyScale", default=None)
                    if position_flag is None and rotation_flag is None and scale_flag is None:
                        continue
                    source = self._ov_resolve(self._ov_get(data, "target", "targetTransform", "m_TargetTransform", default=None))
                    if source is None or getattr(source, "type_name", "") not in ("Transform", "RectTransform"):
                        continue
                    if self._ov_record_key(source) not in animated_keys:
                        continue
                    modes = {
                        "position": bool(position_flag),
                        "rotation": bool(rotation_flag),
                        "scale": bool(scale_flag),
                    }
                    if not any(modes.values()):
                        continue
                    self.animation_transform_by_key[self._ov_record_key(source)] = source
                    self.animation_transform_by_key[self._ov_record_key(driven)] = driven
                    supported.append({
                        "type": "TransformDriver",
                        "record": rec,
                        "source": source,
                        "target": driven,
                        "source_default": self._animation_relative_matrix(source, {}, empty_cache),
                        "target_default": self._animation_relative_matrix(driven, {}, empty_cache),
                        "weight": 1.0,
                        "modes": modes,
                        "multi_source": False,
                        "reverse_discovered": False,
                    })

            # v2.2g: targeted reverse constraint discovery.  Built-in constraint
            # records are cheap and normally few in number.  Search them even
            # when their owner is outside the animated helper subtree, then keep
            # only those that reference an animated source Transform.
            constraint_records = self._animation_constraint_records()
            reverse_limit = 4096
            reverse_examined = 0
            for type_name in sorted(built_in_types):
                for rec in list(constraint_records.get(type_name, []) or []):
                    if reverse_examined >= reverse_limit:
                        unsupported += 1
                        break
                    reverse_examined += 1
                    if self._ov_record_key(rec) in seen_components:
                        continue
                    data = self._ov_read(rec)
                    if data is None:
                        seen_components.add(self._ov_record_key(rec))
                        continue
                    go = self._ov_resolve(self._ov_get(data, "m_GameObject", "gameObject", "game_object", default=None))
                    driven = self._ov_transform_for_gameobject(go) if go is not None else None
                    before = len(supported)
                    _added, limited = _try_add_builtin(rec, driven)
                    if limited:
                        unsupported += 1
                    if len(supported) > before:
                        supported[-1]["reverse_discovered"] = True
                if reverse_examined >= reverse_limit:
                    break

            # Cache affected descendants once.  Recalculating ancestry for every
            # constraint on every animation frame is both unnecessary and slow.
            for desc in supported:
                target = desc.get("target")
                desc["affected_keys"] = [
                    key for key, transform in self.animation_transform_by_key.items()
                    if self._animation_is_descendant_or_self(transform, target)
                ]

            self.animation_constraint_descriptors = supported
            return len(supported), unsupported

        def _animation_constraint_descendant_keys(self, target, matrix_by_key: dict):
            return [
                key for key, transform in self.animation_transform_by_key.items()
                if key in matrix_by_key and self._animation_is_descendant_or_self(transform, target)
            ]

        def _animation_apply_constraints(self, matrix_by_key: dict) -> None:
            if not self.animation_constraint_descriptors:
                return
            # First pass intentionally evaluates each supported constraint once.
            # Chained/multi-source blending remains reported as a limited case.
            for desc in self.animation_constraint_descriptors:
                source_key = self._ov_record_key(desc.get("source"))
                target_key = self._ov_record_key(desc.get("target"))
                source_now = matrix_by_key.get(source_key)
                target_old = matrix_by_key.get(target_key)
                source_default = desc.get("source_default")
                if source_now is None or target_old is None or source_default is None:
                    continue
                kind = str(desc.get("type") or "")
                weight = max(0.0, min(1.0, float(desc.get("weight", 1.0))))
                target_pos, target_rot, target_scale = self._animation_matrix_trs(target_old)
                source_pos, source_rot, source_scale = self._animation_matrix_trs(source_now)
                default_pos, default_rot, default_scale = self._animation_matrix_trs(source_default)
                target_new = target_old
                if kind == "RotationConstraint":
                    delta = self._animation_quat_mul(source_rot, self._animation_quat_inverse(default_rot))
                    delta = self._animation_quat_slerp((0.0, 0.0, 0.0, 1.0), delta, weight)
                    target_new = self._ov_trs_matrix(
                        target_pos,
                        self._animation_quat_mul(delta, target_rot),
                        target_scale,
                    )
                elif kind == "PositionConstraint":
                    delta_pos = tuple((source_pos[i] - default_pos[i]) * weight for i in range(3))
                    target_new = self._ov_trs_matrix(
                        tuple(target_pos[i] + delta_pos[i] for i in range(3)),
                        target_rot,
                        target_scale,
                    )
                elif kind == "ScaleConstraint":
                    ratio = tuple(
                        (source_scale[i] / default_scale[i]) if abs(default_scale[i]) > 1e-10 else 1.0
                        for i in range(3)
                    )
                    blended = tuple(1.0 + (ratio[i] - 1.0) * weight for i in range(3))
                    target_new = self._ov_trs_matrix(
                        target_pos,
                        target_rot,
                        tuple(target_scale[i] * blended[i] for i in range(3)),
                    )
                elif kind == "ParentConstraint":
                    inverse_default = self._ov_mat_inverse_affine(source_default)
                    if inverse_default is None:
                        continue
                    source_delta = self._ov_mat_mul(source_now, inverse_default)
                    dpos, drot, dscale = self._animation_matrix_trs(source_delta)
                    blended_delta = self._ov_trs_matrix(
                        tuple(value * weight for value in dpos),
                        self._animation_quat_slerp((0.0, 0.0, 0.0, 1.0), drot, weight),
                        tuple(1.0 + (value - 1.0) * weight for value in dscale),
                    )
                    target_new = self._ov_mat_mul(blended_delta, target_old)
                elif kind == "TransformDriver":
                    modes = desc.get("modes") or {}
                    new_pos, new_rot, new_scale = target_pos, target_rot, target_scale
                    if modes.get("position"):
                        delta_pos = tuple(source_pos[i] - default_pos[i] for i in range(3))
                        new_pos = tuple(target_pos[i] + delta_pos[i] for i in range(3))
                    if modes.get("rotation"):
                        delta_rot = self._animation_quat_mul(source_rot, self._animation_quat_inverse(default_rot))
                        new_rot = self._animation_quat_mul(delta_rot, target_rot)
                    if modes.get("scale"):
                        ratio = tuple(
                            (source_scale[i] / default_scale[i]) if abs(default_scale[i]) > 1e-10 else 1.0
                            for i in range(3)
                        )
                        new_scale = tuple(target_scale[i] * ratio[i] for i in range(3))
                    target_new = self._ov_trs_matrix(new_pos, new_rot, new_scale)
                inverse_old = self._ov_mat_inverse_affine(target_old)
                if inverse_old is None:
                    continue
                target_delta = self._ov_mat_mul(target_new, inverse_old)
                affected_keys = desc.get("affected_keys") or self._animation_constraint_descendant_keys(desc.get("target"), matrix_by_key)
                for key in affected_keys:
                    if key in matrix_by_key:
                        matrix_by_key[key] = self._ov_mat_mul(target_delta, matrix_by_key[key])

        def _animation_full_duration(self) -> float:
            return max(0.0, float(self.animation_duration or 0.0))

        def _animation_preview_sample_rate(self) -> float:
            """Return the authored frame rate used by preview and scrubbing.

            v2.3i deliberately samples the live viewer on authored frame
            boundaries.  Streamed clips can contain sparse component records,
            non-uniform scale and control-rig values that are valid at Unity's
            authored samples but produce an impossible pose when UBE linearly
            evaluates an arbitrary sub-frame time such as 0.005 s.
            """
            data = self.animation_clip_data
            rate = self._animation_float(
                self._ov_get(data, "m_SampleRate", "sampleRate", default=30.0)
                if data is not None else 30.0,
                30.0,
            )
            if not math.isfinite(rate) or rate <= 0.0:
                rate = 30.0
            return max(1.0, min(240.0, float(rate)))

        def _animation_preview_frame_count(self, duration: float | None = None) -> int:
            if duration is None:
                duration = self._animation_effective_duration()
            duration = max(0.0, float(duration or 0.0))
            rate = self._animation_preview_sample_rate()
            raw = duration * rate
            nearest = round(raw)
            if abs(raw - nearest) <= 1.0e-6:
                return max(1, int(nearest))
            return max(1, int(math.ceil(raw)))

        def _animation_preview_time_for_frame(self, frame_index: int) -> float:
            duration = self._animation_effective_duration()
            rate = self._animation_preview_sample_rate()
            maximum = self._animation_preview_frame_count(duration)
            frame_index = max(0, min(maximum, int(frame_index)))
            if frame_index >= maximum:
                return duration
            return min(duration, float(frame_index) / rate)

        def _animation_preview_frame_for_time(self, time_seconds: float) -> int:
            duration = self._animation_effective_duration()
            rate = self._animation_preview_sample_rate()
            maximum = self._animation_preview_frame_count(duration)
            value = max(0.0, min(duration, float(time_seconds))) if duration > 0.0 else 0.0
            if value >= duration - 1.0e-9:
                return maximum
            return max(0, min(maximum, int(round(value * rate))))

        def _animation_snap_preview_time(self, time_seconds: float) -> float:
            """Snap a live preview request to the nearest authored frame."""
            return self._animation_preview_time_for_frame(
                self._animation_preview_frame_for_time(time_seconds)
            )

        def _animation_update_slider_range(self) -> None:
            """Make one slider unit equal one authored animation frame."""
            maximum = self._animation_preview_frame_count()
            value = self._animation_preview_frame_for_time(self.animation_current_time)
            try:
                self.animation_slider_updating = True
                self.animation_slider.setRange(0, maximum)
                self.animation_slider.setSingleStep(1)
                # Page-up/down moves approximately one second.
                self.animation_slider.setPageStep(
                    max(1, int(round(self._animation_preview_sample_rate())))
                )
                self.animation_slider.setValue(max(0, min(maximum, value)))
                self.animation_slider.setToolTip(
                    f"Frame-accurate scrub: {self._animation_preview_sample_rate():g} fps, "
                    f"frames 0-{maximum}"
                )
            finally:
                self.animation_slider_updating = False

        def _animation_effective_duration(self) -> float:
            """Return the active preview/export range.

            The authored clip duration remains untouched.  A shorter range is
            used only while In place is enabled, so long scene-travel clips can
            be reduced to one clean local motion cycle without changing normal
            authored playback.
            """
            full_duration = self._animation_full_duration()
            if full_duration <= 0.0:
                return 0.0
            try:
                use_limit = bool(
                    self.animation_in_place_check.isChecked()
                    and self.animation_root_lock_keys
                )
                limit = float(self.animation_duration_limit_spin.value())
            except Exception:
                use_limit = False
                limit = full_duration
            if not use_limit:
                return full_duration
            minimum = min(0.001, full_duration)
            return min(full_duration, max(minimum, limit))

        def _animation_duration_is_limited(self) -> bool:
            full_duration = self._animation_full_duration()
            effective_duration = self._animation_effective_duration()
            return full_duration > 0.0 and effective_duration < full_duration - 1e-6

        def _animation_configure_duration_limit(self) -> None:
            full_duration = self._animation_full_duration()
            maximum = max(0.001, full_duration)
            try:
                self.animation_duration_limit_spin.blockSignals(True)
                self.animation_duration_limit_spin.setMaximum(maximum)
                self.animation_duration_limit_spin.setMinimum(min(0.001, maximum))
                self.animation_duration_limit_spin.setValue(maximum)
            finally:
                self.animation_duration_limit_spin.blockSignals(False)
            enabled = bool(self.animation_root_lock_keys and self.animation_in_place_check.isChecked())
            self.animation_duration_limit_spin.setEnabled(enabled)
            self.animation_duration_full_button.setEnabled(enabled)
            self._animation_update_slider_range()

        def _animation_duration_range_text(self) -> str:
            full_duration = self._animation_full_duration()
            effective_duration = self._animation_effective_duration()
            if self._animation_duration_is_limited():
                return f"{effective_duration:.3f} s limit (clip {full_duration:.3f} s)"
            return f"{full_duration:.3f} s"

        def _animation_refresh_time_label(self, prefix: str | None = None) -> None:
            effective_duration = self._animation_effective_duration()
            full_duration = self._animation_full_duration()
            frame_index = self._animation_preview_frame_for_time(self.animation_current_time)
            frame_count = self._animation_preview_frame_count()
            left = str(prefix) if prefix else f"{self.animation_current_time:.3f}"
            self.animation_time_label.setText(
                f"{left} / {effective_duration:.3f} s • {frame_index:,}/{frame_count:,}"
            )
            if self._animation_duration_is_limited():
                tip = (
                    f"Current time: {self.animation_current_time:.6f} s\n"
                    f"Preview/export range: first {effective_duration:.6f} s of {full_duration:.6f} s\n"
                    f"Authored frame: {frame_index:,} of {frame_count:,}"
                )
            else:
                tip = (
                    f"Current time: {self.animation_current_time:.6f} s\n"
                    f"Clip duration: {full_duration:.6f} s\n"
                    f"Authored frame: {frame_index:,} of {frame_count:,}"
                )
            self.animation_time_label.setToolTip(tip)

        def _animation_preview_visibility_changed(self, _label: str = "") -> None:
            """Refresh animation/export text after I/V or viewport-box filtering."""
            if getattr(self, "animation_clip_record", None) is not None:
                self._animation_refresh_export_status_note()

        def _animation_refresh_export_status_note(self) -> None:
            base = str(getattr(self, "animation_status_base_text", "") or "")
            if not base:
                return
            range_note = ""
            if self._animation_duration_is_limited():
                range_note = (
                    f" • range: first {self._animation_effective_duration():.3f} s "
                    f"of {self._animation_full_duration():.3f} s"
                )
            visibility_note = ""
            try:
                visible_indices = self.preview_3d.visible_group_item_indices()
            except Exception:
                visible_indices = None
            if visible_indices is not None and self.animation_render_items:
                visibility_note = (
                    f" • viewport visibility: {len(visible_indices):,}/{len(self.animation_render_items):,} "
                    f"render instance(s) shown and exported"
                )
            effective_export_eligible = bool(self.animation_export_eligible)
            if visible_indices is not None and not visible_indices:
                effective_export_eligible = False
            try:
                self.animation_export_glb_button.setEnabled(effective_export_eligible)
            except Exception:
                pass
            if effective_export_eligible:
                export_warnings = list(getattr(self, "animation_export_warnings", []) or [])
                if export_warnings:
                    export_note = f" • Animated GLB export available: {export_warnings[0]}"
                else:
                    export_note = " • Animated GLB export available"
            else:
                if visible_indices is not None and not visible_indices:
                    first_reason = "viewport visibility hides every render instance"
                else:
                    first_reason = str(
                        self.animation_export_reason
                        or "preview hierarchy not structurally exportable"
                    ).split(";", 1)[0].strip()
                export_note = f" • Animated GLB unavailable: {first_reason}"
            self.animation_status_label.setText(base + range_note + visibility_note + export_note)

        def _animation_refresh_export_eligibility(self) -> None:
            context = dict(getattr(self, "animation_export_context", {}) or {})
            if context:
                self._animation_configure_glb_export(**context)
            else:
                self._animation_refresh_export_status_note()

        def _animation_restore_full_duration(self) -> None:
            try:
                self.animation_duration_limit_spin.setValue(
                    max(0.001, self._animation_full_duration())
                )
            except Exception:
                pass

        def _animation_duration_limit_changed(self, _value: float) -> None:
            if not self.animation_tracks:
                return
            effective_duration = self._animation_effective_duration()
            if self.animation_current_time > effective_duration:
                self.animation_current_time = effective_duration
            self.animation_playback_time = min(
                effective_duration,
                max(0.0, float(self.animation_current_time)),
            )
            self._animation_update_slider_range()
            if not getattr(self, "animation_pose_is_default", True):
                self._animation_apply_time(self.animation_current_time, update_slider=True)
            else:
                self._animation_refresh_time_label("Default pose")
            self._animation_refresh_export_eligibility()

        def _animation_in_place_toggled(self, checked: bool) -> None:
            enabled = bool(checked and self.animation_root_lock_keys)
            try:
                self.animation_duration_limit_spin.setEnabled(enabled)
                self.animation_duration_full_button.setEnabled(enabled)
            except Exception:
                pass
            if not self.animation_tracks:
                self._animation_refresh_export_eligibility()
                return

            effective_duration = self._animation_effective_duration()
            saved_time = min(
                effective_duration,
                max(0.0, float(self.animation_current_time)),
            )
            self.animation_playback_time = saved_time
            self._animation_update_slider_range()

            if enabled and not getattr(self, "animation_pose_is_default", True):
                # Evaluate the exact authored first frame without an old geometry
                # anchor, reframe it once, then capture the rendered main-part
                # centre.  Every later pose is shifted back to this same point.
                self.animation_in_place_preview_center = None
                self._animation_apply_time(0.0, update_slider=False)
                try:
                    self.preview_3d.reframe_current_group_pose(reset_distance=True)
                except Exception:
                    pass
                self._animation_capture_preview_geometry_anchor()
                self._animation_apply_time(saved_time, update_slider=True)
            elif not getattr(self, "animation_pose_is_default", True):
                self._animation_apply_time(saved_time, update_slider=True)
                try:
                    self.preview_3d.reframe_current_group_pose(reset_distance=True)
                except Exception:
                    pass
            else:
                self._animation_refresh_time_label("Default pose")
            self._animation_refresh_export_eligibility()

        def _animation_add_sampled_override(
            self,
            overrides: dict,
            target_key,
            kind: str,
            sampled,
            *,
            in_place: bool,
        ) -> None:
            """Store one sampled channel, applying the first-frame in-place lock."""
            if (
                in_place
                and self.animation_in_place_anchor_baseline_matrix is None
                and target_key in self.animation_root_lock_keys
                and kind in ("position", "rotation", "euler", "scale")
            ):
                locked = (self.animation_in_place_baseline.get(target_key) or {}).get(kind)
                if locked is not None:
                    overrides.setdefault(target_key, {})[kind] = locked
                # If no authored baseline exists, leave the serialized component
                # untouched rather than reintroducing scene-travel/root-heading
                # motion from a partial channel.
                return
            overrides.setdefault(target_key, {})[kind] = sampled

        def _animation_local_matrix(self, transform_rec, overrides: dict):
            pos, rot, scale = self._animation_base_trs(transform_rec)
            override = overrides.get(self._ov_record_key(transform_rec), {})
            if "position" in override:
                pos = override["position"]
            if "scale" in override:
                scale = override["scale"]
            if "rotation" in override:
                rot = override["rotation"]
            elif "euler" in override:
                rot = self._animation_euler_quaternion(override["euler"])
            return self._ov_trs_matrix(pos, rot, scale)

        def _animation_relative_matrix(self, transform_rec, overrides: dict, cache: dict):
            if transform_rec is None:
                return self._ov_mat_identity()
            key = self._ov_record_key(transform_rec)
            if key in cache:
                return cache[key]
            root = self.animation_root_transform
            root_key = self._ov_record_key(root) if root is not None else None
            if root_key is not None and key == root_key:
                # Preview coordinates are relative to the root's default pose.
                base = self._ov_transform_local_matrix(root)
                animated = self._animation_local_matrix(root, overrides)
                inverse = self._ov_mat_inverse_affine(base)
                matrix = self._ov_mat_mul(inverse, animated) if inverse is not None else self._ov_mat_identity()
                cache[key] = matrix
                return matrix
            parent = self._ov_parent_transform_record(transform_rec)
            if parent is None:
                parent_matrix = self._ov_mat_identity()
            else:
                parent_matrix = self._animation_relative_matrix(parent, overrides, cache)
            matrix = self._ov_mat_mul(parent_matrix, self._animation_local_matrix(transform_rec, overrides))
            cache[key] = matrix
            return matrix

        def _animation_prepare_skinning(self, items: list[dict], progress_callback=None) -> tuple[int, int]:
            """Prepare first-pass CPU linear-blend skinning for visible renderers.

            Returns (playable skinned renderers, detected but unsupported renderers).
            The implementation deliberately accepts both older explicit
            ``m_BoneWeights`` arrays and modern BlendWeight/BlendIndices vertex
            channels through the shared mesh decoder.
            """
            from ..core.skinning import extract_bind_poses, extract_bone_weights, pack_bone_weights
            try:
                from ..exporters.mesh_exporter import _read_mesh_stream_bytes_from_record
            except Exception:
                _read_mesh_stream_bytes_from_record = None

            descriptors = []
            unsupported = 0
            parts = list(getattr(self.preview_3d, "group_dynamic_parts", []) or [])
            part_by_item = {int(part.get("item_index", -1)): part for part in parts}

            total_items = len(items or [])
            progress_step = max(1, total_items // 10) if total_items else 1
            for item_index, item in enumerate(items or []):
                if progress_callback is not None and (
                    item_index == 0 or (item_index + 1) % progress_step == 0 or item_index + 1 == total_items
                ):
                    progress_callback(
                        f"Preparing CPU skinning: {item_index + 1:,}/{total_items:,} render instance(s)…"
                    )
                rec = item.get("record") if isinstance(item, dict) else None
                go_rec = self._ov_owning_gameobject(rec) if rec is not None else None
                if go_rec is None:
                    continue
                components = self._ov_component_records_for_gameobject(go_rec)
                skinned = rec if getattr(rec, "type_name", "") == "SkinnedMeshRenderer" else next(
                    (comp for comp in components if getattr(comp, "type_name", "") == "SkinnedMeshRenderer"), None
                )
                if skinned is None:
                    hits = self._ov_records_with_gameobject("SkinnedMeshRenderer", go_rec)
                    skinned = hits[0] if hits else None
                if skinned is None:
                    continue

                sm_data = self._ov_read(skinned)
                mesh_rec = self._ov_resolve(self._ov_get(sm_data, "m_Mesh", "mesh", default=None)) if sm_data is not None else None
                bones = [
                    bone for bone in (
                        self._ov_resolve(pptr)
                        for pptr in self._ov_as_list(self._ov_get(sm_data, "m_Bones", "bones", default=None))
                    ) if bone is not None and getattr(bone, "type_name", "") in ("Transform", "RectTransform")
                ] if sm_data is not None else []
                if mesh_rec is None or not bones:
                    unsupported += 1
                    continue
                mesh_data = self._ov_read(mesh_rec)
                if mesh_data is None:
                    unsupported += 1
                    continue
                raw = None
                if _read_mesh_stream_bytes_from_record is not None:
                    try:
                        raw = _read_mesh_stream_bytes_from_record(mesh_rec, mesh_data)
                    except Exception:
                        raw = None
                weights = extract_bone_weights(mesh_data, raw_override=raw)
                bind_poses = extract_bind_poses(mesh_data)
                part = part_by_item.get(item_index)
                source_vertices = list(part.get("source_vertices") or []) if part else []
                if not weights or not bind_poses or not source_vertices:
                    unsupported += 1
                    continue
                count = min(len(bones), len(bind_poses))
                if count <= 0 or len(weights) != len(source_vertices):
                    unsupported += 1
                    continue
                renderer_transform = item.get("transform")
                if renderer_transform is None:
                    renderer_transform = self._ov_transform_for_gameobject(go_rec)
                if renderer_transform is None:
                    unsupported += 1
                    continue
                root_bone = self._ov_resolve(self._ov_get(sm_data, "m_RootBone", "rootBone", default=None)) if sm_data is not None else None
                if root_bone is not None and getattr(root_bone, "type_name", "") not in ("Transform", "RectTransform"):
                    root_bone = None
                descriptors.append({
                    "record": rec,
                    "skinned_record": skinned,
                    "mesh_record": mesh_rec,
                    "child_index": int(part.get("child_index", -1)),
                    "renderer_transform": renderer_transform,
                    "root_bone": root_bone,
                    "bones": bones[:count],
                    "bind_poses": bind_poses[:count],
                    "weights": weights,
                    "packed_weights": pack_bone_weights(weights),
                    "source_vertices": source_vertices,
                    "name": getattr(go_rec, "name", getattr(skinned, "name", "Skinned mesh")),
                })
                self.animation_transform_by_key[self._ov_record_key(renderer_transform)] = renderer_transform
                for bone in bones[:count]:
                    self.animation_transform_by_key[self._ov_record_key(bone)] = bone

            self.animation_skinning_descriptors = descriptors
            return len(descriptors), unsupported

        def _animation_skinned_vertices(self, matrix_by_key: dict) -> dict[int, list]:
            from ..core.skinning import skin_vertices_obj_basis, skin_vertices_obj_basis_packed
            output = {}
            for desc in self.animation_skinning_descriptors or []:
                renderer = desc.get("renderer_transform")
                renderer_matrix = matrix_by_key.get(self._ov_record_key(renderer))
                inverse_renderer = self._ov_mat_inverse_affine(renderer_matrix) if renderer_matrix is not None else None
                if inverse_renderer is None:
                    continue
                skin_matrices = []
                for bone, bind_pose in zip(desc.get("bones") or [], desc.get("bind_poses") or []):
                    bone_matrix = matrix_by_key.get(self._ov_record_key(bone))
                    if bone_matrix is None:
                        skin_matrices.append(self._ov_mat_identity())
                        continue
                    skin_matrices.append(self._ov_mat_mul(self._ov_mat_mul(inverse_renderer, bone_matrix), bind_pose))
                try:
                    if desc.get("packed_weights") is not None:
                        skinned = skin_vertices_obj_basis_packed(
                            desc.get("source_vertices") or [],
                            desc.get("packed_weights"),
                            skin_matrices,
                        )
                    else:
                        skinned = skin_vertices_obj_basis(
                            desc.get("source_vertices") or [],
                            desc.get("weights") or [],
                            skin_matrices,
                        )
                    output[int(desc.get("child_index", -1))] = skinned
                except Exception:
                    continue
            return output

        def _animation_apply_time(self, time_seconds: float, update_slider: bool = True) -> None:
            if not self.animation_tracks or self.animation_root_transform is None:
                return
            duration = self._animation_effective_duration()
            time_seconds = max(0.0, min(duration, float(time_seconds))) if duration > 0.0 else 0.0
            # v2.3i: never evaluate the live viewer at an invented sub-frame
            # time.  This avoids one-tick scale/shear explosions in streamed
            # control rigs while preserving their exact authored samples.
            time_seconds = self._animation_snap_preview_time(time_seconds)
            overrides: dict[tuple, dict] = {}
            for track in self.animation_tracks:
                target = track.get("target_transform")
                if target is None:
                    continue
                sampled = self._animation_sample_track(track, time_seconds)
                if sampled is None:
                    continue
                target_key = self._ov_record_key(target)
                kind = str(track.get("kind"))
                self._animation_add_sampled_override(
                    overrides,
                    target_key,
                    kind,
                    sampled,
                    in_place=bool(self.animation_in_place_check.isChecked()),
                )

            cache: dict[tuple, list] = {}
            matrix_by_key = {}
            for key, transform_rec in self.animation_transform_by_key.items():
                matrix_by_key[key] = self._animation_relative_matrix(transform_rec, overrides, cache)
            self._animation_apply_constraints(matrix_by_key)
            if (
                self.animation_in_place_check.isChecked()
                and self.animation_in_place_anchor_baseline_matrix is not None
            ):
                self._animation_apply_in_place_world_lock(matrix_by_key)
            try:
                local_vertices_by_child = self._animation_skinned_vertices(matrix_by_key)
                self.preview_3d.apply_group_dynamic_matrices(matrix_by_key, local_vertices_by_child)
                if self.animation_in_place_check.isChecked():
                    self._animation_apply_preview_geometry_anchor()
            except Exception:
                return

            self.animation_current_time = time_seconds
            self.animation_pose_is_default = False
            if update_slider:
                self.animation_slider_updating = True
                try:
                    slider_value = self._animation_preview_frame_for_time(time_seconds)
                    self.animation_slider.setValue(
                        max(0, min(self.animation_slider.maximum(), slider_value))
                    )
                finally:
                    self.animation_slider_updating = False
            self._animation_refresh_time_label()

        def _animation_apply_default_pose(self) -> None:
            matrix_by_key = {}
            for item in self.animation_render_items:
                transform = item.get("transform")
                if transform is not None:
                    matrix_by_key[self._ov_record_key(transform)] = item.get("matrix") or self._ov_mat_identity()
            try:
                self.preview_3d.apply_group_dynamic_matrices(matrix_by_key)
            except Exception:
                pass
            self.animation_pose_is_default = True

        def _animation_slider_changed(self, value: int) -> None:
            if self.animation_slider_updating or not self.animation_tracks:
                return
            try:
                self.animation_timer.stop()
                self.animation_play_button.setText("Play")
            except Exception:
                pass
            time_seconds = self._animation_preview_time_for_frame(int(value))
            self.animation_playback_time = time_seconds
            self._animation_apply_time(time_seconds, update_slider=False)

        def _animation_toggle_play(self) -> None:
            duration = self._animation_effective_duration()
            if not self.animation_tracks or duration <= 0.0:
                return
            if self.animation_timer.isActive():
                self.animation_timer.stop()
                self.animation_play_button.setText("Play")
                return
            if self.animation_current_time >= duration - 1e-6:
                self.animation_current_time = 0.0
            self.animation_playback_time = float(self.animation_current_time)
            if getattr(self, "animation_pose_is_default", False):
                # Reset pose is an explicit inspection state.  When playback
                # resumes, move to and frame the clip's sampled t=0 pose before
                # advancing so the camera does not appear to throw the object.
                self.animation_current_time = 0.0
                self.animation_playback_time = 0.0
                self._animation_apply_time(0.0)
                try:
                    self.preview_3d.reframe_current_group_pose(reset_distance=True)
                except Exception:
                    pass
            self.animation_last_clock = time.perf_counter()
            self.animation_timer.start()
            self.animation_play_button.setText("Pause")

        def _animation_reset_pose(self) -> None:
            """Return to the clip's first valid rendered frame.

            Older builds restored the raw serialized/rest hierarchy here.  Large
            environmental rigs can keep authoring controllers, duplicate scene
            instances or extreme placement/scale values in that rest state.  The
            result looked like a camera zoom-out or a missing creature even though
            animation playback itself was correct.

            For an animation player, "Reset pose" should mean the same clean
            frame-zero pose initially shown when the clip opens.  Evaluate that
            pose through the complete animation, constraint, skinning and In-place
            pipeline, then frame the visible geometry normally.
            """
            try:
                self.animation_timer.stop()
            except Exception:
                pass
            self.animation_play_button.setText("Play")
            self.animation_current_time = 0.0
            self.animation_playback_time = 0.0
            self.animation_slider_updating = True
            try:
                self.animation_slider.setValue(0)
            finally:
                self.animation_slider_updating = False

            # Use the exact same authored frame-zero evaluation as initial load
            # and playback.  This deliberately avoids the raw serialized/rest
            # transforms, which may be scene-placement data rather than a useful
            # character pose.
            self._animation_apply_time(0.0, update_slider=False)
            try:
                self.preview_3d.reframe_current_group_pose(reset_distance=True)
            except Exception:
                pass
            self._animation_refresh_time_label()
            try:
                self.statusBar().showMessage(
                    "Animation reset to the clip's rendered first frame",
                    4000,
                )
            except Exception:
                pass

        def _animation_tick(self) -> None:
            duration = self._animation_effective_duration()
            if not self.animation_tracks or duration <= 0.0:
                self.animation_timer.stop()
                self.animation_play_button.setText("Play")
                return
            now = time.perf_counter()
            delta = max(0.0, min(0.25, now - float(self.animation_last_clock or now)))
            self.animation_last_clock = now
            try:
                speed = float(self.animation_speed_combo.currentData() or 1.0)
            except Exception:
                speed = 1.0
            self.animation_playback_time = max(
                0.0,
                float(getattr(self, "animation_playback_time", self.animation_current_time))
                + delta * speed,
            )
            if self.animation_playback_time >= duration:
                if self.animation_loop_check.isChecked():
                    self.animation_playback_time = self.animation_playback_time % duration
                else:
                    self.animation_playback_time = duration
                    self.animation_timer.stop()
                    self.animation_play_button.setText("Play")
            self._animation_apply_time(self.animation_playback_time)

        def _animation_uncorrected_matrix_map_for_time(self, time_seconds: float) -> dict:
            """Evaluate the authored hierarchy before any In-place correction."""
            duration = max(0.0, float(self.animation_duration or 0.0))
            time_seconds = max(0.0, min(duration, float(time_seconds))) if duration > 0.0 else 0.0
            overrides: dict[tuple, dict] = {}
            for track in self.animation_tracks or []:
                target = track.get("target_transform")
                if target is None:
                    continue
                sampled = self._animation_sample_track(track, time_seconds)
                if sampled is None:
                    continue
                target_key = self._ov_record_key(target)
                kind = str(track.get("kind") or "")
                overrides.setdefault(target_key, {})[kind] = sampled

            cache: dict[tuple, list] = {}
            matrix_by_key = {}
            for key, transform_rec in self.animation_transform_by_key.items():
                matrix_by_key[key] = self._animation_relative_matrix(transform_rec, overrides, cache)
            self._animation_apply_constraints(matrix_by_key)
            return matrix_by_key

        def _animation_matrix_map_for_time(self, time_seconds: float, *, in_place: bool = False) -> dict:
            """Evaluate rigid preview matrices without changing the live viewer state."""
            matrix_by_key = self._animation_uncorrected_matrix_map_for_time(time_seconds)
            if in_place and self.animation_in_place_anchor_baseline_matrix is not None:
                self._animation_apply_in_place_world_lock(matrix_by_key)
            return matrix_by_key

        def _animation_local_matrix_map_for_time(
            self,
            time_seconds: float,
            transforms: list,
            *,
            in_place: bool = False,
        ) -> dict:
            """Evaluate local animation matrices for glTF node hierarchy export.

            The selected animation root uses the same default-pose-relative delta
            as the live preview. Descendants keep their authored local TRS, which
            lets glTF preserve non-uniform bone scale without baking hierarchy
            shear into global matrices.
            """
            duration = max(0.0, float(self.animation_duration or 0.0))
            time_seconds = max(0.0, min(duration, float(time_seconds))) if duration > 0.0 else 0.0
            overrides: dict[tuple, dict] = {}
            for track in self.animation_tracks or []:
                target = track.get("target_transform")
                if target is None:
                    continue
                sampled = self._animation_sample_track(track, time_seconds)
                if sampled is None:
                    continue
                target_key = self._ov_record_key(target)
                kind = str(track.get("kind") or "")
                self._animation_add_sampled_override(
                    overrides,
                    target_key,
                    kind,
                    sampled,
                    in_place=in_place,
                )

            root = self.animation_root_transform
            root_key = self._ov_record_key(root) if root is not None else None
            root_base_inverse = None
            if root is not None:
                root_base_inverse = self._ov_mat_inverse_affine(self._ov_transform_local_matrix(root))

            out = {}
            for transform_rec in transforms or []:
                if transform_rec is None:
                    continue
                key = self._ov_record_key(transform_rec)
                matrix = self._animation_local_matrix(transform_rec, overrides)
                if root_key is not None and key == root_key:
                    matrix = self._ov_mat_mul(root_base_inverse, matrix) if root_base_inverse is not None else self._ov_mat_identity()
                out[key] = matrix

            # v2.3m: glTF local hierarchy equivalent of the live world-anchor
            # correction.  Applying the correction once to the exported root
            # carries it through every descendant without altering bone-local
            # deformation.
            if (
                in_place
                and self.animation_in_place_anchor_baseline_matrix is not None
                and root_key is not None
                and root_key in out
            ):
                global_map = self._animation_uncorrected_matrix_map_for_time(time_seconds)
                correction = self._animation_in_place_correction_matrix(global_map)
                if correction is not None:
                    out[root_key] = self._ov_mat_mul(correction, out[root_key])
            return out

        def _animation_skin_export_template(self, desc: dict) -> tuple[dict | None, str]:
            """Build a parent-first local Transform hierarchy for one skin.

            glTF only requires deforming bones in ``skin.joints``; intermediary
            controls/helpers may still be ordinary nodes. Including the complete
            root-to-bone chains preserves the exact local TRS hierarchy already
            proven by UBE's CPU-skinned preview.
            """
            root = self.animation_root_transform
            renderer = desc.get("renderer_transform") if isinstance(desc, dict) else None
            bones = list(desc.get("bones") or []) if isinstance(desc, dict) else []
            if root is None or renderer is None or not bones:
                return None, "skin has no resolved animation root, renderer Transform, or bones"

            root_key = self._ov_record_key(root)
            required = {}
            for target in [renderer, *bones]:
                current = target
                reached_root = False
                for _ in range(192):
                    if current is None:
                        break
                    key = self._ov_record_key(current)
                    required[key] = current
                    if key == root_key:
                        reached_root = True
                        break
                    current = self._ov_parent_transform_record(current)
                if not reached_root:
                    return None, "a renderer/bone Transform does not descend from the selected animation root"

            depth_cache = {}
            def depth(transform_rec):
                key = self._ov_record_key(transform_rec)
                if key in depth_cache:
                    return depth_cache[key]
                current = transform_rec
                value = 0
                for _ in range(192):
                    if current is None:
                        value = 9999
                        break
                    current_key = self._ov_record_key(current)
                    if current_key == root_key:
                        break
                    current = self._ov_parent_transform_record(current)
                    value += 1
                depth_cache[key] = value
                return value

            ordered = sorted(
                required.values(),
                key=lambda tr: (
                    depth(tr),
                    str(getattr(self._ov_gameobject_for_transform(tr), "name", getattr(tr, "name", "")) or ""),
                    int(getattr(tr, "path_id", 0) or 0),
                ),
            )
            index_by_key = {self._ov_record_key(tr): index for index, tr in enumerate(ordered)}
            nodes = []
            for tr in ordered:
                parent = self._ov_parent_transform_record(tr)
                parent_index = index_by_key.get(self._ov_record_key(parent), -1) if parent is not None else -1
                go = self._ov_gameobject_for_transform(tr)
                nodes.append({
                    "transform": tr,
                    "name": str(getattr(go, "name", getattr(tr, "name", "Transform")) or "Transform"),
                    "path_id": getattr(tr, "path_id", None),
                    "parent_index": int(parent_index),
                })

            try:
                joint_indices = [index_by_key[self._ov_record_key(bone)] for bone in bones]
                renderer_node_index = index_by_key[self._ov_record_key(renderer)]
            except Exception:
                return None, "skin hierarchy could not map all deforming bones or the renderer Transform"

            root_bone = desc.get("root_bone")
            root_bone_node_index = index_by_key.get(self._ov_record_key(root_bone), -1) if root_bone is not None else -1
            return {
                "nodes": nodes,
                "joints": joint_indices,
                "renderer_node_index": int(renderer_node_index),
                "root_bone_node_index": int(root_bone_node_index),
                "bind_poses": list(desc.get("bind_poses") or []),
                "weights": list(desc.get("weights") or []),
                "mesh_record": desc.get("mesh_record"),
                "name": str(desc.get("name") or "Skinned mesh"),
            }, ""

        @staticmethod
        def _animation_float32(value: float) -> float:
            """Round a Python float exactly as it will be stored in a glTF FLOAT accessor."""
            return struct.unpack("<f", struct.pack("<f", float(value)))[0]

        def _animation_glb_sample_times(self, sample_rate: float | None = None) -> tuple[float, list[float]]:
            """Build a strictly increasing float32 timeline ending at clip duration.

            glTF animation input accessors must be strictly increasing.  Building
            the old timeline with ``min(duration, frame/rate)`` could create two
            identical final float32 values when the clip duration already landed
            on a sample boundary.
            """
            data = self.animation_clip_data
            source_rate = self._animation_float(
                self._ov_get(data, "m_SampleRate", "sampleRate", default=30.0) if data is not None else 30.0,
                30.0,
            )
            rate = float(sample_rate) if sample_rate is not None else source_rate
            rate = max(1.0, min(60.0, rate if rate > 0.0 else 30.0))
            end_time = self._animation_float32(self._animation_effective_duration())
            if end_time <= 0.0:
                return rate, [0.0, self._animation_float32(1.0 / rate)]

            times = [0.0]
            frame_index = 1
            # The eligibility guard rejects very large timelines; keep a hard
            # stop here as an additional safety boundary.
            while frame_index <= 12000:
                value = self._animation_float32(frame_index / rate)
                if value >= end_time:
                    break
                if value > times[-1]:
                    times.append(value)
                frame_index += 1
            if end_time > times[-1]:
                times.append(end_time)
            if len(times) < 2:
                times.append(self._animation_float32(times[0] + 1.0 / rate))
            return rate, times

        def _animation_glb_sample_plan(self) -> tuple[float, int, int]:
            sample_rate, times = self._animation_glb_sample_times()
            frame_count = len(times)
            total_part_samples = frame_count * max(1, len(self.animation_render_items or []))
            return sample_rate, frame_count, total_part_samples

        def _animation_configure_glb_export(
            self,
            *,
            unresolved: list[str],
            skinned_count: int,
            unsupported_skin_count: int,
            constraint_count: int,
            unsupported_constraint_count: int,
            runtime_warning: bool,
            progress_callback=None,
        ) -> None:
            """Show Animated GLB for a structurally representable rigid/skinned clip.

            v2.3f: the resolved preview hierarchy is authoritative for export.
            Runtime owner/linkage diagnostics and non-Transform property bindings
            remain useful warnings, but no longer hide an otherwise complete
            skeletal/Transform export.  This supports clips whose animation plays
            flawlessly even when Unity's runtime owner points at an unrelated
            scene object or when constant/unsupported renderer properties are
            also present in the binding table.
            """
            reasons = []
            warnings = []
            effective_duration = self._animation_effective_duration()
            full_duration = self._animation_full_duration()
            in_place = bool(self.animation_in_place_check.isChecked())
            if not self.animation_tracks or effective_duration <= 0.0:
                reasons.append("no playable Transform timeline")
            if unresolved:
                reasons.append(f"{len(unresolved)} unresolved target path(s)")
            if unsupported_skin_count:
                reasons.append(f"{unsupported_skin_count} skinned renderer(s) lack complete bone/weight/bind-pose data")
            skin_templates = []
            if skinned_count:
                for desc in self.animation_skinning_descriptors or []:
                    template, reason = self._animation_skin_export_template(desc)
                    if template is None:
                        reasons.append(reason or "a skinned renderer hierarchy is incomplete")
                    else:
                        skin_templates.append(template)
            if constraint_count or unsupported_constraint_count:
                reasons.append("constraint-driven motion is not exported")
            unsupported_props = int(getattr(self, "animation_unsupported_property_bindings", 0) or 0)
            if unsupported_props:
                warnings.append(
                    f"{unsupported_props} non-Transform property binding(s) will be omitted"
                )
            if runtime_warning:
                warnings.append(
                    "runtime owner/linkage warning ignored; export uses the resolved preview hierarchy"
                )
            if self._animation_duration_is_limited():
                warnings.append(
                    f"animation trimmed to the first {effective_duration:.3f} s of the "
                    f"{full_duration:.3f} s clip"
                )
            if not self.animation_render_items:
                reasons.append("no renderable instances")

            record_keys = []
            for item in self.animation_render_items or []:
                rec = item.get("record") if isinstance(item, dict) else None
                tr = item.get("transform") if isinstance(item, dict) else None
                if rec is None or tr is None:
                    reasons.append("a render instance lacks a stable record/Transform")
                    continue
                record_keys.append((
                    str(getattr(rec, "source_name", "") or ""),
                    str(getattr(rec, "type_name", "") or ""),
                    getattr(rec, "path_id", id(rec)),
                ))
            if len(record_keys) != len(set(record_keys)):
                reasons.append("duplicate renderer records need separate instance-node export")

            # Rigid render wrappers are baked from global matrices, so actual
            # hierarchy shear remains a rejection for *rigid* instances.
            # Skinned renderers use the actual local Transform hierarchy and can
            # preserve non-uniform bone/helper scale directly as glTF node TRS.
            #
            # v2.2v: mixed scenes (for example a skinned character plus a chair
            # or tea-set prop) must not make the skinned rig fall back through the
            # rigid shear gate. The previous all-or-nothing ``fully_skinned``
            # test hid otherwise valid exports as soon as one rigid prop existed.
            skin_record_keys = {
                (
                    str(getattr(desc.get("record"), "source_name", "") or ""),
                    str(getattr(desc.get("record"), "type_name", "") or ""),
                    getattr(desc.get("record"), "path_id", id(desc.get("record"))),
                )
                for desc in (self.animation_skinning_descriptors or [])
                if isinstance(desc, dict) and desc.get("record") is not None
            }
            skin_transform_keys = set()
            for template in skin_templates:
                for node in template.get("nodes") or []:
                    transform_rec = node.get("transform") if isinstance(node, dict) else None
                    if transform_rec is not None:
                        skin_transform_keys.add(self._ov_record_key(transform_rec))

            rigid_items = []
            for item in self.animation_render_items or []:
                rec = item.get("record") if isinstance(item, dict) else None
                if rec is None:
                    rigid_items.append(item)
                    continue
                rec_key = (
                    str(getattr(rec, "source_name", "") or ""),
                    str(getattr(rec, "type_name", "") or ""),
                    getattr(rec, "path_id", id(rec)),
                )
                if rec_key not in skin_record_keys:
                    rigid_items.append(item)

            # v2.4a: non-uniform scale by itself is valid glTF TRS.  The old
            # eligibility gate rejected any such scale anywhere in a rigid
            # hierarchy, even when the final rendered matrices remained perfectly
            # orthogonal (for example Amusement Park's Sheep Carousel).  Track the
            # authored condition for a useful export note, but decide safety from
            # the actual sampled global matrices instead.
            nonuniform_rigid_scale = False
            scale_checked = set()
            for item in rigid_items:
                current = item.get("transform") if isinstance(item, dict) else None
                for _ in range(96):
                    if current is None:
                        break
                    current_key = self._ov_record_key(current)
                    if current_key in skin_transform_keys or current_key in scale_checked:
                        break
                    scale_checked.add(current_key)
                    _pos, _rot, scale = self._animation_base_trs(current)
                    magnitudes = [abs(float(v)) for v in scale]
                    if max(magnitudes) - min(magnitudes) > 1e-5:
                        nonuniform_rigid_scale = True
                    if self.animation_root_transform is not None and current_key == self._ov_record_key(self.animation_root_transform):
                        break
                    current = self._ov_parent_transform_record(current)

            for track in self.animation_tracks or []:
                if str(track.get("kind") or "") != "scale":
                    continue
                target_transform = track.get("target_transform")
                if target_transform is not None and self._ov_record_key(target_transform) in skin_transform_keys:
                    continue
                for _time, value in track.get("keys") or []:
                    magnitudes = [abs(float(v)) for v in value]
                    if max(magnitudes) - min(magnitudes) > 1e-5:
                        nonuniform_rigid_scale = True
                        break

            # Sample the matrices that will actually be baked.  A rotation above
            # a non-uniformly scaled leaf is still valid TRS; a rotation below a
            # non-uniform scale creates true affine shear and remains rejected.
            # Eligibility uses at most 96 evenly distributed samples to stay
            # responsive.  The exporter validates every baked frame again before
            # writing any glTF channels, so an intermittent unsafe frame cannot be
            # silently approximated.
            if not reasons and rigid_items and effective_duration > 0.0:
                _shear_rate, all_shear_times = self._animation_glb_sample_times()
                if len(all_shear_times) <= 96:
                    shear_times = list(all_shear_times)
                else:
                    last_index = len(all_shear_times) - 1
                    shear_indices = sorted({
                        int(round(step * last_index / 95.0))
                        for step in range(96)
                    })
                    shear_times = [all_shear_times[index] for index in shear_indices]
                shear_failure = None
                shear_total = len(shear_times)
                shear_step = max(1, shear_total // 8) if shear_total else 1
                for shear_index, sample_time in enumerate(shear_times):
                    if progress_callback is not None and (
                        shear_index == 0 or (shear_index + 1) % shear_step == 0 or shear_index + 1 == shear_total
                    ):
                        progress_callback(
                            f"Checking Animated GLB compatibility: representative pose "
                            f"{shear_index + 1:,}/{shear_total:,}…"
                        )
                    matrix_map = self._animation_matrix_map_for_time(sample_time, in_place=in_place)
                    for item in rigid_items:
                        transform_rec = item.get("transform") if isinstance(item, dict) else None
                        if transform_rec is None:
                            continue
                        matrix = matrix_map.get(self._ov_record_key(transform_rec))
                        if matrix is None:
                            matrix = item.get("matrix") or self._ov_mat_identity()
                        shear = _matrix_gltf_trs_shear(matrix)
                        if shear > 2e-4:
                            record = item.get("record") if isinstance(item, dict) else None
                            name = str(getattr(record, "name", "rigid renderer") or "rigid renderer")
                            shear_failure = (name, float(sample_time), float(shear))
                            break
                    if shear_failure is not None:
                        break
                if shear_failure is not None:
                    name, sample_time, shear = shear_failure
                    reasons.append(
                        f"rigid hierarchy produces glTF-inexpressible shear on {name} "
                        f"at {sample_time:.3f} s (basis error {shear:.6g})"
                    )
                elif nonuniform_rigid_scale:
                    warnings.append(
                        "non-uniform rigid scale is shear-free in sampled poses and will be preserved as glTF TRS"
                    )

            # Ensure at least one visible rigid transform or deforming bone
            # actually changes. This prevents offering an export for helper-only
            # tracks that never reach the displayed result.
            if not reasons and effective_duration > 0.0:
                sample_maps = [
                    self._animation_matrix_map_for_time(0.0, in_place=in_place),
                    self._animation_matrix_map_for_time(effective_duration * 0.5, in_place=in_place),
                    self._animation_matrix_map_for_time(effective_duration, in_place=in_place),
                ]
                visible_change = False
                candidate_transforms = []
                for item in self.animation_render_items or []:
                    transform = item.get("transform") if isinstance(item, dict) else None
                    if transform is not None:
                        candidate_transforms.append(transform)
                for desc in self.animation_skinning_descriptors or []:
                    candidate_transforms.extend(list(desc.get("bones") or []))
                seen_change_keys = set()
                for transform in candidate_transforms:
                    key = self._ov_record_key(transform)
                    if key in seen_change_keys:
                        continue
                    seen_change_keys.add(key)
                    base_matrix = sample_maps[0].get(key)
                    if base_matrix is None:
                        continue
                    for compare_map in sample_maps[1:]:
                        matrix = compare_map.get(key)
                        if matrix is None:
                            continue
                        if any(
                            abs(float(base_matrix[row][col]) - float(matrix[row][col])) > 1e-6
                            for row in range(4) for col in range(4)
                        ):
                            visible_change = True
                            break
                    if visible_change:
                        break
                if not visible_change:
                    reasons.append("decoded tracks do not change a visible rigid instance or deforming bone")

            sample_rate, frame_count, total_part_samples = self._animation_glb_sample_plan()
            skin_node_samples = frame_count * sum(len(template.get("nodes") or []) for template in skin_templates)
            if frame_count > 12000 or total_part_samples > 500000 or skin_node_samples > 2500000:
                reasons.append(
                    f"baked animation would be too large ({frame_count:,} frames, "
                    f"{len(self.animation_render_items):,} parts, {skin_node_samples:,} skin-node samples)"
                )

            self.animation_export_sample_rate = sample_rate
            self.animation_export_eligible = not reasons
            self.animation_export_reason = "; ".join(reasons)
            self.animation_export_warnings = list(warnings)
            try:
                self.animation_export_glb_button.setVisible(self.animation_export_eligible)
                self.animation_export_glb_button.setEnabled(self.animation_export_eligible)
                if self.animation_export_eligible:
                    warning_text = ""
                    if warnings:
                        warning_text = "\n\nExport note: " + "; ".join(warnings) + "."
                    self.animation_export_glb_button.setToolTip(
                        f"Export this animation as GLB at {sample_rate:g} fps "
                        f"({frame_count:,} samples over {effective_duration:.3f} s). "
                        f"Rigid transforms and fully resolved skins are supported; the current "
                        f"In place, duration limit, V/I and viewport-box visibility states are honoured."
                        f"{warning_text}"
                    )
                else:
                    self.animation_export_glb_button.setToolTip(
                        "Animated GLB is hidden because the resolved preview hierarchy is not structurally exportable: " + self.animation_export_reason
                    )
            except Exception:
                pass
            self._animation_refresh_export_status_note()

        def _animation_export_animated_glb(self) -> None:
            if not self.animation_export_eligible or not self.animation_clip_record:
                return
            folder = QFileDialog.getExistingDirectory(
                self,
                "Choose Animated GLB export folder",
                self.last_export_folder or "",
            )
            if not folder:
                return
            self.last_export_folder = str(folder)
            clip_rec = self.animation_clip_record
            clip_name = str(getattr(clip_rec, "name", "AnimationClip") or "AnimationClip")
            # Prefer the user's external comment for the exported filename.  Many
            # Unity projects contain dozens of generically named clips such as
            # "Scene", while the comment is often the useful identification
            # (for example "March Hare sitting down").  Only the first non-empty
            # line is used so a longer research note does not become a filename.
            comment_label = ""
            try:
                raw_comment = str(self.comment_store.get(clip_rec) or "")
                for comment_line in raw_comment.splitlines():
                    comment_line = re.sub(r"\s+", " ", comment_line).strip()
                    if comment_line:
                        comment_label = comment_line
                        break
            except Exception:
                comment_label = ""
            export_name = comment_label or clip_name
            export_warnings = list(getattr(self, "animation_export_warnings", []) or [])
            in_place = bool(self.animation_in_place_check.isChecked())
            sample_rate, export_times = self._animation_glb_sample_times()
            frame_count = len(export_times)
            duration = self._animation_effective_duration()
            full_duration = self._animation_full_duration()
            uv_channel = int(getattr(getattr(self, "preview_3d", None), "uv_channel", 0) or 0)
            ground_axis = self._current_ground_up_axis()

            self._show_export_work_notice(f"Preparing animated GLB — {clip_name}…")
            result = None
            export_error = None
            succeeded = False
            try:
                records = []
                item_rows = []
                seen = set()
                source_items = list(self.animation_render_items or [])
                visible_item_indices = None
                try:
                    visible_item_indices = self.preview_3d.visible_group_item_indices()
                except Exception:
                    visible_item_indices = None
                if visible_item_indices is None:
                    indexed_items = list(enumerate(source_items))
                    hidden_export_count = 0
                else:
                    indexed_items = [
                        (index, item) for index, item in enumerate(source_items)
                        if index in visible_item_indices
                    ]
                    hidden_export_count = max(0, len(source_items) - len(indexed_items))
                all_items = [item for _source_index, item in indexed_items]
                for item_index, item in enumerate(all_items, start=1):
                    if not isinstance(item, dict):
                        continue
                    rec = item.get("record")
                    tr = item.get("transform")
                    if rec is None or tr is None:
                        continue
                    key = (
                        str(getattr(rec, "source_name", "") or ""),
                        str(getattr(rec, "type_name", "") or ""),
                        getattr(rec, "path_id", id(rec)),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    self._update_export_work_notice(
                        f"Resolving materials and textures {item_index}/{len(all_items)} — "
                        f"{getattr(rec, 'name', 'Object')}"
                    )
                    self._hydrate_object_external_render_assets(rec)
                    records.append(rec)
                    item_rows.append((key, rec, tr))
                    if item_index % 3 == 0:
                        self._pump_loading_events(20)

                if not records:
                    raise RuntimeError("No stable render instances were available for export.")

                descriptor_by_record_key = {}
                for desc in self.animation_skinning_descriptors or []:
                    desc_record = desc.get("record") if isinstance(desc, dict) else None
                    if desc_record is None:
                        continue
                    desc_key = (
                        str(getattr(desc_record, "source_name", "") or ""),
                        str(getattr(desc_record, "type_name", "") or ""),
                        getattr(desc_record, "path_id", id(desc_record)),
                    )
                    descriptor_by_record_key[desc_key] = desc

                skin_templates_by_record = {}
                for key, _rec, _tr in item_rows:
                    desc = descriptor_by_record_key.get(key)
                    if desc is None:
                        continue
                    template, reason = self._animation_skin_export_template(desc)
                    if template is None:
                        raise RuntimeError(reason or "A skinned renderer could not be represented as glTF.")
                    skin_templates_by_record[key] = template

                def write_animated(report):
                    report(
                        f"Baking {frame_count:,} animation samples at {sample_rate:g} fps "
                        f"for {len(item_rows):,} rigid render instance(s)…"
                    )
                    times = list(export_times)

                    matrices_by_record = {key: [] for key, _rec, _tr in item_rows}
                    skin_node_matrices = {
                        key: [[] for _node in (template.get("nodes") or [])]
                        for key, template in skin_templates_by_record.items()
                    }
                    all_skin_transforms = []
                    seen_skin_transform_keys = set()
                    for template in skin_templates_by_record.values():
                        for node in template.get("nodes") or []:
                            transform_rec = node.get("transform")
                            if transform_rec is None:
                                continue
                            transform_key = self._ov_record_key(transform_rec)
                            if transform_key in seen_skin_transform_keys:
                                continue
                            seen_skin_transform_keys.add(transform_key)
                            all_skin_transforms.append(transform_rec)

                    report_step = max(1, frame_count // 12)
                    for frame_index, sample_time in enumerate(times):
                        matrix_map = self._animation_matrix_map_for_time(sample_time, in_place=in_place)
                        local_matrix_map = self._animation_local_matrix_map_for_time(
                            sample_time,
                            all_skin_transforms,
                            in_place=in_place,
                        ) if all_skin_transforms else {}
                        for key, _rec, transform_rec in item_rows:
                            transform_key = self._ov_record_key(transform_rec)
                            matrix = matrix_map.get(transform_key)
                            if matrix is None:
                                matrix = self._ov_mat_identity()
                            matrices_by_record[key].append(matrix)
                        for key, template in skin_templates_by_record.items():
                            rows_by_node = skin_node_matrices[key]
                            for node_index, node in enumerate(template.get("nodes") or []):
                                transform_rec = node.get("transform")
                                matrix = local_matrix_map.get(self._ov_record_key(transform_rec)) if transform_rec is not None else None
                                rows_by_node[node_index].append(matrix or self._ov_mat_identity())
                        if frame_index % report_step == 0 or frame_index == frame_count - 1:
                            report(f"Baking animation pose {frame_index + 1:,}/{frame_count:,}…")

                    static_matrices = {key: rows[0] for key, rows in matrices_by_record.items() if rows}
                    animation_payloads = {
                        key: {"times": times, "matrices": rows}
                        for key, rows in matrices_by_record.items()
                        if len(rows) == len(times) and key not in skin_templates_by_record
                    }
                    skin_payloads = {}
                    for key, template in skin_templates_by_record.items():
                        export_nodes = []
                        rows_by_node = skin_node_matrices.get(key) or []
                        for node_index, node in enumerate(template.get("nodes") or []):
                            export_nodes.append({
                                "name": node.get("name"),
                                "path_id": node.get("path_id"),
                                "parent_index": node.get("parent_index", -1),
                                "matrices": rows_by_node[node_index] if node_index < len(rows_by_node) else [],
                            })
                        skin_payloads[key] = {
                            "times": times,
                            "nodes": export_nodes,
                            "joints": list(template.get("joints") or []),
                            "renderer_node_index": int(template.get("renderer_node_index", -1)),
                            "root_bone_node_index": int(template.get("root_bone_node_index", -1)),
                            "bind_poses": list(template.get("bind_poses") or []),
                            "weights": list(template.get("weights") or []),
                            "mesh_record": template.get("mesh_record"),
                            "name": str(template.get("name") or "Skinned mesh"),
                        }
                    label = export_name + ("__in_place" if in_place else "")
                    if in_place and duration < full_duration - 1e-6:
                        duration_token = f"{duration:.3f}".rstrip("0").rstrip(".").replace(".", "p")
                        label += f"__{duration_token}s"
                    report("Writing meshes, materials, textures, skins and glTF animation channels…")
                    raw = export_multi_object_glb_records(
                        records,
                        folder,
                        self.bundle_index,
                        self.asset_graph,
                        uv_channel=uv_channel,
                        name_override=label,
                        record_matrices=static_matrices,
                        allow_single=True,
                        record_animation_matrices=animation_payloads,
                        record_skin_payloads=skin_payloads,
                        animation_name=clip_name,
                    )
                    report(f"Applying {ground_axis} export basis…")
                    return apply_ground_axis_to_export_result(raw, ground_axis)

                result = self._run_export_task_responsive(
                    f"Exporting animated GLB — {clip_name}…",
                    write_animated,
                )
                succeeded = bool(result is not None and getattr(result, "ok", False))
            except Exception as exc:
                export_error = exc
            finally:
                self._hide_export_work_notice(success=succeeded)

            if export_error is not None:
                QMessageBox.warning(
                    self,
                    "Animated GLB export failed",
                    f"Could not export the selected animation.\n\n{export_error}",
                )
                return

            if result is not None and getattr(result, "ok", False) and getattr(result, "path", None):
                warning_summary = ""
                if export_warnings:
                    warning_summary = (
                        "\nExport notes:\n- " + "\n- ".join(export_warnings) + "\n"
                    )
                QMessageBox.information(
                    self,
                    "Animated GLB exported",
                    f"Exported the selected animation to:\n{result.path}\n\n"
                    f"Filename source: {'external comment' if comment_label else 'AnimationClip name'}.\n"
                    f"Existing files are never overwritten; UBE appends _1, _2, and so on.\n"
                    f"Baked at {sample_rate:g} fps over {duration:.3f} s"
                    f" of the {full_duration:.3f} s source clip. "
                    f"In-place mode: {'on' if in_place else 'off'}.\n"
                    f"Preview-hidden/removed parts excluded: {hidden_export_count}.\n"
                    f"{warning_summary}"
                    "The export uses the same resolved render hierarchy and sampled pose data as the working preview.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Animated GLB export failed",
                    str(getattr(result, "message", "Could not write the animated GLB.")),
                )

        def preview_animation_clip(self, rec) -> bool:
            clip_name = str(getattr(rec, "name", "AnimationClip") or "AnimationClip")
            self._show_animation_work_notice(clip_name)
            success = False
            try:
                success = bool(self._preview_animation_clip_impl(rec))
                return success
            finally:
                self._hide_animation_work_notice(success=success)

        def _preview_animation_clip_impl(self, rec) -> bool:
            self._animation_leave_preview()
            self.animation_controls.setVisible(True)
            self.animation_play_button.setEnabled(False)
            self.animation_reset_button.setEnabled(False)
            self.animation_loop_check.setEnabled(False)
            self.animation_in_place_check.setEnabled(False)
            self.animation_speed_combo.setEnabled(False)
            self.animation_duration_limit_spin.setEnabled(False)
            self.animation_duration_full_button.setEnabled(False)
            self.animation_slider.setEnabled(False)
            self.animation_clip_record = rec
            self._update_animation_work_notice("Reading AnimationClip data…")
            data = self._ov_read(rec)
            self.animation_clip_data = data
            if data is None:
                self.animation_status_label.setText("AnimationClip could not be decoded.")
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False

            self._update_animation_work_notice("Decoding animation curves and binding channels…")
            tracks = self._animation_curve_tracks_from_clip(
                data, rec, progress_callback=self._update_animation_work_notice
            )
            if not tracks:
                streamed_error = str((self.animation_streamed_meta or {}).get("error") or "").strip()
                if streamed_error:
                    message = f"Streamed animation data was found but could not be decoded: {streamed_error}."
                else:
                    message = (
                        "No playable position/rotation/scale curves are exposed. "
                        "This clip may contain humanoid, visibility, blend-shape, material, or other property animation."
                    )
                self.animation_status_label.setText(message)
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False

            self._update_animation_work_notice(
                f"Resolving {len(tracks):,} animation track(s) against the Transform hierarchy…"
            )
            root_tr, targets, unresolved = self._animation_resolve_root_and_targets(tracks, rec)
            resolved_owner_go = self._ov_gameobject_for_transform(root_tr) if root_tr is not None else None
            resolved_owner_summary = "resolved from the AnimationClip target hierarchy"
            if root_tr is None:
                self.animation_status_label.setText(
                    f"Transform curves found ({len(tracks)}), but their hierarchy paths could not be resolved in the loaded bundle/project."
                )
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False

            matched_tracks = 0
            for track in tracks:
                target = targets.get(str(track.get("path") or ""))
                track["target_transform"] = target
                if target is not None:
                    matched_tracks += 1
            tracks = [track for track in tracks if track.get("target_transform") is not None]
            if not tracks:
                self.animation_status_label.setText("Transform paths were discovered, but no playable curve target could be selected.")
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False

            self._update_animation_work_notice("Finding the authoritative animation owner and render branch…")

            # v2.2l: Legacy clips are owned by an Animation component rather
            # than an AnimatorController.  Resolve through that explicit owner
            # before accepting bundle-global duplicate path matches.
            legacy_owned_items = []
            legacy_root, legacy_targets, legacy_items, legacy_summary = (
                self._animation_legacy_preview_context(rec, tracks)
            )
            if legacy_root is not None and legacy_items:
                root_tr = legacy_root
                targets.update(legacy_targets)
                for track in tracks:
                    path = str(track.get("path") or "")
                    if path in legacy_targets:
                        track["target_transform"] = legacy_targets[path]
                tracks = [track for track in tracks if track.get("target_transform") is not None]
                legacy_owned_items = legacy_items
                self.animation_controller_context_summary = legacy_summary
                resolved_owner_go = self._ov_gameobject_for_transform(legacy_root)
                resolved_owner_summary = legacy_summary
                unresolved = [
                    path for path in unresolved
                    if path not in legacy_targets
                ]

            # v2.2m/v2.2n: some WAM Legacy clip copies are not directly
            # referenced by a serialized Animation component in this bundle.
            # First use a numbered/variant-aware target-first owner lookup (for
            # example CupSheepAnim (4)); then fall back to the original longest
            # clip-name prefix owner lookup (for example flagStopper_pink).
            if not legacy_owned_items:
                is_legacy_clip = bool(self._ov_get(data, "m_Legacy", "legacy", default=False))
                clip_name_low = str(getattr(rec, "name", "") or "").lower()
                if is_legacy_clip or "legacy" in clip_name_low:
                    variant_root, variant_targets, variant_items, variant_summary = (
                        self._animation_variant_named_owner_preview_context(rec, tracks)
                    )
                    if variant_root is not None and variant_items:
                        root_tr = variant_root
                        targets.update(variant_targets)
                        for track in tracks:
                            path = str(track.get("path") or "")
                            if path in variant_targets:
                                track["target_transform"] = variant_targets[path]
                        tracks = [track for track in tracks if track.get("target_transform") is not None]
                        legacy_owned_items = variant_items
                        self.animation_controller_context_summary = variant_summary
                        resolved_owner_go = self._ov_gameobject_for_transform(variant_root)
                        resolved_owner_summary = variant_summary
                        unresolved = [path for path in unresolved if path not in variant_targets]

            if not legacy_owned_items:
                is_legacy_clip = bool(self._ov_get(data, "m_Legacy", "legacy", default=False))
                clip_name_low = str(getattr(rec, "name", "") or "").lower()
                if is_legacy_clip or "legacy" in clip_name_low:
                    named_root, named_targets, named_items, named_summary = (
                        self._animation_named_owner_preview_context(rec, tracks)
                    )
                    if named_root is not None and named_items:
                        root_tr = named_root
                        targets.update(named_targets)
                        for track in tracks:
                            path = str(track.get("path") or "")
                            if path in named_targets:
                                track["target_transform"] = named_targets[path]
                        tracks = [track for track in tracks if track.get("target_transform") is not None]
                        legacy_owned_items = named_items
                        self.animation_controller_context_summary = named_summary
                        resolved_owner_go = self._ov_gameobject_for_transform(named_root)
                        resolved_owner_summary = named_summary
                        unresolved = [path for path in unresolved if path not in named_targets]

            root_go = self._ov_gameobject_for_transform(root_tr)
            if root_go is None:
                self.animation_status_label.setText("The animation root Transform has no resolvable GameObject.")
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False

            # v2.2j: the resolved binding root can be a transform-only
            # skeleton/helper branch. The visible SkinnedMeshRenderer may be a
            # sibling beneath the next character/object owner. Promote only the
            # preview root to the nearest renderable ancestor; curve targets stay
            # exactly as resolved.
            self._update_animation_work_notice("Collecting coherent renderable descendants…")
            if legacy_owned_items:
                preview_root_tr = root_tr
                items = legacy_owned_items
                promoted_steps = 0
            else:
                preview_root_tr, items, promoted_steps = self._animation_promote_root_to_renderable_owner(
                    root_tr,
                    max_parent_steps=12,
                    render_limit=240,
                    render_depth=16,
                )

            # v2.2k: when binding hashes identify a skeleton/property family but
            # the selected branch has no renderer, follow the authoritative
            # AnimationClip -> AnimatorController -> Animator wiring.
            if not items:
                controller_root, controller_targets, controller_items, controller_summary = (
                    self._animation_controller_preview_context(rec, tracks)
                )
                if controller_root is not None and controller_items:
                    preview_root_tr = controller_root
                    items = controller_items
                    targets.update(controller_targets)
                    for track in tracks:
                        path = str(track.get("path") or "")
                        if path in controller_targets:
                            track["target_transform"] = controller_targets[path]
                    self.animation_controller_context_summary = controller_summary
                    resolved_owner_go = self._ov_gameobject_for_transform(controller_root)
                    resolved_owner_summary = controller_summary
                    promoted_steps = 0

            # Never regress below the known-good v2.2h behaviour. If richer
            # context cannot find a renderable owner, retry playable tracks only.
            if not items and getattr(self, "animation_binding_hint_paths", None):
                legacy_root, legacy_targets, legacy_unresolved = self._animation_resolve_root_and_targets(
                    tracks,
                    rec,
                    use_binding_hints=False,
                )
                if legacy_root is not None:
                    legacy_go = self._ov_gameobject_for_transform(legacy_root)
                    legacy_items = self._ov_renderable_items_from_selection(
                        legacy_go,
                        limit=240,
                        max_depth=16,
                        include_root=True,
                    ) if legacy_go is not None else []
                    if legacy_items:
                        preview_root_tr = legacy_root
                        items = legacy_items
                        targets.update(legacy_targets)
                        for track in tracks:
                            path = str(track.get("path") or "")
                            if path in legacy_targets:
                                track["target_transform"] = legacy_targets[path]
                        unresolved = legacy_unresolved
                        self.animation_controller_context_summary = (
                            "playable-track fallback used; property-binding owner unresolved"
                        )
                        resolved_owner_go = self._ov_gameobject_for_transform(legacy_root)
                        resolved_owner_summary = self.animation_controller_context_summary
                        promoted_steps = 0

            if not items:
                # Retain the correctly resolved transform owner even when the
                # common bundle contains only animation drivers and the visual
                # geometry lives in a scene bundle/runtime linkage.
                owner_for_link = resolved_owner_go or self._ov_gameobject_for_transform(root_tr)
                if owner_for_link is not None:
                    self.animation_owner_gameobject = owner_for_link
                    self.animation_owner_resolution_summary = str(resolved_owner_summary or "resolved animation owner")
                    self.animation_owner_clip_key = self._ov_record_key(rec)
                guard = str(getattr(self, "animation_root_promotion_guard_summary", "") or "").strip()
                if guard:
                    message = (
                        f"Animation paths matched, but {guard}. "
                        "UBE did not attach neighbouring animation geometry. The visible object is likely supplied by a scene bundle, constraint, or runtime script."
                    )
                else:
                    message = (
                        "Animation paths matched, but neither the binding root, Animator owner, nor nearby coherent hierarchy contains renderable mesh descendants."
                    )
                self.animation_status_label.setText(message)
                self.animation_play_button.setEnabled(False)
                self.animation_reset_button.setEnabled(False)
                self.preview_relationship_flow(rec)
                return False
            root_tr = preview_root_tr
            root_go = self._ov_gameobject_for_transform(root_tr)

            # v2.3d: retain the authoritative animation owner separately from
            # any render-only parent promotion.  The inspector can then expose
            # a direct clickable owner link instead of forcing a manual search.
            if resolved_owner_go is None:
                resolved_owner_go = root_go
            self.animation_owner_gameobject = resolved_owner_go
            self.animation_owner_resolution_summary = str(resolved_owner_summary or "resolved animation owner")
            self.animation_owner_clip_key = self._ov_record_key(rec)

            # v2.3a: resolve external materials/textures before the animation
            # viewer creates its material cache.  Previously the first animation
            # preview could be grey until the user selected a Material, because
            # Material preview was the only path that hydrated an external
            # _ColorMap/_BaseMap dependency.
            hydrated_animation_objects = 0
            hydrated_animation_bundles = 0
            try:
                hydrated_animation_objects, hydrated_animation_bundles = (
                    self._hydrate_animation_render_assets(
                        items, progress_callback=self._update_animation_work_notice
                    )
                )
            except Exception:
                hydrated_animation_objects = 0
                hydrated_animation_bundles = 0

            # v2.3x: imported "all variants" animation owners can contain several
            # numbered complete skinned renderers at exactly the same transform.
            # The game chooses one at runtime; drawing every alternative causes
            # z-fighting, mixed atlas colours and an unreadable composite.  Detect
            # only the strict overlapping-variant pattern and start with one
            # renderer visible.  The existing I hotkey still cycles every variant.
            self.animation_render_variant_info = self._animation_overlapping_variant_set(items) or {}

            if promoted_steps > 0:
                promoted_name = str(getattr(root_go, "name", "renderable owner") or "renderable owner")
                self.animation_root_promotion_summary = (
                    f"preview root promoted {promoted_steps} level(s) to {promoted_name}"
                )

            self._update_animation_work_notice(
                f"Preparing {len(items):,} render instance(s) and animated Transform targets…"
            )
            transform_by_key = {}
            for item in items:
                transform = item.get("transform")
                if transform is not None:
                    key = self._ov_record_key(transform)
                    item["transform_key"] = key
                    transform_by_key[key] = transform
            # Bone targets are often transform-only and therefore absent from
            # the render-item list. Keep every matched curve target available
            # to the pose evaluator before skinning is prepared.
            for track in tracks:
                target = track.get("target_transform")
                if target is not None:
                    transform_by_key[self._ov_record_key(target)] = target

            duration = max((key[0] for track in tracks for key in track.get("keys", [])), default=0.0)
            self.animation_tracks = tracks
            self.animation_duration = max(0.0, float(duration))
            self.animation_current_time = 0.0
            self.animation_playback_time = 0.0
            self.animation_root_transform = root_tr
            self.animation_render_items = items
            self.animation_transform_by_key = transform_by_key
            self.animation_pose_is_default = True
            self._animation_configure_root_motion(tracks)
            self._animation_configure_duration_limit()

            self.preview_stack.setCurrentWidget(self.preview_3d)
            uv_channel = int(getattr(self.preview_3d, "uv_channel", 0) or 0)
            self._update_animation_work_notice(
                f"Building preview geometry from {len(items):,} render instance(s)…"
            )
            self.preview_3d.load_object_group_records(
                f"Animation: {getattr(rec, 'name', 'Clip')}",
                items,
                self.bundle_index,
                self.asset_graph,
                uv_channel=uv_channel,
                preview_mode="group",
                default_solo_child_index=(
                    self.animation_render_variant_info.get("default_index")
                    if self.animation_render_variant_info else None
                ),
                variant_context_label=(
                    f"variant 1/{int(self.animation_render_variant_info.get('count') or 0)} shown; I cycles alternatives"
                    if self.animation_render_variant_info else ""
                ),
                progress_callback=self._update_animation_work_notice,
            )
            self._update_animation_work_notice("Preparing skinning and constraint data…")
            skinned_count, unsupported_skin_count = self._animation_prepare_skinning(
                items, progress_callback=self._update_animation_work_notice
            )
            constraint_count, unsupported_constraint_count = self._animation_prepare_constraints()
            self._animation_configure_in_place_world_anchor()
            self._animation_configure_preview_geometry_anchor()

            path_count = len({str(track.get("path") or "<root>") for track in tracks})
            unresolved_text = f" • {len(unresolved)} unresolved path(s)" if unresolved else ""
            skin_text = ""
            if skinned_count:
                skin_text = f" • CPU skinning: {skinned_count} renderer(s)"
            if unsupported_skin_count:
                skin_text += f" • {unsupported_skin_count} skinned renderer(s) static"
            constraint_text = ""
            if constraint_count:
                constraint_text = f" • constraints: {constraint_count}"
            if unsupported_constraint_count:
                constraint_text += f" ({unsupported_constraint_count} limited)"
            target_instance_text = ""
            if getattr(self, "animation_target_instance_summary", ""):
                target_instance_text = f" • {self.animation_target_instance_summary}"
            variant_text = ""
            if getattr(self, "animation_render_variant_info", None):
                variant_count = int(self.animation_render_variant_info.get("count") or 0)
                if variant_count > 1:
                    variant_text = f" • {variant_count} overlapping render alternatives; one shown (I cycles)"
            streamed_text = ""
            streamed_meta = self.animation_streamed_meta or {}
            streamed_channels = int(streamed_meta.get("declared_curve_count") or 0)
            streamed_frames = int(streamed_meta.get("playable_frame_count") or 0)
            if streamed_channels:
                streamed_text = f" • streamed curves: {streamed_channels}"
                if streamed_frames:
                    streamed_text += f" / {streamed_frames} frame record(s)"
            curve_note = str(streamed_meta.get("curve_count_note") or "").strip()
            if curve_note:
                streamed_text += f" ({curve_note})"
            root_text = f" • {self.animation_root_motion_summary}" if self.animation_root_motion_summary else ""
            binding_context_text = (
                f" • {self.animation_binding_hint_summary}"
                if getattr(self, "animation_binding_hint_summary", "") else ""
            )
            promotion_text = (
                f" • {self.animation_root_promotion_summary}"
                if getattr(self, "animation_root_promotion_summary", "") else ""
            )
            controller_context_text = (
                f" • {self.animation_controller_context_summary}"
                if getattr(self, "animation_controller_context_summary", "") else ""
            )
            external_colour_text = ""
            if hydrated_animation_bundles:
                external_colour_text = (
                    f" • loaded {hydrated_animation_bundles} external visual dependency bundle(s)"
                )

            runtime_linkage_text = ""
            runtime_diag = {}
            try:
                runtime_diag = _animation_runtime_linkage_diagnostic(rec, data, self.bundle_index) or {}
                if runtime_diag.get("warning"):
                    runtime_linkage_text = f" • {runtime_diag.get('status', 'runtime visual linkage incomplete')}"
            except Exception:
                runtime_diag = {}
                runtime_linkage_text = ""

            self.animation_export_context = {
                "unresolved": list(unresolved or []),
                "skinned_count": skinned_count,
                "unsupported_skin_count": unsupported_skin_count,
                "constraint_count": constraint_count,
                "unsupported_constraint_count": unsupported_constraint_count,
                "runtime_warning": bool(runtime_diag.get("warning")),
            }
            self.animation_status_base_text = (
                f"Animation preview: {matched_tracks} curve(s), {path_count} target path(s), "
                f"{len(items)} render instance(s) • frame-accurate authored sampling • linear curve interpolation{streamed_text}{skin_text}{constraint_text}{target_instance_text}{variant_text}{binding_context_text}{promotion_text}{controller_context_text}{external_colour_text}{runtime_linkage_text}{root_text}{unresolved_text}"
            )
            self._update_animation_work_notice("Checking Animated GLB export compatibility…")
            self._animation_configure_glb_export(
                **self.animation_export_context,
                progress_callback=self._update_animation_work_notice,
            )
            self._animation_refresh_export_status_note()
            self.animation_slider_updating = True
            try:
                self.animation_slider.setValue(0)
            finally:
                self.animation_slider_updating = False
            self.animation_play_button.setEnabled(self.animation_duration > 0.0)
            self.animation_reset_button.setEnabled(True)
            self.animation_loop_check.setEnabled(True)
            self.animation_in_place_check.setEnabled(bool(self.animation_root_lock_keys))
            self.animation_duration_limit_spin.setEnabled(
                bool(self.animation_root_lock_keys and self.animation_in_place_check.isChecked())
            )
            self.animation_duration_full_button.setEnabled(
                bool(self.animation_root_lock_keys and self.animation_in_place_check.isChecked())
            )
            self.animation_speed_combo.setEnabled(True)
            self.animation_slider.setEnabled(self.animation_duration > 0.0)

            self._update_animation_work_notice("Sampling and framing the first rendered pose…")

            # The holding view is the clip's sampled first frame, not the raw
            # serialized/rest hierarchy.  Reset pose now returns to this same
            # visible frame-zero result, because environmental rigs can contain
            # extreme scene-placement data in their serialized rest transforms.
            self._animation_apply_time(0.0, update_slider=False)
            try:
                self.preview_3d.reframe_current_group_pose(reset_distance=True)
            except Exception:
                pass
            self._animation_capture_preview_geometry_anchor()
            self._animation_refresh_time_label("0.000")
            # The stage notice temporarily occupies the animation status line;
            # restore the complete ready/export summary before hiding the dialog.
            self._animation_refresh_export_status_note()
            try:
                self.statusBar().showMessage(
                    (
                        "AnimationClip first frame ready — one overlapping render variant shown; press I to cycle alternatives"
                        if self.animation_render_variant_info
                        else "AnimationClip first frame ready — Play, scrub, loop, change speed, or reset to frame zero"
                    )
                    + f" • prepared in {self._animation_work_elapsed_seconds():.1f} s • Space: play/pause",
                    7000,
                )
            except Exception:
                pass

            # The inspector is initially drawn before the preview resolver runs.
            # Rebuild it once so the newly resolved owner appears immediately as
            # a clickable Quick Link, without adding another history entry.
            try:
                if getattr(self, "_current_inspector_record_key", None) == self._ov_record_key(rec):
                    plain = str(getattr(self, "_current_inspector_plain", "") or "")
                else:
                    plain = describe_record(rec, self.bundle_index, self.asset_graph, include_relationships=False)
                self.info.setHtml(self._record_html(plain, rec))
            except Exception:
                pass
            return True

        def on_select(self):
            items = self.tree.selectedItems()
            self.selected_record = None
            self.export_button.setText("Export Selected Asset...")
            self.export_button.setEnabled(False)
            if not items:
                return

            data = items[0].data(0, Qt.UserRole)
            if isinstance(data, tuple):
                if data[0] in ("bundle_path", "serialized_asset_path"):
                    # Load bundle / serialized asset source from a project-style node.
                    self.load_path(Path(data[1]), from_project=True)
                    return
                if data[0] == "asset_type":
                    # Asset-type group headings are tree controls, not assets.
                    # Preserve the established behaviour of showing the bundle
                    # dashboard when a heading is selected.
                    if self.bundle_index:
                        self.show_bundle_info()
                    return

            if not data:
                if self.bundle_index:
                    self.show_bundle_info()
                return

            rec = data
            if getattr(rec, "type_name", "") != "AudioClip":
                self.stop_current_audio()
            if getattr(rec, "type_name", "") != "AnimationClip":
                self._animation_leave_preview()
            self.selected_record = rec
            self.show_record_in_inspector(rec, push_history=not self._suppress_history)
            self.export_button.setEnabled(True)
            if self.export_supported_for_record(rec):
                self.export_button.setText("Export Selected Asset...")
            else:
                self.export_button.setText("Export Inspector Report...")

            multi_records = self._selected_multi_preview_records()
            if len(multi_records) >= 2:
                self.export_button.setEnabled(True)
                self.export_button.setText(f"Export {min(len(multi_records), 4)} Selected as One...")
                if self.preview_multi_selection_records(multi_records, active_rec=rec):
                    return

            if rec.type_name == "Texture2D":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_texture(rec)
            elif rec.type_name == "Texture2DArray":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview.setText(
                    f"Texture Array\n\n{rec.name}\n\n"
                    "This is a Texture2DArray, not a single PNG.\n"
                    "Inspect the right panel for slice/depth metadata.\n"
                    "Meshes may use this through _BaseMap plus _TextureIndex."
                )
            elif rec.type_name == "Cubemap":
                self.preview_cubemap(rec)
            elif rec.type_name == "Material":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_material(rec)
            elif rec.type_name == "Shader":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_shader(rec)
            elif rec.type_name == "AudioClip":
                self.preview_stack.setCurrentWidget(self.audio_widget)
                self.preview_audio(rec)
            elif rec.type_name == "AnimationClip":
                self.preview_animation_clip(rec)
            elif rec.type_name == "Sprite":
                self._hydrate_sprite_external_assets(rec)
                self.preview_sprite(rec)
            elif rec.type_name == "SpriteRenderer":
                self._hydrate_sprite_external_assets(rec)
                self.preview_sprite_renderer(rec)
            elif rec.type_name == "Camera":
                self.preview_camera(rec)
            elif rec.type_name == "Light":
                self.preview_light(rec)
            elif rec.type_name == "ReflectionProbe":
                self.preview_reflection_probe(rec)
            elif rec.type_name == "LODGroup":
                self.preview_lod_group(rec)
            elif rec.type_name in ("ParticleSystem", "ParticleSystemRenderer"):
                self.preview_particle_system(rec)
            elif rec.type_name == "BoxCollider":
                self.preview_box_collider(rec)
            elif rec.type_name == "SpriteMask":
                self.preview_sprite_mask(rec)
            elif rec.type_name == "SphereCollider":
                self.preview_sphere_collider(rec)
            elif rec.type_name == "CapsuleCollider":
                self.preview_capsule_collider(rec)
            elif rec.type_name == "MeshCollider":
                self.preview_mesh_collider(rec)
            elif rec.type_name == "Avatar":
                self.preview_avatar(rec)
            elif rec.type_name in ("Font", "TMP_FontAsset"):
                self.preview_font(rec)
            elif rec.type_name in ("LineRenderer", "TrailRenderer", "Rigidbody", "PhysicMaterial", "TextAsset", "PlayableDirector"):
                self.preview_18t_symbolic(rec)
            elif rec.type_name in ("NavMeshData", "NavMeshSettings", "NavMeshProjectSettings"):
                self.preview_navmesh(rec)
            elif rec.type_name == "RectTransform":
                self.preview_rect_transform(rec)
            elif rec.type_name in self.object_view_types():
                self.preview_object_attached_mesh(rec)
            elif rec.type_name == "Mesh":
                self.preview_stack.setCurrentWidget(self.preview_3d)
                self.preview_3d.load_mesh_record(rec, self.bundle_index, self.asset_graph)
            elif rec.type_name in self.relationship_flow_auto_types():
                self.preview_relationship_flow(rec)
            else:
                self.preview_relationship_flow(rec)

        def show_record_in_inspector(self, rec, push_history: bool = True):
            if rec is None:
                return
            if push_history:
                self.push_history(rec.path_id)
                self.record_selection_history(rec)
            # Allow a small number of lazy single-PathID index lookups while rendering this inspector.
            # This catches useful cases like shared URP shaders/sprites in OBB bundles without expanding the
            # multi-million-object project index.
            self._pathid_lookup_render_budget = 8
            if getattr(rec, "type_name", "") in ("Sprite", "SpriteRenderer", "SpriteMask"):
                self._hydrate_sprite_external_assets(rec)
            plain = describe_record(rec, self.bundle_index, self.asset_graph, include_relationships=False)
            self._current_inspector_record_key = self._ov_record_key(rec)
            self._current_inspector_plain = plain
            html = self._record_html(plain, rec)
            self.info.setHtml(html)

            
        def _split_inspector_sections(self, plain: str):
            """Split the plain inspector text into a small header plus visual sections.

            This keeps the core inspectors simple, but lets the UI present the
            information as readable blocks. Section headings can be collapsed by
            clicking them, a little like document headings in Word.
            """
            raw_lines = plain.splitlines()
            header = []
            sections = []
            current_title = None
            current_lines = []

            def is_section_heading(line: str) -> bool:
                if not line or line.startswith(" "):
                    return False
                # Detail rows usually contain a colon. Headings normally don't.
                if ":" in line:
                    return False
                return line[0] in "🧠🖼🎨🧊📦📐📊🧩🔗⚙🏷🔁🎲↔👁🧍📉💡🪞✨🌗🧾🔤🌳🧭🎧🔊▶📍📈🎛🎚📸⏸🔀"

            for line in raw_lines:
                if current_title is None and not is_section_heading(line):
                    header.append(line)
                    continue
                if is_section_heading(line):
                    if current_title is not None:
                        sections.append((current_title, current_lines))
                    current_title = line
                    current_lines = []
                else:
                    current_lines.append(line)
            if current_title is not None:
                sections.append((current_title, current_lines))
            return header, sections

        def _record_html(self, plain: str, rec) -> str:
            header, sections = self._split_inspector_sections(plain)
            body = [
                "<html><body style='font-family: Segoe UI, Arial, sans-serif; font-size: 10.5pt; color:#eee;'>",
                "<style>",
                "a { color:#8ecbff; text-decoration:none; }",
                ".card { border:1px solid #404040; border-radius:7px; margin:8px 0; padding:8px 10px; background:#252525; }",
                ".head { font-weight:600; color:#ffffff; margin-bottom:5px; }",
                ".collapsed { color:#a8a8a8; font-style:italic; padding:2px 0; }",
                ".muted { color:#aaa; }",
                ".badge { display:inline-block; border:1px solid #555; border-radius:9px; padding:1px 6px; margin-left:4px; color:#ddd; background:#303030; font-size:9pt; }",
                ".atlasbox { color:#ffd56b; font-weight:600; }",
                ".external { color:#d9b36c; }",
                ".unresolved { color:#d99797; }",
                "pre { white-space:pre-wrap; font-family:'Segoe UI', Arial, sans-serif; margin:0; }",
                "</style>",
            ]

            if header:
                body.append("<div class='card'><pre>")
                body.append(escape("\n".join(header)).strip())
                body.append("</pre></div>")

            body.extend(self._external_comment_html(rec))
            body.extend(self._animation_owner_html(rec))
            body.extend(self._component_owner_html(rec))
            body.extend(self._preview_context_html(rec))

            for i, (title, lines) in enumerate(sections):
                key = (getattr(rec, "path_id", 0), i)
                collapsed = key in self.collapsed_inspector_sections
                arrow = "▶" if collapsed else "▼"
                body.append("<div class='card'>")
                body.append(
                    f"<div class='head'><a href='ube://toggle/{getattr(rec, 'path_id', 0)}/{i}' "
                    f"style='color:#ffffff'>{arrow} {escape(title)}</a></div>"
                )
                if collapsed:
                    body.append("<div class='collapsed'>Section collapsed</div>")
                else:
                    custom_components = None
                    if getattr(rec, "type_name", "") == "GameObject" and str(title).startswith("🧩 Components"):
                        custom_components = self._gameobject_components_html(rec)
                    if custom_components:
                        body.append(custom_components)
                    else:
                        text = "\n".join(lines).strip("\n")
                        if text:
                            body.append("<pre>")
                            body.append(self._inspector_text_html(text, rec))
                            body.append("</pre>")
                body.append("</div>")

            body.extend(self._object_hierarchy_html(rec))
            body.extend(self._texture_region_search_results_html(rec))
            body.extend(self._relationship_html(rec))
            body.append("</body></html>")
            return "".join(body)

        def _preview_context_html(self, rec) -> list[str]:
            """Small educational note explaining what the top preview is showing.

            Many Unity records are components rather than visible meshes.  UBE
            often previews the owning GameObject or a diagnostic diagram so the
            user still gets a useful visual.  This note makes that explicit for
            learners and avoids confusion when, for example, selecting a
            MonoBehaviour displays the hat/head/object it is attached to.
            """
            if rec is None:
                return []
            t = getattr(rec, "type_name", "")
            name = escape(str(getattr(rec, "name", "") or ""))
            notes: list[str] = []

            try:
                go_rec = self._ov_owning_gameobject(rec) if t != "GameObject" else rec
            except Exception:
                go_rec = None

            def go_link() -> str:
                if go_rec is not None:
                    return self._ov_asset_link(getattr(go_rec, "path_id", 0), "GameObject")
                return "<span class='muted'>owning GameObject not resolved</span>"

            if t == "MonoBehaviour":
                notes.append(f"<b>Preview source:</b> showing owning GameObject {go_link()}.")
                notes.append("MonoBehaviour/script components are not visible by themselves; they usually configure or control the object they are attached to.")
            elif t == "AudioSource":
                notes.append(f"<b>Preview source:</b> relationship wiring for owning GameObject {go_link()} and the assigned AudioClip.")
                notes.append("AudioSource is an invisible playback component. Open its Audio Clip reference to hear or export the actual sound.")
            elif t == "MeshFilter":
                notes.append(f"<b>Preview source:</b> showing the linked mesh for {go_link()} with sibling renderer/material context where UBE can resolve it.")
                notes.append("A MeshFilter stores the shape reference; a MeshRenderer beside it supplies the material and texture slots.")
            elif t in ("MeshRenderer", "SkinnedMeshRenderer"):
                notes.append(f"<b>Preview source:</b> showing the owning GameObject {go_link()} using this renderer's material slots.")
                notes.append("Renderer components are the draw setup; they are meaningful when paired with a MeshFilter or skinned mesh.")
            elif t == "Transform":
                notes.append(f"<b>Preview source:</b> showing the owning GameObject {go_link()} or its renderable child group when available.")
                notes.append("A Transform is position/rotation/scale data; it becomes visual only through attached or child renderers.")
            elif t == "GameObject":
                active_note = ""
                try:
                    data = self._ov_read(rec)
                    active = self._ov_get(data, "m_IsActive", "is_active", default=None) if data is not None else None
                    if active is not None and not bool(active):
                        active_note = " This saved object is inactive/disabled, but UBE still previews it so the mesh, material, and component setup can be inspected."
                except Exception:
                    active_note = ""
                notes.append("<b>Preview source:</b> showing this GameObject directly, or an assembled group if it is a render-only parent.")
                notes.append("A GameObject is a container of components; the visual result normally comes from its MeshFilter/Renderer, SkinnedMeshRenderer, SpriteRenderer, or child objects." + active_note)
            elif t == "LODGroup":
                notes.append(f"<b>Preview source:</b> diagnostic LOD chart/relationship view for {go_link()}.")
                notes.append("This is not Unity rendering the object; it explains which child renderers are used at different screen sizes.")
            elif t == "Light":
                notes.append("<b>Preview source:</b> symbolic light influence diagram.")
                notes.append("The viewer shows direction/range/cone/area shape, not the final Unity lighting result.")
            elif t in ("ReflectionProbe", "LightProbeGroup", "LightingSettings", "LightmapSettings"):
                notes.append("<b>Preview source:</b> symbolic lighting/probe diagnostic view where available.")
                notes.append("Probe and lightmap records usually store scene lighting data or bake setup rather than a directly visible model.")
            elif t in ("ParticleSystem", "ParticleSystemRenderer"):
                notes.append("<b>Preview source:</b> symbolic particle setup diagram.")
                notes.append("UBE shows emitter shape, material/render mode, and key settings; it does not simulate the live Unity particle effect.")
            elif t == "BoxCollider":
                notes.append(f"<b>Preview source:</b> collider shape diagram for {go_link()}.")
                notes.append("Colliders are physics/trigger volumes. The wire box explains the volume; it is not a rendered game mesh.")
            elif t in ("SphereCollider", "CapsuleCollider", "MeshCollider"):
                notes.append(f"<b>Preview source:</b> scaled collider shape visual for {go_link()}.")
                notes.append("Colliders are invisible physics/trigger volumes. The preview shows the local-space collision/detection shape, not the visible artwork.")
            elif t in ("Rigidbody", "PhysicMaterial"):
                notes.append(f"<b>Preview source:</b> symbolic physics diagnostic for {go_link()}.")
                notes.append("Physics records define interaction, gravity, collision and trigger behaviour. They usually do not draw the visible model.")
            elif t in ("LineRenderer", "TrailRenderer"):
                notes.append(f"<b>Preview source:</b> symbolic generated-renderer diagnostic for {go_link()}.")
                notes.append("LineRenderer and TrailRenderer create ribbon geometry at runtime, rather than pointing to a normal Mesh asset.")
            elif t == "SpriteMask":
                notes.append(f"<b>Preview source:</b> linked Sprite image when resolvable, otherwise a symbolic 2D mask diagnostic for {go_link()}.")
                notes.append("SpriteMask is an invisible stencil: the linked Sprite image defines the mask shape, but the mask itself is normally not drawn as visible artwork.")
            elif t == "TextAsset":
                notes.append("<b>Preview source:</b> readable text/config preview when the asset data is text.")
                notes.append("TextAssets are often JSON, config, localization, dialogue or small binary tables.")
            elif t == "Avatar":
                notes.append("<b>Preview source:</b> symbolic rig card.")
                notes.append("Avatar is animation rig mapping metadata, not a visible mesh; inspect it with Animator/SkinnedMeshRenderer/bones.")
            elif t in ("Font", "TMP_FontAsset"):
                notes.append("<b>Preview source:</b> font sample card.")
                notes.append("UBE tries to load embedded TrueType/OpenType bytes when exposed; otherwise it shows a system-font sample using the asset name.")
            elif t == "PlayableDirector":
                notes.append(f"<b>Preview source:</b> symbolic Timeline/Playable controller diagnostic for {go_link()}.")
                notes.append("PlayableDirector is a sequencer/controller; it does not render by itself.")
            elif t in ("NavMeshData", "NavMeshSettings", "NavMeshProjectSettings"):
                notes.append("<b>Preview source:</b> symbolic NavMesh/pathfinding diagnostic.")
                notes.append("NavMesh data is an invisible walking/pathfinding surface used by AI agents; it is not visible level artwork.")
            elif t == "Camera":
                notes.append("<b>Preview source:</b> camera frustum diagram.")
                notes.append("The frustum visual shows projection/lens/clip behaviour, not a screenshot from the camera.")
            elif t == "RectTransform":
                notes.append(f"<b>Preview source:</b> UI rectangle/anchor diagnostic for {go_link()}.")
                notes.append("RectTransform is UI layout data, so the preview shows anchors, pivot, size, and offset rather than a 3D mesh.")
            elif t == "Texture2D":
                notes.append("<b>Preview source:</b> decoded texture preview.")
                notes.append("Wheel zoom and drag pan help inspect large atlases; clickable rows project a renderer mesh's UV bounds over the texture.")
                notes.append("The UVs belong to the mesh, not the texture. UBE shows available channels for comparison; the shader decides which channel actually samples each texture slot.")

            if not notes:
                return []

            html = ["<div class='card'>", "<div class='head'>👁 Preview context</div>"]
            html.append("<div>" + "<br>".join(notes) + "</div>")
            html.append("</div>")
            return ["".join(html)]

        def _inspector_text_html(self, text: str, rec) -> str:
            """Escape inspector text, with small clickable helpers for known blocks."""
            if getattr(rec, "type_name", "") == "Texture2D" and (
                "Mesh UV regions on" in text or "Mesh UV bounds projected onto" in text
            ):
                return self._texture_atlas_text_html(text, rec)
            return escape(text)

        def _texture_atlas_text_html(self, text: str, rec) -> str:
            """Turn atlas finder UV rows into preview-overlay links.

            The core inspector stays plain text.  The UI layer reads the
            generated UV region lines and adds educational links: click the row
            number for the smallest atlas-candidate box, or click a specific UV
            token to compare channels.  The candidate is deliberately labelled
            as unconfirmed because only the shader decides which UV channel is
            paired with a particular texture slot.
            """
            lines = text.splitlines()
            out: list[str] = []
            row_re = re.compile(r"^(\s*)(\d+):\s+(.*)$")
            region_re = re.compile(
                r"UV(?P<uv>\d+)\s*:\s*x\s*(?P<x>[-+]?\d+)\s*[–-]\s*(?P<x2>[-+]?\d+)\s*,\s*"
                r"y\s*(?P<y>[-+]?\d+)\s*[–-]\s*(?P<y2>[-+]?\d+)\s*\(\s*(?P<w>\d+)\s*[×x]\s*(?P<h>\d+)\s*px\s*\)"
            )
            renderer_re = re.compile(r"Renderer:\s*([A-Za-z_]+_(-?\d+))")

            def region_from_match(m):
                try:
                    return {
                        "uv": int(m.group("uv")),
                        "x": int(m.group("x")),
                        "y": int(m.group("y")),
                        "w": max(1, int(m.group("w"))),
                        "h": max(1, int(m.group("h"))),
                    }
                except Exception:
                    return None

            def atlas_url(row_num: int, region: dict) -> str:
                return (
                    f"ube://atlas/{int(getattr(rec, 'path_id', 0) or 0)}/{int(row_num)}/"
                    f"{region['x']}/{region['y']}/{region['w']}/{region['h']}/{region['uv']}"
                )

            current_row = None
            current_renderer_pid = None
            i = 0
            while i < len(lines):
                line = lines[i]
                m = row_re.match(line)
                if m:
                    indent, num_text, name_text = m.groups()
                    current_row = int(num_text)
                    current_renderer_pid = None
                    first_region = None
                    renderer_pid = None
                    # The renderer and UV region lines are normally inside the
                    # next few lines.  Link the row number to the first/likely
                    # UV box, while still making each UV token clickable below.
                    for look in lines[i + 1:i + 12]:
                        if renderer_pid is None:
                            rm = renderer_re.search(look)
                            if rm:
                                try:
                                    renderer_pid = int(rm.group(2))
                                except Exception:
                                    renderer_pid = None
                        rr = region_re.search(look)
                        if rr:
                            candidate_region = region_from_match(rr)
                            is_candidate = "candidate" in look.lower() or "likely" in look.lower()
                            if candidate_region and (first_region is None or is_candidate):
                                first_region = candidate_region
                                if is_candidate:
                                    # Prefer the core inspector's smallest atlas
                                    # candidate for the numbered-row shortcut.  This is
                                    # a comparison hint, not confirmed shader wiring.
                                    pass
                    current_renderer_pid = renderer_pid

                    prefix = escape(indent)
                    if first_region:
                        num_html = f"<a class='atlasbox' href='{atlas_url(current_row, first_region)}'>▣ {escape(num_text)}</a>"
                    else:
                        num_html = escape(num_text)

                    safe_name = escape(name_text)
                    if renderer_pid is not None:
                        safe_name = f"<a href='ube://asset/{renderer_pid}'>{safe_name}</a>"
                    out.append(f"{prefix}{num_html}: {safe_name}")
                    i += 1
                    continue

                rr = region_re.search(line)
                if rr and current_row is not None:
                    region = region_from_match(rr)
                    if region:
                        # Preserve the original line text but replace only the
                        # UV token with a link.  This gives separate UV0 / UV1
                        # click targets on grouped atlas rows.
                        uv_token = f"UV{region['uv']}"
                        linked = (
                            f"<a class='atlasbox' href='{atlas_url(current_row, region)}'>"
                            f"▣ {escape(uv_token)}</a>"
                        )
                        escaped = escape(line)
                        escaped = escaped.replace(escape(uv_token), linked, 1)
                        out.append(escaped)
                        i += 1
                        continue

                # Renderer path IDs can still be linked even if the selected
                # line is not the numbered heading.
                if current_renderer_pid is not None and "Renderer:" in line:
                    out.append(escape(line))
                else:
                    out.append(escape(line))
                i += 1
            return "\n".join(out)

        def _draw_texture_preview_with_overlay(self, overlay: dict | None = None):
            """Draw the selected Texture2D preview, optionally with an atlas box.

            v1.7u: the texture preview is now a small 2D viewer.  The base
            preview is rendered into the QLabel at a zoomable/pannable scale;
            the atlas rectangle is drawn before scaling so it stays locked to
            the correct texture pixels.
            """
            if self.texture_preview_base_pixmap is None or self.texture_preview_base_pixmap.isNull():
                return False
            pix = QPixmap(self.texture_preview_base_pixmap)
            def draw_texture_box(box: dict, label: str, border: QColor, fill: QColor, pen_width: int = 3):
                try:
                    tex_w, tex_h = self.texture_preview_texture_size
                    if tex_w <= 0 or tex_h <= 0:
                        return
                    sx = pix.width() / float(tex_w)
                    sy = pix.height() / float(tex_h)
                    x = max(0.0, float(box.get("x", 0)) * sx)
                    y = max(0.0, float(box.get("y", 0)) * sy)
                    w = max(2.0, float(box.get("w", 1)) * sx)
                    h = max(2.0, float(box.get("h", 1)) * sy)
                    if x + w > pix.width():
                        w = max(2.0, pix.width() - x)
                    if y + h > pix.height():
                        h = max(2.0, pix.height() - y)

                    painter = QPainter(pix)
                    painter.setRenderHint(QPainter.Antialiasing, False)
                    painter.setPen(QPen(border, pen_width))
                    painter.setBrush(QBrush(fill))
                    painter.drawRect(int(round(x)), int(round(y)), int(round(w)), int(round(h)))
                    cx = int(round(x + w * 0.5))
                    cy = int(round(y + h * 0.5))
                    painter.drawLine(max(0, cx - 10), cy, min(pix.width(), cx + 10), cy)
                    painter.drawLine(cx, max(0, cy - 10), cx, min(pix.height(), cy + 10))
                    painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    label_w = max(130, min(420, len(label) * 8 + 18))
                    label_x = int(max(4, min(pix.width() - label_w - 4, x + 4)))
                    label_y = int(max(4, y - 26 if y > 30 else y + h + 6))
                    painter.setPen(QPen(QColor(10, 10, 10), 1))
                    painter.setBrush(QBrush(QColor(border.red(), border.green(), border.blue(), 220)))
                    painter.drawRoundedRect(label_x, label_y, label_w, 22, 5, 5)
                    painter.setPen(QColor(20, 20, 20))
                    painter.drawText(label_x + 8, label_y + 16, label)
                    painter.end()
                except Exception:
                    pass

            if self.texture_preview_texture_size:
                if overlay:
                    draw_texture_box(
                        overlay,
                        f"Atlas row {overlay.get('row', '?')}  UV{overlay.get('uv', '?')}",
                        QColor(255, 210, 80),
                        QColor(255, 210, 80, 42),
                        3,
                    )
                selection = self._texture_selection_overlay()
                if selection and selection.get("w", 0) >= 2 and selection.get("h", 0) >= 2:
                    draw_texture_box(
                        selection,
                        f"Search box {selection.get('w', 0)}×{selection.get('h', 0)}",
                        QColor(120, 220, 255),
                        QColor(120, 220, 255, 36),
                        2,
                    )

            view_w = max(1, int(self.preview.width()))
            view_h = max(1, int(self.preview.height()))
            self._clamp_texture_pan()
            fit = self._texture_fit_scale()
            zoom = max(1.0, min(float(self.texture_preview_zoom), self._texture_max_zoom()))
            self.texture_preview_zoom = zoom
            scale = fit * zoom
            draw_w = max(1, int(round(pix.width() * scale)))
            draw_h = max(1, int(round(pix.height() * scale)))
            x0 = int(round((view_w - draw_w) * 0.5 + float(self.texture_preview_pan.x())))
            y0 = int(round((view_h - draw_h) * 0.5 + float(self.texture_preview_pan.y())))

            canvas = QPixmap(view_w, view_h)
            canvas.fill(QColor(28, 28, 30))
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, zoom <= 1.0001)
            painter.drawPixmap(x0, y0, draw_w, draw_h, pix)

            # Small zoom HUD when zoomed in, unobtrusive but useful.
            if zoom > 1.0001:
                display_scale = scale
                pct = int(round(display_scale * 100.0))
                hud = f"{pct}%  wheel zoom / middle-drag pan / double-click reset / Tab focus"
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                hud_w = max(240, min(view_w - 16, len(hud) * 7 + 18))
                painter.setPen(QPen(QColor(10, 10, 10), 1))
                painter.setBrush(QBrush(QColor(255, 210, 80, 205)))
                painter.drawRoundedRect(8, 8, hud_w, 22, 5, 5)
                painter.setPen(QColor(20, 20, 20))
                painter.drawText(16, 24, hud)
            painter.end()

            self.preview.setPixmap(canvas)
            return True

        def show_texture_atlas_overlay(self, texture_path_id: int, row: int, x: int, y: int, w: int, h: int, uv: int):
            """Show a highlighted atlas rectangle on the selected texture preview."""
            if self.selected_record is None or int(getattr(self.selected_record, "path_id", 0) or 0) != int(texture_path_id):
                self.select_record_by_path_id(texture_path_id, push_history=True)
            if self.selected_record is None or getattr(self.selected_record, "type_name", "") != "Texture2D":
                return
            self.texture_atlas_overlay = {"row": row, "x": x, "y": y, "w": w, "h": h, "uv": uv}
            self._center_texture_view_on_overlay()
            if not self._draw_texture_preview_with_overlay(self.texture_atlas_overlay):
                self.preview_texture(self.selected_record)
                self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            try:
                self.statusBar().showMessage(
                    f"Atlas row {row}: UV{uv} region x {x}–{x + w}, y {y}–{y + h} ({w}×{h}px)",
                    6000,
                )
            except Exception:
                pass

        def _texture_region_rect_intersection(self, a: dict, b: dict):
            ax1 = int(a.get("x", 0)); ay1 = int(a.get("y", 0))
            ax2 = ax1 + max(0, int(a.get("w", 0))); ay2 = ay1 + max(0, int(a.get("h", 0)))
            bx1 = int(b.get("x", 0)); by1 = int(b.get("y", 0))
            bx2 = bx1 + max(0, int(b.get("w", 0))); by2 = by1 + max(0, int(b.get("h", 0)))
            ix1 = max(ax1, bx1); iy1 = max(ay1, by1)
            ix2 = min(ax2, bx2); iy2 = min(ay2, by2)
            iw = max(0, ix2 - ix1); ih = max(0, iy2 - iy1)
            return iw * ih

        def _texture_atlas_region_rows_for_record(self, rec):
            """Parse the plain Texture2D inspector and return atlas UV region rows."""
            if rec is None or getattr(rec, "type_name", "") != "Texture2D":
                return []
            try:
                plain = describe_record(rec, self.bundle_index, self.asset_graph, include_relationships=False)
            except Exception:
                return []
            lines = plain.splitlines()
            row_re = re.compile(r"^(\s*)(\d+):\s+(.*)$")
            region_re = re.compile(
                r"UV(?P<uv>\d+)\s*:\s*x\s*(?P<x>[-+]?\d+)\s*[–-]\s*(?P<x2>[-+]?\d+)\s*,\s*"
                r"y\s*(?P<y>[-+]?\d+)\s*[–-]\s*(?P<y2>[-+]?\d+)\s*\(\s*(?P<w>\d+)\s*[×x]\s*(?P<h>\d+)\s*px\s*\)"
            )
            renderer_re = re.compile(r"Renderer:\s*([A-Za-z_]+_(-?\d+))")
            mesh_re = re.compile(r"Mesh:\s*([^|]+)")
            mat_re = re.compile(r"Material:\s*([^|]+)")
            rows = []
            current = None
            current_renderer_pid = None
            current_mesh = ""
            current_mat = ""
            for line in lines:
                m = row_re.match(line)
                if m:
                    current = {"row": int(m.group(2)), "name": m.group(3).strip()}
                    current_renderer_pid = None
                    current_mesh = ""
                    current_mat = ""
                    continue
                if current is None:
                    continue
                rm = renderer_re.search(line)
                if rm:
                    try:
                        current_renderer_pid = int(rm.group(2))
                    except Exception:
                        current_renderer_pid = None
                mm = mesh_re.search(line)
                if mm:
                    current_mesh = mm.group(1).strip()
                ma = mat_re.search(line)
                if ma:
                    current_mat = ma.group(1).strip()
                rr = region_re.search(line)
                if rr:
                    try:
                        rows.append({
                            "row": int(current.get("row", 0)),
                            "name": str(current.get("name", "")),
                            "renderer_pid": current_renderer_pid,
                            "mesh": current_mesh,
                            "material": current_mat,
                            "uv": int(rr.group("uv")),
                            "x": int(rr.group("x")),
                            "y": int(rr.group("y")),
                            "w": max(1, int(rr.group("w"))),
                            "h": max(1, int(rr.group("h"))),
                            "line": line.strip(),
                            "kind": line.split(";", 1)[1].strip() if ";" in line else "",
                        })
                    except Exception:
                        pass
            return rows

        def _run_texture_region_search(self, region: dict):
            """Search current Texture2D atlas rows for UV rectangles overlapping a user-drawn area."""
            rec = self.selected_record
            if rec is None or getattr(rec, "type_name", "") != "Texture2D":
                return
            tex_pid = int(getattr(rec, "path_id", 0) or 0)
            tex_w, tex_h = self.texture_preview_texture_size or (0, 0)
            selected_area = max(1, int(region.get("w", 0)) * int(region.get("h", 0)))
            tex_area = max(1, int(tex_w) * int(tex_h))
            matches = []
            broad_matches = []
            for r in self._texture_atlas_region_rows_for_record(rec):
                inter = self._texture_region_rect_intersection(region, r)
                if inter <= 0:
                    continue
                r_area = max(1, int(r.get("w", 0)) * int(r.get("h", 0)))
                overlap_selected = inter / float(selected_area)
                overlap_region = inter / float(r_area)
                broad = r_area > tex_area * 0.35 or "mostly full texture" in str(r.get("kind", "")).lower()
                item = dict(r)
                item["overlap_selected"] = overlap_selected
                item["overlap_region"] = overlap_region
                item["broad"] = broad
                # Prefer compact atlas tiles that substantially touch the box.
                item["score"] = (overlap_region * 3.0) + overlap_selected - (r_area / float(tex_area))
                if broad:
                    broad_matches.append(item)
                else:
                    matches.append(item)
            matches.sort(key=lambda x: x.get("score", 0), reverse=True)
            broad_matches.sort(key=lambda x: x.get("score", 0), reverse=True)

            shown = matches[:80]
            if not shown and broad_matches:
                shown = broad_matches[:40]
                broad_note = "Only broad/full-texture UV regions matched this box."
            else:
                broad_note = f"{len(broad_matches)} broad/full-texture UV region(s) also overlap and are hidden from the main list." if broad_matches else ""

            def link_name(item):
                name = escape(str(item.get("name", "")))
                pid = item.get("renderer_pid")
                if pid is not None:
                    return f"<a href='ube://asset/{int(pid)}'>{name}</a>"
                return name

            html = []
            html.append("<div class='card atlas-results'>")
            html.append("<div class='head'>🔎 Manual atlas region search results</div>")
            html.append(
                f"<div>Selected box: x {int(region.get('x', 0))}–{int(region.get('x', 0)) + int(region.get('w', 0))}, "
                f"y {int(region.get('y', 0))}–{int(region.get('y', 0)) + int(region.get('h', 0))} "
                f"({int(region.get('w', 0))}×{int(region.get('h', 0))} px)</div>"
            )
            html.append("<div class='muted'>Search method: compare your drawn box with the mesh UV rectangles already found by the Texture Atlas Region Finder.</div>")
            if broad_note:
                html.append(f"<div class='muted'>{escape(broad_note)}</div>")
            if shown:
                html.append(f"<ol>")
                for item in shown:
                    x = int(item.get("x", 0)); y = int(item.get("y", 0)); w = int(item.get("w", 0)); h = int(item.get("h", 0))
                    uv = int(item.get("uv", 0)); row = int(item.get("row", 0))
                    atlas_href = f"ube://atlas/{tex_pid}/{row}/{x}/{y}/{w}/{h}/{uv}"
                    html.append(
                        "<li>"
                        f"<a class='atlasbox' href='{atlas_href}'>▣ UV{uv}</a> "
                        f"{link_name(item)}"
                        f"<br><span class='muted'>row {row}; x {x}–{x+w}, y {y}–{y+h} ({w}×{h}px); "
                        f"overlap {item.get('overlap_region', 0)*100:.1f}% of this UV region"
                        f"</span>"
                    )
                    mesh = escape(str(item.get("mesh", "")))
                    mat = escape(str(item.get("material", "")))
                    if mesh or mat:
                        html.append(f"<br><span class='muted'>Mesh: {mesh} &nbsp; Material: {mat}</span>")
                    html.append("</li>")
                html.append("</ol>")
            else:
                html.append("<div>No mesh UV regions overlapped this selection.</div>")
            html.append(
                f"<div class='muted'>"
                f"<a href='ube://toggle_region_search/{tex_pid}'>show/hide results</a> · "
                f"<a href='ube://clear_region_search/{tex_pid}'>clear results</a>"
                f"</div>"
            )
            html.append("</div>")
            self.texture_region_search_html_by_pid[tex_pid] = "".join(html)
            self.texture_region_search_visible_by_pid[tex_pid] = True
            try:
                self.statusBar().showMessage(f"Atlas region search: {len(shown)} shown, {len(broad_matches)} broad hidden", 6000)
            except Exception:
                pass
            self.show_record_in_inspector(rec, push_history=False)

        def _texture_region_search_results_html(self, rec) -> list[str]:
            if rec is None or getattr(rec, "type_name", "") != "Texture2D":
                return []
            pid = int(getattr(rec, "path_id", 0) or 0)
            html = self.texture_region_search_html_by_pid.get(pid)
            if not html:
                return []
            if self.texture_region_search_visible_by_pid.get(pid, True):
                return [html]
            return [
                "<div class='card'>"
                "<div class='head'>🔎 Manual atlas region search results</div>"
                "<div class='collapsed'>Results hidden. "
                f"<a href='ube://toggle_region_search/{pid}'>show results</a> · "
                f"<a href='ube://clear_region_search/{pid}'>clear results</a>"
                "</div></div>"
            ]

        def _find_pathid_index_root(self) -> Path | None:
            """Find the nearest .ube_pathid_index.json without parsing it."""
            candidates = []
            if self.current_project_folder is not None:
                candidates.append(Path(self.current_project_folder))
            if self.project_index is not None:
                candidates.append(Path(self.project_index.folder))
            if self.bundle_index is not None:
                p = Path(self.bundle_index.path)
                candidates.append(p.parent)
                candidates.extend(list(p.parents)[:5])

            seen = set()
            for folder in candidates:
                try:
                    key = str(folder.resolve())
                except Exception:
                    key = str(folder)
                if key in seen:
                    continue
                seen.add(key)
                if index_path(folder).exists():
                    return folder
            return None

        def _lazy_resolve_pathid_from_project_index(self, path_id: int):
            """Resolve one external PathID from the big JSON index, on demand only.

            This deliberately does not load the full JSON file.  It streams until
            it finds the requested PathID, caches that one result, and adds it to
            the current bundle's external maps so existing external links work.
            """
            if self.bundle_index is None or path_id in (None, 0):
                return None
            if path_id in getattr(self.bundle_index, "record_by_path_id", {}):
                return getattr(self.bundle_index, "record_by_path_id", {}).get(path_id)
            existing = getattr(self.bundle_index, "external_record_by_path_id", {}).get(path_id)
            if existing is not None:
                return existing

            root = self._find_pathid_index_root()
            if root is None:
                return None

            cache_key = (str(root), int(path_id))
            if cache_key in self.pathid_lookup_cache:
                cached = self.pathid_lookup_cache.get(cache_key)
                if cached is None:
                    return None
                rec, bundle_path = cached
                self.bundle_index.external_record_by_path_id.setdefault(path_id, rec)
                self.bundle_index.external_bundle_by_path_id.setdefault(path_id, bundle_path)
                return rec

            # Protect the UI from a page with many unresolved links.  We only do a
            # handful of expensive single-PathID scans per inspector render; cached
            # values are free afterward.
            if self._pathid_lookup_render_budget <= 0:
                return None
            self._pathid_lookup_render_budget -= 1

            matches = lookup_pathid_index_records(root, int(path_id), max_results=8)
            if not matches:
                self.pathid_lookup_cache[cache_key] = None
                return None

            current = Path(getattr(self.bundle_index, "path", ""))

            def score(entry):
                try:
                    if entry.bundle_path.resolve() == current.resolve():
                        return 9999
                except Exception:
                    pass
                # Prefer same course/sibling folders, then OBB/global bundles.
                try:
                    if entry.bundle_path.parent == current.parent:
                        return 0
                except Exception:
                    pass
                name = entry.bundle_path.name.lower()
                rel = str(entry.bundle_path).lower()
                if "assets" in name or "common" in name:
                    return 5
                if "obb" in rel or "urp" in name or "shader" in name:
                    return 10
                return 20

            best = sorted(matches, key=score)[0]
            rec = AssetRecord(
                name=best.name or f"{best.type_name}_{path_id}",
                type_name=best.type_name or "Unknown",
                path_id=int(path_id),
                object=None,
            )
            self.bundle_index.external_record_by_path_id.setdefault(int(path_id), rec)
            self.bundle_index.external_bundle_by_path_id.setdefault(int(path_id), best.bundle_path)
            self.pathid_lookup_cache[cache_key] = (rec, best.bundle_path)
            return rec

        def _cache_key_for_bundle(self, bundle_path: Path) -> str:
            try:
                return str(Path(bundle_path).resolve()).lower()
            except Exception:
                return str(Path(bundle_path)).lower()

        def _hydrate_external_pathid_from_project_index(self, path_id: int):
            """Load the one external bundle needed for a selected object's PathID.

            The inspector's lazy resolver is deliberately metadata-only so it can
            display names quickly.  Preview/export need the real UnityPy object,
            so for a selected object we load only the bundle that owns the exact
            missing PathID, then merge that bundle's records into the current
            external maps.  This keeps normal browsing fast and avoids opening the
            whole multi-million-object project.
            """
            if self.bundle_index is None or path_id in (None, 0):
                return None

            local = getattr(self.bundle_index, "record_by_path_id", {})
            if int(path_id) in local:
                return local.get(int(path_id))

            existing = getattr(self.bundle_index, "external_record_by_path_id", {}).get(int(path_id))
            if existing is not None and getattr(existing, "object", None) is not None:
                return existing

            # Ensure the exact PathID has at least a metadata entry and bundle path.
            if existing is None or getattr(self.bundle_index, "external_bundle_by_path_id", {}).get(int(path_id)) is None:
                self._lazy_resolve_pathid_from_project_index(int(path_id))

            bundle_path = getattr(self.bundle_index, "external_bundle_by_path_id", {}).get(int(path_id))
            if bundle_path is None:
                return existing

            try:
                key = self._cache_key_for_bundle(Path(bundle_path))
                ext_idx = self.external_bundle_cache.get(key)
                if ext_idx is None:
                    notice_already_visible = bool(
                        self._loading_dialog is not None and self._loading_dialog.isVisible()
                    )
                    if not notice_already_visible:
                        self._show_loading_notice(Path(bundle_path))
                    try:
                        self._update_loading_notice(f"Loading referenced bundle {Path(bundle_path).name}…")
                        ext_idx = self._load_bundle_responsive(Path(bundle_path))
                        self.external_bundle_cache[key] = ext_idx
                    finally:
                        if not notice_already_visible:
                            self._hide_loading_notice(success=True)

                # Merge just-loaded bundle records into the current bundle's
                # external maps.  This is one bundle only, and it lets an external
                # material resolve its own local textures for preview/export.
                current_local = getattr(self.bundle_index, "record_by_path_id", {})
                ext_records = getattr(self.bundle_index, "external_record_by_path_id", {})
                ext_bundles = getattr(self.bundle_index, "external_bundle_by_path_id", {})
                for pid, rec in getattr(ext_idx, "record_by_path_id", {}).items():
                    if pid in current_local:
                        continue
                    # Prefer existing exact/course-local links, but replace
                    # metadata-only entries from the same bundle with real ones.
                    old = ext_records.get(pid)
                    if old is None or getattr(old, "object", None) is None:
                        ext_records[pid] = rec
                        ext_bundles[pid] = Path(bundle_path)

                return ext_records.get(int(path_id))
            except Exception:
                return existing

        def _hydrate_pptr_for_preview(self, pptr_or_pid):
            pid = pptr_or_pid if isinstance(pptr_or_pid, int) else self._ov_pptr_path_id(pptr_or_pid)
            if pid in (None, 0):
                return None
            rec = self._ov_resolve(int(pid))
            if rec is not None and getattr(rec, "object", None) is not None:
                return rec
            return self._hydrate_external_pathid_from_project_index(int(pid))

        def _hydrate_material_texture_refs_for_preview(self, mat_rec) -> None:
            if mat_rec is None or getattr(mat_rec, "type_name", "") != "Material":
                return
            if getattr(mat_rec, "object", None) is None:
                mat_rec = self._hydrate_external_pathid_from_project_index(int(getattr(mat_rec, "path_id", 0) or 0))
            data = self._ov_read(mat_rec)
            if data is None:
                return
            saved = self._ov_get(data, "m_SavedProperties", "saved_properties", default=None)
            tex_envs = self._ov_get(saved, "m_TexEnvs", "tex_envs", default=None) if saved is not None else None
            for item in self._ov_as_list(tex_envs):
                _key, value = self._ov_pair_key_value(item)
                texture = self._ov_get(value, "m_Texture", "texture", default=value)
                self._hydrate_pptr_for_preview(texture)

        def _hydrate_material_base_colour_for_preview(self, mat_rec):
            """Hydrate one material and its recognised base-colour texture only."""
            if mat_rec is None or getattr(mat_rec, "type_name", "") != "Material":
                return None
            if getattr(mat_rec, "object", None) is None:
                mat_rec = self._hydrate_external_pathid_from_project_index(
                    int(getattr(mat_rec, "path_id", 0) or 0)
                )
            if mat_rec is None:
                return None
            saved = self._material_saved_properties(mat_rec)
            _slot, texture_pptr, texture_pid = self._material_find_texture_slot(
                saved,
                "_BaseMap", "_ColorMap", "_ColourMap", "_BaseColorMap",
                "_MainTex", "_MainTexture", "_Albedo", "_BaseTex",
                "_BaseMap1",
            )
            if texture_pptr is None and texture_pid in (None, 0):
                return None
            return self._hydrate_pptr_for_preview(
                texture_pptr if texture_pptr is not None else int(texture_pid)
            )

        def _hydrate_animation_render_assets(
            self,
            items,
            max_items: int = 240,
            max_new_bundles: int = 4,
            progress_callback=None,
        ) -> tuple[int, int]:
            """Hydrate external base-colour dependencies before animation draw.

            Animation preview used to hand its render items directly to the 3D
            viewer. Material preview followed external texture references first,
            so an external `_ColorMap` could appear only after the user clicked a
            Material. This bounded pass follows only the visible renderers'
            Material and recognised base-colour texture references before the
            viewer builds its material cache.

            Returns ``(visited_objects, newly_loaded_bundles)``.
            """
            if self.bundle_index is None or not items:
                return 0, 0

            before = set(getattr(self, "external_bundle_cache", {}).keys())
            visited = 0
            seen_objects = set()
            seen_materials = set()

            bounded_items = list(items or [])[:max(0, int(max_items or 0))]
            total_items = len(bounded_items)
            progress_step = max(1, total_items // 8) if total_items else 1
            for item_index, item in enumerate(bounded_items):
                if progress_callback is not None and (
                    item_index == 0 or (item_index + 1) % progress_step == 0 or item_index + 1 == total_items
                ):
                    progress_callback(
                        f"Resolving materials and visual dependencies: "
                        f"{item_index + 1:,}/{total_items:,} render instance(s)…"
                    )
                rec = item.get("record") if isinstance(item, dict) else None
                if rec is None:
                    continue
                object_key = self._ov_record_key(rec)
                if object_key in seen_objects:
                    continue
                seen_objects.add(object_key)
                visited += 1

                try:
                    go_rec = self._ov_owning_gameobject(rec)
                    components = self._ov_component_records_for_gameobject(go_rec) if go_rec is not None else []
                    type_name = str(getattr(rec, "type_name", "") or "")
                    renderers = []
                    if type_name in ("MeshRenderer", "SkinnedMeshRenderer"):
                        renderers.append(rec)
                    renderers.extend(
                        comp for comp in components
                        if getattr(comp, "type_name", "") in ("MeshRenderer", "SkinnedMeshRenderer")
                    )
                    if not renderers and go_rec is not None:
                        renderers.extend(self._ov_records_with_gameobject("MeshRenderer", go_rec)[:1])
                        renderers.extend(self._ov_records_with_gameobject("SkinnedMeshRenderer", go_rec)[:1])

                    for renderer in renderers:
                        renderer_data = self._ov_read(renderer)
                        if renderer_data is None:
                            continue
                        for mat_pptr in self._ov_as_list(
                            self._ov_get(renderer_data, "m_Materials", "materials", default=None)
                        ):
                            material_key = (
                                self._ov_pptr_file_id(mat_pptr),
                                self._ov_pptr_path_id(mat_pptr),
                            )
                            if material_key in seen_materials:
                                continue
                            seen_materials.add(material_key)
                            mat_rec = self._hydrate_pptr_for_preview(mat_pptr)
                            self._hydrate_material_base_colour_for_preview(mat_rec)

                            loaded_now = len(
                                set(getattr(self, "external_bundle_cache", {}).keys()) - before
                            )
                            if loaded_now >= max(1, int(max_new_bundles or 1)):
                                return visited, loaded_now
                except Exception:
                    # A malformed or missing dependency must not stop playback;
                    # the existing grey/external-link diagnostic remains valid.
                    continue

            after = set(getattr(self, "external_bundle_cache", {}).keys())
            return visited, len(after - before)

        def _hydrate_object_external_render_assets(self, rec) -> None:
            """Hydrate external Mesh/Material/Texture assets used by one object.

            This is the selected-object counterpart to the manual --pathID lookup:
            only exact MeshFilter/Renderer/SkinnedRenderer links are followed.
            """
            if rec is None or self.bundle_index is None:
                return
            go_rec = self._ov_owning_gameobject(rec)
            go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
            components = self._ov_component_records_for_gameobject(go_rec) if go_rec is not None else []
            type_name = getattr(rec, "type_name", "")

            mesh_filter = rec if type_name == "MeshFilter" else next((c for c in components if getattr(c, "type_name", "") == "MeshFilter"), None)
            mesh_renderer = rec if type_name == "MeshRenderer" else next((c for c in components if getattr(c, "type_name", "") == "MeshRenderer"), None)
            skinned = rec if type_name == "SkinnedMeshRenderer" else next((c for c in components if getattr(c, "type_name", "") == "SkinnedMeshRenderer"), None)

            if mesh_filter is None:
                hits = self._ov_records_with_gameobject("MeshFilter", go_rec)
                mesh_filter = hits[0] if hits else None
            if mesh_renderer is None:
                hits = self._ov_records_with_gameobject("MeshRenderer", go_rec)
                mesh_renderer = hits[0] if hits else None
            if skinned is None:
                hits = self._ov_records_with_gameobject("SkinnedMeshRenderer", go_rec)
                skinned = hits[0] if hits else None

            material_pptrs = []
            if skinned is not None:
                data = self._ov_read(skinned)
                if data is not None:
                    self._hydrate_pptr_for_preview(self._ov_get(data, "m_Mesh", "mesh", default=None))
                    material_pptrs.extend(self._ov_as_list(self._ov_get(data, "m_Materials", "materials", default=None)))
            else:
                if mesh_filter is not None:
                    data = self._ov_read(mesh_filter)
                    if data is not None:
                        self._hydrate_pptr_for_preview(self._ov_get(data, "m_Mesh", "mesh", default=None))
                if mesh_renderer is not None:
                    data = self._ov_read(mesh_renderer)
                    if data is not None:
                        material_pptrs.extend(self._ov_as_list(self._ov_get(data, "m_Materials", "materials", default=None)))

            for mat_pptr in material_pptrs:
                mat_rec = self._hydrate_pptr_for_preview(mat_pptr)
                self._hydrate_material_texture_refs_for_preview(mat_rec)

        def _asset_link_html(self, path_id, kind: str, name: str, relation: str = "", external_bundle: str | None = None, source_name: str = "") -> str:
            label = f"{display_name_with_icon(name, kind)}"
            source_suffix = f" <span style='color:#999'>[{escape(str(source_name))}]</span>" if source_name else ""
            rel_text = f"<span style='color:#bbb'>{escape(relation)}:</span> " if relation else ""
            if path_id is not None and self.bundle_index and path_id in getattr(self.bundle_index, "record_by_path_id", {}):
                return f"<li>{rel_text}<a href='ube://asset/{path_id}' style='color:#8ecbff; text-decoration:none'>{escape(label)}</a>{source_suffix}</li>"

            if path_id is not None and external_bundle:
                enc = quote(str(external_bundle), safe="")
                bundle_name = Path(external_bundle).name
                return (
                    f"<li>{rel_text}<a href='ube://external/{enc}/{path_id}' "
                    f"style='color:#8ecbff; text-decoration:none'>{escape(label)}</a>{source_suffix} "
                    f"<span style='color:#d9b36c'>🔍 External</span> "
                    f"<span style='color:#999'>({escape(bundle_name)}, PathID {escape(str(path_id))})</span></li>"
                )

            if path_id is not None:
                rec = self._lazy_resolve_pathid_from_project_index(int(path_id))
                ext_bundle = self.bundle_index.external_bundle_by_path_id.get(int(path_id)) if self.bundle_index else None
                if rec is not None and ext_bundle is not None:
                    enc = quote(str(ext_bundle), safe="")
                    bundle_name = Path(str(ext_bundle)).name
                    resolved_label = display_name_with_icon(rec.name, rec.type_name)
                    return (
                        f"<li>{rel_text}<a href='ube://external/{enc}/{path_id}' "
                        f"style='color:#8ecbff; text-decoration:none'>{escape(resolved_label)}</a>{source_suffix} "
                        f"<span style='color:#d9b36c'>🔎 Index</span> "
                        f"<span style='color:#999'>({escape(bundle_name)}, PathID {escape(str(path_id))})</span></li>"
                    )

            pid = "-" if path_id is None else str(path_id)
            return (
                f"<li>{rel_text}<span style='color:#d8d8d8'>{escape(label)}</span>{source_suffix} "
                f"<span style='color:#d9b36c'>🔍 External asset</span> "
                f"<span style='color:#999'>(PathID {escape(pid)}, not present in this bundle)</span></li>"
            )

        def _relationship_html(self, rec) -> list[str]:
            if not self.asset_graph or not self.bundle_index:
                return []
            parts = []
            try:
                refs = self.asset_graph.references(rec, self.bundle_index)
            except Exception as e:
                refs = []
                parts.append(f"<p style='color:#d99797'>⚠ Relationships could not be resolved: {escape(str(e))}</p>")
            if refs:
                parts.append(f"<h3 style='margin-bottom:4px'>🔗 References ({len(refs)})</h3><ul>")
                for rel in refs[:120]:
                    parts.append(self._asset_link_html(rel.target_path_id, rel.target_type, rel.target_name, rel.relationship, getattr(rel, "external_bundle", None), getattr(rel, "target_source_name", "")))
                if len(refs) > 120:
                    parts.append(f"<li>... {len(refs) - 120} more references</li>")
                parts.append("</ul>")
            try:
                used_by = self.asset_graph.used_by(rec, self.bundle_index)
            except Exception:
                used_by = []
            if used_by:
                parts.append(f"<h3 style='margin-bottom:4px'>🔗 Used by ({len(used_by)})</h3><ul>")
                for rel in used_by[:120]:
                    parts.append(self._asset_link_html(rel.source_path_id, rel.source_type, rel.source_name, rel.relationship, getattr(rel, "external_bundle", None), getattr(rel, "source_source_name", "")))
                if len(used_by) > 120:
                    parts.append(f"<li>... {len(used_by) - 120} more users</li>")
                parts.append("</ul>")
            return parts

        def show_info_context_menu(self, pos):
            """Right-click helper menu for the HTML inspector."""
            try:
                menu = self.info.createStandardContextMenu(pos)
            except Exception:
                menu = QMenu(self.info)
            rec = self.selected_record
            if rec is not None:
                menu.addSeparator()
                expand_action = menu.addAction("Expand all inspector sections")
                collapse_action = menu.addAction("Collapse all inspector sections")
                report_action = menu.addAction("Export inspector report...")
                expand_action.triggered.connect(self.expand_all_inspector_sections)
                collapse_action.triggered.connect(self.collapse_all_inspector_sections)
                report_action.triggered.connect(
                    lambda _=False, r=rec: self.export_inspector_reports(
                        [r], "Export inspector report", report_label=getattr(r, "name", "asset")
                    )
                )
                if getattr(rec, "type_name", "") == "Texture2D":
                    pid = int(getattr(rec, "path_id", 0) or 0)
                    if self.texture_region_search_html_by_pid.get(pid):
                        visible = self.texture_region_search_visible_by_pid.get(pid, True)
                        toggle_action = menu.addAction("Hide manual atlas search results" if visible else "Show manual atlas search results")
                        clear_action = menu.addAction("Clear manual atlas search results")
                        toggle_action.triggered.connect(lambda _=False, p=pid: self.toggle_texture_region_search_results(p))
                        clear_action.triggered.connect(lambda _=False, p=pid: self.clear_texture_region_search_results(p))
                    else:
                        hint_action = menu.addAction("Texture search: drag a box on the preview")
                        hint_action.setEnabled(False)
            menu.exec(self.info.mapToGlobal(pos))

        def _current_record_section_count(self) -> int:
            rec = self.selected_record
            if rec is None:
                return 0
            try:
                plain = describe_record(rec, self.bundle_index, self.asset_graph, include_relationships=False)
                _header, sections = self._split_inspector_sections(plain)
                return len(sections)
            except Exception:
                return 0

        def expand_all_inspector_sections(self):
            rec = self.selected_record
            if rec is None:
                return
            pid = int(getattr(rec, "path_id", 0) or 0)
            self.collapsed_inspector_sections = {k for k in self.collapsed_inspector_sections if k[0] != pid}
            self.show_record_in_inspector(rec, push_history=False)

        def collapse_all_inspector_sections(self):
            rec = self.selected_record
            if rec is None:
                return
            pid = int(getattr(rec, "path_id", 0) or 0)
            for i in range(self._current_record_section_count()):
                self.collapsed_inspector_sections.add((pid, i))
            self.show_record_in_inspector(rec, push_history=False)

        def toggle_texture_region_search_results(self, pid: int):
            self.texture_region_search_visible_by_pid[int(pid)] = not self.texture_region_search_visible_by_pid.get(int(pid), True)
            if self.selected_record is not None:
                self.show_record_in_inspector(self.selected_record, push_history=False)

        def clear_texture_region_search_results(self, pid: int):
            pid = int(pid)
            self.texture_region_search_html_by_pid.pop(pid, None)
            self.texture_region_search_visible_by_pid.pop(pid, None)
            self.texture_region_select_start = None
            self.texture_region_select_current = None
            self.texture_region_selecting = False
            if self.selected_record is not None:
                self.show_record_in_inspector(self.selected_record, push_history=False)
            self._draw_texture_preview_with_overlay(self.texture_atlas_overlay)
            try:
                self.statusBar().showMessage("Manual atlas search results cleared", 1800)
            except Exception:
                pass

        def on_info_link_clicked(self, url):
            text = url.toString()
            if text == "ube://comment/edit":
                self.edit_comment_for_record(self.selected_record)
                return

            toggle_prefix = "ube://toggle/"
            if text.startswith(toggle_prefix):
                try:
                    rest = text[len(toggle_prefix):]
                    path_text, idx_text = rest.split("/", 1)
                    key = (int(path_text), int(idx_text))
                except Exception:
                    return
                if key in self.collapsed_inspector_sections:
                    self.collapsed_inspector_sections.remove(key)
                else:
                    self.collapsed_inspector_sections.add(key)
                if self.selected_record is not None:
                    self.show_record_in_inspector(self.selected_record, push_history=False)
                return

            atlas_prefix = "ube://atlas/"
            if text.startswith(atlas_prefix):
                try:
                    rest = text[len(atlas_prefix):]
                    tex_pid, row, x, y, w, h, uv = [int(v) for v in rest.split("/", 6)]
                except Exception:
                    return
                self.show_texture_atlas_overlay(tex_pid, row, x, y, w, h, uv)
                return

            toggle_region_prefix = "ube://toggle_region_search/"
            if text.startswith(toggle_region_prefix):
                try:
                    pid = int(text[len(toggle_region_prefix):])
                except Exception:
                    return
                self.toggle_texture_region_search_results(pid)
                return

            clear_region_prefix = "ube://clear_region_search/"
            if text.startswith(clear_region_prefix):
                try:
                    pid = int(text[len(clear_region_prefix):])
                except Exception:
                    return
                self.clear_texture_region_search_results(pid)
                return

            external_prefix = "ube://external/"
            if text.startswith(external_prefix):
                try:
                    rest = text[len(external_prefix):]
                    bundle_text, pid_text = rest.rsplit("/", 1)
                    bundle_path = Path(unquote(bundle_text))
                    path_id = int(pid_text)
                except Exception:
                    return
                self.load_path(bundle_path, from_project=self.current_project_folder is not None)
                self.select_record_by_path_id(path_id, push_history=True)
                return

            prefix = "ube://asset/"
            if text.startswith(prefix):
                try:
                    path_id = int(text[len(prefix):])
                except Exception:
                    return
                self.select_record_by_path_id(path_id, push_history=True)

        def select_record_by_path_id(self, path_id: int, push_history: bool = True):
            if not self.bundle_index:
                return
            rec = getattr(self.bundle_index, "record_by_path_id", {}).get(path_id)
            item = self.item_by_path_id.get(path_id)
            if rec is None or item is None:
                return
            self._suppress_history = not push_history
            try:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
            finally:
                self._suppress_history = False
            # If selection did not change, force refresh.
            if getattr(rec, "type_name", "") != "AudioClip":
                self.stop_current_audio()
            self.selected_record = rec
            self.show_record_in_inspector(rec, push_history=push_history)
            self.export_button.setEnabled(self.export_supported_for_record(rec))
            if rec.type_name == "Texture2D":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_texture(rec)
            elif rec.type_name == "Texture2DArray":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview.setText(
                    f"Texture Array\n\n{rec.name}\n\n"
                    "This is a Texture2DArray, not a single PNG.\n"
                    "Inspect the right panel for slice/depth metadata.\n"
                    "Meshes may use this through _BaseMap plus _TextureIndex."
                )
            elif rec.type_name == "Cubemap":
                self.preview_cubemap(rec)
            elif rec.type_name == "Material":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_material(rec)
            elif rec.type_name == "Shader":
                self.preview_stack.setCurrentWidget(self.preview)
                self.preview_shader(rec)
            elif rec.type_name == "AudioClip":
                self.preview_stack.setCurrentWidget(self.audio_widget)
                self.preview_audio(rec)
            elif rec.type_name == "Sprite":
                self._hydrate_sprite_external_assets(rec)
                self.preview_sprite(rec)
            elif rec.type_name == "SpriteRenderer":
                self._hydrate_sprite_external_assets(rec)
                self.preview_sprite_renderer(rec)
            elif rec.type_name == "Camera":
                self.preview_camera(rec)
            elif rec.type_name == "Light":
                self.preview_light(rec)
            elif rec.type_name == "ReflectionProbe":
                self.preview_reflection_probe(rec)
            elif rec.type_name == "LODGroup":
                self.preview_lod_group(rec)
            elif rec.type_name in ("ParticleSystem", "ParticleSystemRenderer"):
                self.preview_particle_system(rec)
            elif rec.type_name == "BoxCollider":
                self.preview_box_collider(rec)
            elif rec.type_name in ("NavMeshData", "NavMeshSettings", "NavMeshProjectSettings"):
                self.preview_navmesh(rec)
            elif rec.type_name == "RectTransform":
                self.preview_rect_transform(rec)
            elif rec.type_name in self.object_view_types():
                self.preview_object_attached_mesh(rec)
            elif rec.type_name == "Mesh":
                self.preview_stack.setCurrentWidget(self.preview_3d)
                self.preview_3d.load_mesh_record(rec, self.bundle_index, self.asset_graph)
            elif rec.type_name in self.relationship_flow_auto_types():
                self.preview_relationship_flow(rec)
            else:
                self.preview_relationship_flow(rec)
        def push_history(self, path_id: int):
            if self.history_index >= 0 and self.history and self.history[self.history_index] == path_id:
                self.update_navigation_actions()
                return
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]
            self.history.append(path_id)
            self.history_index = len(self.history) - 1
            self.update_navigation_actions()

        def update_navigation_actions(self):
            if hasattr(self, "back_action"):
                self.back_action.setEnabled(self.history_index > 0)
                self.forward_action.setEnabled(self.history_index >= 0 and self.history_index < len(self.history) - 1)

        def go_back(self):
            if self.history_index <= 0:
                return
            self.history_index -= 1
            self.update_navigation_actions()
            self.select_record_by_path_id(self.history[self.history_index], push_history=False)

        def go_forward(self):
            if self.history_index < 0 or self.history_index >= len(self.history) - 1:
                return
            self.history_index += 1
            self.update_navigation_actions()
            self.select_record_by_path_id(self.history[self.history_index], push_history=False)

        def _tree_item_plain_label(self, item) -> str:
            try:
                return re.sub(r"^[^A-Za-z0-9_\\-/]+\s*", "", item.text(0) or "").strip()
            except Exception:
                return item.text(0) if item is not None else ""

        def _item_is_descendant_or_self(self, item, root_item) -> bool:
            cur = item
            while cur is not None:
                if cur is root_item:
                    return True
                cur = cur.parent()
            return False

        def _item_is_ancestor_of(self, item, child_item) -> bool:
            cur = child_item
            while cur is not None:
                if cur is item:
                    return True
                cur = cur.parent()
            return False

        def prompt_filter_branch(self, item):
            if item is None:
                return
            label = self._tree_item_plain_label(item) or "selected branch"
            previous = getattr(self, "branch_filter_text", "") or ""
            text, ok = QInputDialog.getText(
                self,
                "Filter this branch",
                f"Show only matching assets inside:\n{label}\n\nKeyword:",
                text=previous,
            )
            if not ok:
                return
            text = (text or "").strip()
            if not text:
                self.clear_branch_filter(apply_now=True)
                return
            self.branch_filter_item = item
            self.branch_filter_text = text
            self.branch_filter_label = label
            self.apply_tree_filter(self.search.text() if hasattr(self, "search") else "")
            try:
                item.setExpanded(True)
            except Exception:
                pass

        def clear_branch_filter(self, apply_now: bool = True):
            self.branch_filter_item = None
            self.branch_filter_text = ""
            self.branch_filter_label = ""
            if apply_now and hasattr(self, "tree"):
                self.apply_tree_filter(self.search.text() if hasattr(self, "search") else "")

        def _asset_type_for_group_item(self, item) -> str:
            if item is None:
                return ""
            data = item.data(0, Qt.UserRole)
            if isinstance(data, tuple) and len(data) >= 2 and data[0] == "asset_type":
                return str(data[1] or "")
            return ""

        def set_asset_type_isolation(self, type_name: str, apply_now: bool = True):
            type_name = str(type_name or "").strip()
            if not type_name or type_name not in getattr(self, "asset_type_items", {}):
                return
            self.isolated_asset_type = type_name

            # A branch filter outside the newly isolated type would deliberately
            # produce an empty tree, which is almost never useful.  Keep a branch
            # filter only when that branch lives inside the isolated type.
            branch_root = getattr(self, "branch_filter_item", None)
            type_root = self.asset_type_items.get(type_name)
            if branch_root is not None and type_root is not None and not self._item_is_descendant_or_self(branch_root, type_root):
                self.clear_branch_filter(apply_now=False)

            if apply_now and hasattr(self, "tree"):
                self.apply_tree_filter(self.search.text() if hasattr(self, "search") else "")
                try:
                    type_root.setExpanded(True)
                except Exception:
                    pass
                count = type_root.childCount() if type_root is not None else 0
                self.statusBar().showMessage(
                    f"Isolated asset type: {friendly_type_name(type_name)} ({count:,} assets). Untick the same menu item to restore all types.",
                    5000,
                )

        def clear_asset_type_isolation(self, apply_now: bool = True):
            previous = str(getattr(self, "isolated_asset_type", "") or "")
            self.isolated_asset_type = ""
            if apply_now and hasattr(self, "tree"):
                self.apply_tree_filter(self.search.text() if hasattr(self, "search") else "")
                if previous:
                    self.statusBar().showMessage("Asset-type isolation cleared — all asset types restored.", 3500)

        def has_active_tree_filter(self) -> bool:
            return (
                bool((self.search.text() or "").strip())
                or bool(getattr(self, "branch_filter_text", ""))
                or bool(getattr(self, "isolated_asset_type", ""))
            )

        def _item_matches_terms(self, item, terms: list[str]) -> bool:
            if not terms:
                return True
            hay = " ".join((item.text(col) or "").lower() for col in range(item.columnCount()))
            return all(term in hay for term in terms if term)

        def apply_tree_filter(self, text: str):
            global_text = (text or "").strip().lower()
            branch_text = (getattr(self, "branch_filter_text", "") or "").strip().lower()
            branch_root = getattr(self, "branch_filter_item", None)
            branch_active = bool(branch_text and branch_root is not None)

            isolated_type = str(getattr(self, "isolated_asset_type", "") or "")
            isolated_root = getattr(self, "asset_type_items", {}).get(isolated_type)
            isolation_active = bool(isolated_type and isolated_root is not None)

            def filter_item(item):
                in_isolated_type = (not isolation_active) or self._item_is_descendant_or_self(item, isolated_root)
                is_isolation_ancestor = (
                    isolation_active
                    and self._item_is_ancestor_of(item, isolated_root)
                    and item is not isolated_root
                )

                in_branch = (not branch_active) or self._item_is_descendant_or_self(item, branch_root)
                is_branch_ancestor = branch_active and self._item_is_ancestor_of(item, branch_root) and item is not branch_root

                # Type isolation is the outer visibility boundary.  Reject a
                # complete non-matching type branch before walking its children;
                # this is important for bundles containing 100,000+ objects.
                if isolation_active and not in_isolated_type and not is_isolation_ancestor:
                    item.setHidden(True)
                    return False

                # Branch filtering can use the same fast subtree rejection.
                if branch_active and not in_branch and not is_branch_ancestor:
                    item.setHidden(True)
                    return False

                child_match = False
                for i in range(item.childCount()):
                    if filter_item(item.child(i)):
                        child_match = True

                terms = []
                if global_text:
                    terms.append(global_text)
                if branch_active and in_branch:
                    terms.append(branch_text)

                own_match = in_isolated_type and in_branch and self._item_matches_terms(item, terms)
                # Keep the isolated type header visible even when a keyword
                # currently matches zero assets, so it can always be right-clicked
                # and unticked to restore the full tree.
                visible = own_match or child_match or is_isolation_ancestor or is_branch_ancestor or item is isolated_root
                item.setHidden(not visible)
                if (global_text or branch_active or isolation_active) and (
                    child_match or item is branch_root or item is isolated_root
                ):
                    item.setExpanded(True)
                return visible

            for i in range(self.tree.topLevelItemCount()):
                filter_item(self.tree.topLevelItem(i))


        def preview_cubemap(self, rec):
            """Draw a decoded cubemap preview when possible, otherwise a symbolic six-face diagram."""
            self.preview_stack.setCurrentWidget(self.preview)
            cd = cubemap_details(rec)
            result = None
            try:
                sha = getattr(self.bundle_index, "bundle_sha256", None) or getattr(self.bundle_index, "sha256", None) or ""
                result = get_texture_preview(rec, sha, size=1024)
            except Exception:
                result = None

            if result and result.path.exists():
                pix = QPixmap(str(result.path))
                if not pix.isNull():
                    # Scale decoded cubemap/contact sheet to the preview panel.
                    view_w = max(1, int(self.preview.width()))
                    view_h = max(1, int(self.preview.height()))
                    canvas = QPixmap(view_w, view_h)
                    canvas.fill(QColor(28, 28, 30))
                    painter = QPainter(canvas)
                    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                    scaled = pix.scaled(view_w - 20, view_h - 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x = int((view_w - scaled.width()) / 2)
                    y = int((view_h - scaled.height()) / 2)
                    painter.drawPixmap(x, y, scaled)
                    painter.setPen(QColor(220, 220, 220))
                    painter.setFont(QFont("Segoe UI", 10))
                    painter.drawText(10, view_h - 18, f"Cubemap preview/cache: {result.width}×{result.height} | {result.mode} | {rec.name}")
                    painter.end()
                    self.preview.setPixmap(canvas)
                    try:
                        self.info.append("\n🌌 Preview: decoded Cubemap/contact-sheet preview. Cubemaps are sampled by direction, not flat UV coordinates.")
                    except Exception:
                        pass
                    return

            # Symbolic fallback if UnityPy cannot decode this cubemap format.
            w = max(520, int(self.preview.width()))
            h = max(300, int(self.preview.height()))
            canvas = QPixmap(w, h)
            canvas.fill(QColor(28, 28, 30))
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(QPen(QColor(210, 210, 210), 2))
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.drawText(18, 32, f"🌌 Cubemap: {rec.name}")
            painter.setFont(QFont("Segoe UI", 9))
            if cd:
                painter.drawText(18, 56, f"Face size: {cd.width}×{cd.height}   Format: {cd.texture_format}   Mips: {cd.mip_count if cd.mip_count is not None else '-'}")
            else:
                painter.drawText(18, 56, "Metadata not available")

            # Draw a standard cubemap cross layout: +Y above, -Y below, +/-X around, +/-Z front/back.
            side = int(min(max(58, (h - 120) / 3), max(58, (w - 80) / 4.5)))
            cx = int(w / 2 - side / 2)
            cy = int(h / 2 - side / 2 + 20)
            faces = [
                ("+Y", 0, -1, QColor(120, 165, 230)),
                ("-X", -1, 0, QColor(230, 150, 110)),
                ("+Z", 0, 0, QColor(120, 210, 150)),
                ("+X", 1, 0, QColor(230, 210, 110)),
                ("-Z", 2, 0, QColor(170, 140, 220)),
                ("-Y", 0, 1, QColor(120, 200, 220)),
            ]
            for label, gx, gy, colour in faces:
                x = cx + gx * side
                y = cy + gy * side
                painter.setBrush(QBrush(QColor(colour.red(), colour.green(), colour.blue(), 155)))
                painter.setPen(QPen(QColor(235, 235, 235), 2))
                painter.drawRoundedRect(x, y, side - 4, side - 4, 8, 8)
                painter.setPen(QColor(20, 20, 20))
                painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
                painter.drawText(x, y, side - 4, side - 4, Qt.AlignCenter, label)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor(210, 210, 210))
            note = "Used for skyboxes, reflections, ambient/environment lighting and shiny material lookups."
            painter.drawText(18, h - 42, note)
            painter.drawText(18, h - 22, "Preview is symbolic because the cubemap decoder did not expose a flat image/contact sheet.")
            painter.end()
            self.preview.setPixmap(canvas)
            try:
                self.info.append("\n🌌 Preview: symbolic Cubemap six-face layout. This is not a flat UV texture preview.")
            except Exception:
                pass

        def preview_texture(self, rec):
            # UBE rule: metadata first, preview only when selected.
            # This creates a small cached thumbnail/preview instead of repeatedly
            # decoding full-size textures while browsing.
            bundle_sha = self.bundle_index.sha256 if self.bundle_index else None
            # Use a larger on-demand cache for atlas inspection.  This keeps
            # normal browsing responsive, but gives the texture viewer enough
            # pixels for useful zoom/pan work on 2048/4096 atlases.
            result = get_texture_preview(rec, bundle_sha, size=2048)
            if not result:
                td = texture_details(rec)
                fmt = td.texture_format if td else ""
                name = td.name if td else rec.name
                self.preview.setText(preview_unavailable_message(fmt, name))
                self.texture_preview_base_pixmap = None
                self.texture_preview_record_path_id = None
                self.texture_preview_texture_size = None
                self.texture_preview_cache_path = None
                self.texture_atlas_overlay = None
                return
            pix = QPixmap(str(result.path))
            if pix.isNull():
                self.preview.setText("Could not load cached texture preview")
                self.texture_preview_base_pixmap = None
                self.texture_preview_record_path_id = None
                self.texture_preview_texture_size = None
                self.texture_preview_cache_path = None
                self.texture_atlas_overlay = None
                return

            td = texture_details(rec)
            new_texture_pid = int(getattr(rec, "path_id", 0) or 0)
            if self.texture_preview_record_path_id != new_texture_pid:
                self.texture_region_select_start = None
                self.texture_region_select_current = None
                self.texture_region_selecting = False
            self.texture_preview_base_pixmap = pix
            self.texture_preview_record_path_id = new_texture_pid
            self.texture_preview_texture_size = (int(td.width), int(td.height)) if td and td.width and td.height else (int(result.width), int(result.height))
            self.texture_preview_cache_path = result.path
            self.texture_atlas_overlay = None
            self.reset_texture_preview_view(redraw=False)
            self._draw_texture_preview_with_overlay(None)
            cache_state = "decoded now" if result.source_was_decoded else "loaded from cache"
            self.info.append(
                f"\n🖼 Preview: {result.width} x {result.height} | mode {result.mode} | "
                f"alpha: {'yes' if result.has_alpha else 'no'} | {cache_state}"
            )
            self.info.append(f"💾 Preview cache: {result.path}")
            self.info.append("🔍 Texture controls: wheel zoom, middle-drag pan, double-click reset, Tab / F11 focus view. Display is capped at 100% of the decoded preview.")

        def _sprite_texture_pptr_for_ui(self, data):
            rd = self._ov_get(data, "m_RD", "rd", "render_data", "m_RenderData", "renderData", default=None)
            if rd is not None:
                tex = self._ov_get(rd, "texture", "m_Texture", "m_Texture2D", "m_AtlasTexture", default=None)
                if tex is not None:
                    return tex
                texs = self._ov_as_list(self._ov_get(rd, "textures", "m_Textures", default=None))
                if texs:
                    return texs[0]
            return self._ov_get(data, "m_Texture", "texture", "m_AtlasTexture", default=None)

        def _sprite_alpha_texture_pptr_for_ui(self, data):
            rd = self._ov_get(data, "m_RD", "rd", "render_data", "m_RenderData", "renderData", default=None)
            if rd is not None:
                tex = self._ov_get(rd, "alphaTexture", "m_AlphaTexture", default=None)
                if tex is not None:
                    return tex
            return self._ov_get(data, "m_AlphaTexture", "alphaTexture", default=None)

        def _hydrate_sprite_external_assets(self, rec) -> None:
            """Hydrate exactly the external Sprite/Texture/Material links needed by Sprite/SpriteRenderer.

            This follows the same lazy PathID-index route as mesh preview/export: it only opens the
            one external bundle that owns the referenced sprite, for example common_assets_all.bundle.
            """
            if rec is None or self.bundle_index is None:
                return
            type_name = getattr(rec, "type_name", "")

            sprite_rec = rec if type_name == "Sprite" else None
            material_pptrs = []

            data = self._ov_read(rec)
            if data is None:
                return

            if type_name == "SpriteRenderer":
                sprite_pptr = self._ov_get(data, "m_Sprite", "sprite", default=None)
                sprite_rec = self._hydrate_pptr_for_preview(sprite_pptr)
                material_pptrs.extend(self._ov_as_list(self._ov_get(data, "m_Materials", "materials", default=None)))

            if sprite_rec is not None and getattr(sprite_rec, "object", None) is not None:
                sdata = self._ov_read(sprite_rec)
                if sdata is not None:
                    self._hydrate_pptr_for_preview(self._sprite_texture_pptr_for_ui(sdata))
                    self._hydrate_pptr_for_preview(self._sprite_alpha_texture_pptr_for_ui(sdata))

            for mat_pptr in material_pptrs:
                mat_rec = self._hydrate_pptr_for_preview(mat_pptr)
                self._hydrate_material_texture_refs_for_preview(mat_rec)

        def _sprite_pptr_from_renderer(self, rec):
            data = self._ov_read(rec)
            if data is None:
                return None
            return self._ov_get(data, "m_Sprite", "sprite", default=None)

        def _sprite_pptr_from_mask(self, rec):
            data = self._ov_read(rec)
            if data is None:
                return None
            # Unity versions expose this as m_Sprite on normal SpriteMask.
            # Some versions also expose mask/source fields, so keep a few
            # tolerant fallbacks for older/variant serialized layouts.
            return self._ov_get(
                data,
                "m_Sprite",
                "sprite",
                "m_MaskSource",
                "maskSource",
                "m_SourceSprite",
                "sourceSprite",
                default=None,
            )

        def preview_sprite_mask(self, rec):
            """Preview the linked Sprite used as the SpriteMask stencil shape."""
            self.preview_stack.setCurrentWidget(self.preview)
            self._hydrate_sprite_external_assets(rec)
            sprite_rec = self._hydrate_pptr_for_preview(self._sprite_pptr_from_mask(rec))
            if sprite_rec is not None and getattr(sprite_rec, "type_name", "") == "Sprite":
                self.preview_sprite(sprite_rec)
                try:
                    self.info.append(
                        f"\n🎭 SpriteMask preview source: {rec.name} -> Sprite {sprite_rec.name}\n"
                        "This image is the invisible stencil/mask shape used by the SpriteMask component."
                    )
                except Exception:
                    pass
            else:
                self.preview_18t_symbolic(rec)
                try:
                    self.info.append(
                        "\n🎭 SpriteMask preview note: linked Sprite could not be resolved, so symbolic preview was used."
                    )
                except Exception:
                    pass

        def preview_sprite(self, rec):
            self.preview_stack.setCurrentWidget(self.preview)
            self._hydrate_sprite_external_assets(rec)
            data = self._ov_read(rec)
            tex_rec = None
            if data is not None:
                tex_rec = self._hydrate_pptr_for_preview(self._sprite_texture_pptr_for_ui(data))
            if tex_rec is not None and getattr(tex_rec, "type_name", "") == "Texture2D":
                self.preview_texture(tex_rec)
                self.info.append(f"\n🖼 Sprite preview source: {rec.name} -> Texture2D {tex_rec.name}")
            else:
                self.preview.setText(f"Sprite\n\n{rec.name}\n\nBacking Texture2D could not be resolved for preview.")

        def preview_sprite_renderer(self, rec):
            self.preview_stack.setCurrentWidget(self.preview)
            self._hydrate_sprite_external_assets(rec)
            sprite_rec = self._hydrate_pptr_for_preview(self._sprite_pptr_from_renderer(rec))
            if sprite_rec is not None:
                self.preview_sprite(sprite_rec)
                self.info.append(f"\n🖼 SpriteRenderer preview source: {rec.name} -> Sprite {sprite_rec.name}")
            else:
                self.preview.setText(f"SpriteRenderer\n\n{rec.name}\n\nSprite reference could not be resolved for preview.")

        def _box_preview_float(self, value, default=None):
            try:
                v = float(value)
            except Exception:
                return default
            try:
                import math
                if not math.isfinite(v):
                    return default
            except Exception:
                pass
            return v

        def _box_preview_vec3(self, value, default=(0.0, 0.0, 0.0)):
            if value is None:
                return tuple(float(x) for x in default)
            if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
                try:
                    return (float(value.x), float(value.y), float(value.z))
                except Exception:
                    return tuple(float(x) for x in default)
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                try:
                    return (float(value[0]), float(value[1]), float(value[2]))
                except Exception:
                    return tuple(float(x) for x in default)
            return tuple(float(x) for x in default)

        def _box_preview_fmt(self, value, digits=3):
            try:
                v = float(value)
                txt = f"{v:.{digits}f}".rstrip("0").rstrip(".")
                if txt == "-0":
                    txt = "0"
                return txt
            except Exception:
                return str(value)


        def _rect_preview_vec2(self, value, default=(0.0, 0.0)):
            if value is None:
                return tuple(float(x) for x in default)
            if hasattr(value, "x") and hasattr(value, "y"):
                try:
                    return (float(value.x), float(value.y))
                except Exception:
                    return tuple(float(x) for x in default)
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                try:
                    return (float(value[0]), float(value[1]))
                except Exception:
                    return tuple(float(x) for x in default)
            return tuple(float(x) for x in default)

        def preview_rect_transform(self, rec):
            """Draw an educational UI-layout rectangle for RectTransform components."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"RectTransform\n\n{rec.name}\n\nCould not read RectTransform data for preview.")
                return

            anchor_min = self._rect_preview_vec2(self._ov_get(data, "m_AnchorMin", "anchorMin", default=None), (0.5, 0.5))
            anchor_max = self._rect_preview_vec2(self._ov_get(data, "m_AnchorMax", "anchorMax", default=None), anchor_min)
            anchored = self._rect_preview_vec2(self._ov_get(data, "m_AnchoredPosition", "anchoredPosition", default=None), (0.0, 0.0))
            size_delta = self._rect_preview_vec2(self._ov_get(data, "m_SizeDelta", "sizeDelta", default=None), (100.0, 100.0))
            pivot = self._rect_preview_vec2(self._ov_get(data, "m_Pivot", "pivot", default=None), (0.5, 0.5))
            local_pos = self._box_preview_vec3(self._ov_get(data, "m_LocalPosition", "localPosition", default=None), (0.0, 0.0, 0.0))

            # Clamp anchors/pivot for display only. We still print the real numbers in the label.
            def clamp01(v):
                try:
                    return max(0.0, min(1.0, float(v)))
                except Exception:
                    return 0.0

            ax0, ay0 = clamp01(anchor_min[0]), clamp01(anchor_min[1])
            ax1, ay1 = clamp01(anchor_max[0]), clamp01(anchor_max[1])
            px, py = clamp01(pivot[0]), clamp01(pivot[1])
            stretch_x = abs(anchor_min[0] - anchor_max[0]) > 0.00001
            stretch_y = abs(anchor_min[1] - anchor_max[1]) > 0.00001

            from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont
            from PySide6.QtCore import QPointF, QRectF, Qt

            view_size = self.preview.size()
            w = max(440, int(view_size.width() or 680))
            h = max(320, int(view_size.height() or 390))
            pix = QPixmap(w, h)
            pix.fill(QColor(30, 32, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 62)
            panel = QColor(64, 70, 78)
            panel_fill = QColor(48, 54, 62)
            anchor_col = QColor(238, 184, 75)
            anchor_fill = QColor(238, 184, 75, 36)
            rect_col = QColor(91, 214, 230)
            rect_fill = QColor(91, 214, 230, 54)
            pivot_col = QColor(240, 240, 245)
            text = QColor(232, 236, 240)
            muted = QColor(166, 174, 181)
            green = QColor(112, 214, 130)
            red = QColor(230, 105, 105)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "RectTransform layout")
            painter.setFont(QFont("Segoe UI", 9))
            mode = "stretch both axes" if stretch_x and stretch_y else "stretch X" if stretch_x else "stretch Y" if stretch_y else "fixed anchor"
            painter.setPen(muted)
            painter.drawText(
                22,
                58,
                f"{mode}  •  anchor {self._box_preview_fmt(anchor_min[0])},{self._box_preview_fmt(anchor_min[1])} → {self._box_preview_fmt(anchor_max[0])},{self._box_preview_fmt(anchor_max[1])}  •  pivot {self._box_preview_fmt(pivot[0])},{self._box_preview_fmt(pivot[1])}",
            )

            # Main parent Canvas/panel rectangle.
            parent_w = min(w - 150, 520)
            parent_h = min(h - 135, 300)
            parent_w = max(320, parent_w)
            parent_h = max(190, parent_h)
            left = (w - parent_w) * 0.5
            top = 86
            parent_rect = QRectF(left, top, parent_w, parent_h)

            painter.setPen(QPen(panel, 2))
            painter.setBrush(QBrush(panel_fill))
            painter.drawRoundedRect(parent_rect, 8, 8)
            painter.setPen(QPen(QColor(95, 103, 112), 1, Qt.DashLine))
            painter.drawLine(QPointF(left + parent_w * 0.5, top), QPointF(left + parent_w * 0.5, top + parent_h))
            painter.drawLine(QPointF(left, top + parent_h * 0.5), QPointF(left + parent_w, top + parent_h * 0.5))

            def panel_point(u, v):
                # Unity anchor V is bottom=0, top=1. Qt Y grows downward.
                return QPointF(left + u * parent_w, top + (1.0 - v) * parent_h)

            # Anchor area/pin.
            a_tl = panel_point(min(ax0, ax1), max(ay0, ay1))
            a_br = panel_point(max(ax0, ax1), min(ay0, ay1))
            anchor_rect = QRectF(a_tl, a_br).normalized()
            painter.setPen(QPen(anchor_col, 2, Qt.DashLine if (stretch_x or stretch_y) else Qt.SolidLine))
            painter.setBrush(QBrush(anchor_fill))
            if anchor_rect.width() > 2 and anchor_rect.height() > 2:
                painter.drawRect(anchor_rect)
            else:
                ap = panel_point(ax0, ay0)
                painter.drawLine(QPointF(ap.x() - 14, ap.y()), QPointF(ap.x() + 14, ap.y()))
                painter.drawLine(QPointF(ap.x(), ap.y() - 14), QPointF(ap.x(), ap.y() + 14))
                painter.setBrush(QBrush(anchor_col))
                painter.drawEllipse(ap, 3.5, 3.5)

            # Estimate the actual UI rectangle. This is educational, not a full Unity layout solve.
            # Virtual parent size grows when large offsets/sizes are present so the rect stays visible.
            sdw, sdh = abs(size_delta[0]), abs(size_delta[1])
            offx, offy = abs(anchored[0]), abs(anchored[1])
            virtual_w = max(800.0, sdw * 2.2 + offx * 2.0, 1.0)
            virtual_h = max(520.0, sdh * 2.2 + offy * 2.0, 1.0)
            unit_scale = min(parent_w / virtual_w, parent_h / virtual_h)

            if stretch_x or stretch_y:
                # Start from the anchor rectangle, then add sizeDelta and anchoredPosition approximately.
                anchor_c = panel_point((ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5)
                rect_w = max(8.0, abs(ax1 - ax0) * parent_w + size_delta[0] * unit_scale)
                rect_h = max(8.0, abs(ay1 - ay0) * parent_h + size_delta[1] * unit_scale)
                pivot_pos = QPointF(anchor_c.x() + anchored[0] * unit_scale, anchor_c.y() - anchored[1] * unit_scale)
            else:
                anchor_p = panel_point(ax0, ay0)
                rect_w = max(8.0, sdw * unit_scale)
                rect_h = max(8.0, sdh * unit_scale)
                pivot_pos = QPointF(anchor_p.x() + anchored[0] * unit_scale, anchor_p.y() - anchored[1] * unit_scale)

            elem_left = pivot_pos.x() - px * rect_w
            elem_bottom = pivot_pos.y() + py * rect_h
            elem_top = elem_bottom - rect_h
            elem_rect = QRectF(elem_left, elem_top, rect_w, rect_h)

            painter.setPen(QPen(rect_col, 2.4))
            painter.setBrush(QBrush(rect_fill))
            painter.drawRoundedRect(elem_rect, 4, 4)
            painter.setPen(QPen(QColor(rect_col.red(), rect_col.green(), rect_col.blue(), 150), 1))
            painter.drawLine(QPointF(elem_rect.left(), pivot_pos.y()), QPointF(elem_rect.right(), pivot_pos.y()))
            painter.drawLine(QPointF(pivot_pos.x(), elem_rect.top()), QPointF(pivot_pos.x(), elem_rect.bottom()))
            painter.setPen(QPen(QColor(20, 20, 20), 1))
            painter.setBrush(QBrush(pivot_col))
            painter.drawEllipse(pivot_pos, 5, 5)

            # Draw a small vector from local origin/anchor to pivot when offset exists.
            if not (abs(anchored[0]) < 0.001 and abs(anchored[1]) < 0.001):
                base_p = panel_point((ax0 + ax1) * 0.5, (ay0 + ay1) * 0.5) if (stretch_x or stretch_y) else panel_point(ax0, ay0)
                painter.setPen(QPen(QColor(235, 235, 235, 150), 1.4))
                painter.drawLine(base_p, pivot_pos)

            # Small axis guide for UI space.
            ax_base = QPointF(left + 34, top + parent_h - 28)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(red, 2))
            painter.drawLine(ax_base, QPointF(ax_base.x() + 42, ax_base.y())); painter.drawText(QPointF(ax_base.x() + 47, ax_base.y() + 4), "+X")
            painter.setPen(QPen(green, 2))
            painter.drawLine(ax_base, QPointF(ax_base.x(), ax_base.y() - 42)); painter.drawText(QPointF(ax_base.x() - 10, ax_base.y() - 48), "+Y")

            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 42, f"anchored position {self._box_preview_fmt(anchored[0])}, {self._box_preview_fmt(anchored[1])}  •  size delta {self._box_preview_fmt(size_delta[0])} × {self._box_preview_fmt(size_delta[1])}")
            painter.drawText(22, h - 22, "Approximate UI rectangle: parent panel, anchor box/pin, element rect and pivot dot. Final layout may depend on parent Canvas/RectTransform.")
            painter.end()

            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n▭ Preview: approximate RectTransform UI layout drawn from anchors, size delta, anchored position and pivot.")

        def preview_navmesh(self, rec):
            """Symbolic educational preview for NavMeshData/settings."""
            self.preview_stack.setCurrentWidget(self.preview)
            try:
                data = self._ov_read(rec)
            except Exception:
                data = None

            def get(*names, default=None):
                return self._ov_get(data, *names, default=default) if data is not None else default

            def list_count(value):
                try:
                    if value is None:
                        return None
                    if isinstance(value, (list, tuple, dict)):
                        return len(value)
                    if hasattr(value, "__len__") and not isinstance(value, (str, bytes, bytearray)):
                        return len(value)
                except Exception:
                    pass
                return None

            tiles = get("m_NavMeshTiles", "navMeshTiles", "m_Tiles", "tiles", default=None)
            links = get("m_OffMeshLinks", "offMeshLinks", "m_Links", "links", default=None)
            sources = get("m_Sources", "sources", "m_NavMeshSources", "navMeshSources", default=None)
            tile_count = list_count(tiles)
            link_count = list_count(links)
            source_count = list_count(sources)

            from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QPolygonF
            from PySide6.QtCore import QPointF, Qt

            view_size = self.preview.size()
            w = max(520, int(view_size.width() or 760))
            h = max(360, int(view_size.height() or 430))
            pix = QPixmap(w, h)
            pix.fill(QColor(30, 34, 33))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(48, 56, 54)
            walk_fill = QColor(75, 170, 104, 76)
            walk_edge = QColor(108, 226, 138)
            area_alt = QColor(232, 188, 84, 70)
            obstacle = QColor(94, 94, 94, 170)
            path_blue = QColor(98, 176, 240)
            text = QColor(232, 236, 236)
            muted = QColor(166, 176, 174)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 15, QFont.Bold))
            painter.setPen(text)
            title = "NavMeshData walking surface" if rec.type_name == "NavMeshData" else friendly_type_name(rec.type_name)
            painter.drawText(22, 36, title)

            bits = []
            if tile_count is not None:
                bits.append(f"{tile_count:,} tile(s)")
            if source_count is not None:
                bits.append(f"{source_count:,} source(s)")
            if link_count is not None:
                bits.append(f"{link_count:,} off-mesh link(s)")
            if not bits:
                bits.append("symbolic pathfinding preview")
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(bits))

            cx = w * 0.52
            cy = h * 0.54
            s = min(w, h) * 0.30

            pts = [
                QPointF(cx - 1.35*s, cy - 0.40*s),
                QPointF(cx - 0.75*s, cy - 0.95*s),
                QPointF(cx + 0.20*s, cy - 0.70*s),
                QPointF(cx + 1.20*s, cy - 0.35*s),
                QPointF(cx + 1.00*s, cy + 0.65*s),
                QPointF(cx + 0.05*s, cy + 0.95*s),
                QPointF(cx - 0.95*s, cy + 0.55*s),
            ]
            tris = [(0, 1, 6), (1, 2, 6), (2, 5, 6), (2, 3, 5), (3, 4, 5)]

            painter.setBrush(QBrush(walk_fill))
            painter.setPen(QPen(walk_edge, 1.6))
            for tri in tris:
                painter.drawPolygon(QPolygonF([pts[tri[0]], pts[tri[1]], pts[tri[2]]]))

            painter.setBrush(QBrush(area_alt))
            painter.setPen(QPen(QColor(232, 188, 84), 1.2, Qt.DashLine))
            painter.drawPolygon(QPolygonF([pts[2], pts[3], pts[5]]))

            painter.setBrush(QBrush(obstacle))
            painter.setPen(QPen(QColor(130, 130, 130), 1.4))
            painter.drawRoundedRect(int(cx - 0.18*s), int(cy - 0.20*s), int(0.38*s), int(0.35*s), 8, 8)

            route = [
                QPointF(cx - 1.05*s, cy + 0.28*s),
                QPointF(cx - 0.55*s, cy - 0.10*s),
                QPointF(cx + 0.08*s, cy - 0.05*s),
                QPointF(cx + 0.62*s, cy + 0.28*s),
            ]
            painter.setPen(QPen(path_blue, 3.0))
            for a, b in zip(route, route[1:]):
                painter.drawLine(a, b)
            painter.setBrush(QBrush(path_blue))
            painter.setPen(Qt.NoPen)
            for p in route:
                painter.drawEllipse(p, 4, 4)

            if link_count is None or link_count:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor(245, 145, 105), 2.0, Qt.DashLine))
                painter.drawArc(int(cx - 0.30*s), int(cy - 0.92*s), int(0.90*s), int(0.75*s), 20 * 16, 145 * 16)
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor(245, 178, 140))
                painter.drawText(QPointF(cx + 0.18*s, cy - 0.62*s), "off-mesh link / jump")

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(text)
            painter.drawText(22, h - 72, "Green triangles = walkable surface used by AI path queries")
            painter.setPen(QColor(232, 188, 84))
            painter.drawText(22, h - 50, "Gold region = different area/cost type")
            painter.setPen(path_blue)
            painter.drawText(22, h - 28, "Blue route = example path across the navmesh")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append(
                "\n🧭 Preview: symbolic NavMesh walking/pathfinding surface. "
                "It explains the role of the data; it is not yet a decoded real navmesh triangle overlay."
            )


        def preview_avatar(self, rec):
            """Symbolic preview for Unity Avatar rig-mapping assets."""
            self.preview_stack.setCurrentWidget(self.preview)
            name = str(getattr(rec, "name", "") or "Avatar")
            low = name.lower()
            if "hand" in low or "oculus" in low or "quest" in low or "controller" in low:
                role = "hand / controller rig"
            elif any(k in low for k in ("mario", "luigi", "yoshi", "kong", "robot", "character", "player", "talking")):
                role = "character animation rig"
            else:
                role = "animation rig mapping"

            w = max(640, self.preview.width() if self.preview.width() > 0 else 720)
            h = max(420, self.preview.height() if self.preview.height() > 0 else 480)
            pix = QPixmap(w, h)
            pix.fill(QColor("#17191f"))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            card = QRectF(28, 28, w - 56, h - 56)
            painter.setPen(QPen(QColor("#4d5462"), 1))
            painter.setBrush(QBrush(QColor("#242936")))
            painter.drawRoundedRect(card, 14, 14)
            painter.setFont(QFont("Segoe UI", 20, QFont.Bold))
            painter.setPen(QColor("#f3f6ff"))
            painter.drawText(int(card.left() + 24), int(card.top() + 42), f"🦴 {name}")
            painter.setFont(QFont("Segoe UI", 11))
            painter.setPen(QColor("#b9c3d6"))
            painter.drawText(int(card.left() + 26), int(card.top() + 70), f"Unity Avatar • {role}")

            cx = int(card.left() + card.width() * 0.33)
            top = int(card.top() + 128)
            scale = min(card.width(), card.height()) / 420.0
            def P(x, y):
                return QPointF(cx + x * scale, top + y * scale)
            painter.setPen(QPen(QColor("#8fd0ff"), max(2, int(3 * scale))))
            bones = [((0,0),(0,45)),((0,45),(0,112)),((0,70),(-65,45)),((-65,45),(-112,82)),((0,70),(65,45)),((65,45),(112,82)),((0,112),(-45,185)),((-45,185),(-35,250)),((0,112),(45,185)),((45,185),(35,250))]
            for a,b in bones:
                painter.drawLine(P(*a), P(*b))
            painter.setPen(QPen(QColor("#2f6c9a"), 1))
            painter.setBrush(QBrush(QColor("#d7f1ff")))
            for x,y in [(0,0),(0,45),(0,70),(0,112),(-65,45),(-112,82),(65,45),(112,82),(-45,185),(-35,250),(45,185),(35,250)]:
                r=6*scale; p=P(x,y); painter.drawEllipse(QRectF(p.x()-r,p.y()-r,r*2,r*2))
            painter.setPen(QPen(QColor("#ffd36a"), max(2, int(2 * scale))))
            painter.setBrush(QBrush(QColor("#384151")))
            head=P(0,-28); painter.drawEllipse(QRectF(head.x()-24*scale, head.y()-24*scale, 48*scale, 48*scale))

            panel_x = int(card.left() + card.width() * 0.55)
            # Keep the explanatory column comfortably inside the card even when
            # the preview area is relatively shallow.  The earlier generous
            # spacing allowed the final Debug entries to collide with the lower
            # caption after KeepAspectRatio scaling.
            y = int(card.top() + 102)
            painter.setFont(QFont("Segoe UI", 13, QFont.Bold)); painter.setPen(QColor("#ffffff")); painter.drawText(panel_x, y, "Avatar means rig mapping")
            y += 30
            painter.setFont(QFont("Segoe UI", 10)); painter.setPen(QColor("#c8d1df"))
            for line in ["Not a visible mesh or texture.", "Used by Animator / Mecanim.", "Maps skeleton bones to animation roles.", "May support humanoid retargeting.", "Hand/controller rigs use the same asset type."]:
                painter.drawText(panel_x, y, "• " + line); y += 23
            y += 8
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold)); painter.setPen(QColor("#ffd36a")); painter.drawText(panel_x, y, "Debug with:"); y += 22
            painter.setFont(QFont("Segoe UI", 10)); painter.setPen(QColor("#d7e6ff"))
            for line in ["Animator", "SkinnedMeshRenderer", "Bones / Transforms", "AnimationClip"]:
                painter.drawText(panel_x, y, "  " + line); y += 21
            painter.setFont(QFont("Segoe UI", 9)); painter.setPen(QColor("#8f98a8"))
            painter.drawText(int(card.left() + 28), int(card.bottom() - 24), "Symbolic preview only — Avatar stores rig metadata, not renderable geometry.")
            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n🦴 Preview: symbolic Avatar rig-mapping card.")

        def _font_bytes_from_data(self, data):
            if data is None:
                return None
            for name in ("m_FontData", "font_data", "fontData", "m_Data", "data"):
                value = self._ov_get(data, name, default=None)
                if isinstance(value, bytes):
                    return value
                if isinstance(value, bytearray):
                    return bytes(value)
                if isinstance(value, memoryview):
                    return value.tobytes()
                if isinstance(value, list):
                    try:
                        if value and all(isinstance(x, int) for x in value[:32]):
                            return bytes(max(0, min(255, int(x))) for x in value)
                    except Exception:
                        pass
            return None

        def preview_font(self, rec):
            """Draw a practical font sample card.

            This is intentionally not a full Unity/TMP font renderer.  It gives a
            developer/learner an immediate visual clue: font family, embedded
            data status, alphabet/numbers/pangram and common UI glyphs.
            """
            self.preview_stack.setCurrentWidget(self.preview)

            data = self._ov_read(rec)
            name = str(getattr(rec, "name", "") or "Font")
            font_data = self._font_bytes_from_data(data)
            loaded_family = ""
            loaded_note = "system fallback"

            if font_data:
                try:
                    font_id = QFontDatabase.addApplicationFontFromData(QByteArray(font_data))
                    if font_id >= 0:
                        families = QFontDatabase.applicationFontFamilies(font_id)
                        if families:
                            loaded_family = families[0]
                            loaded_note = "loaded embedded font bytes"
                except Exception:
                    loaded_family = ""

            if not loaded_family:
                # Asset names often use underscores.  Try a friendly family name
                # first, then let Qt fallback if it is not installed.
                loaded_family = name.replace("_Regular", "").replace("_", " ")

            w = max(640, self.preview.width() if self.preview.width() > 0 else 720)
            h = max(420, self.preview.height() if self.preview.height() > 0 else 480)
            pix = QPixmap(w, h)
            pix.fill(QColor("#181a1f"))

            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            card = QRectF(28, 28, w - 56, h - 56)
            painter.setPen(QPen(QColor("#4a4f59"), 1))
            painter.setBrush(QBrush(QColor("#242832")))
            painter.drawRoundedRect(card, 14, 14)

            title_font = QFont("Segoe UI", 20, QFont.Bold)
            painter.setFont(title_font)
            painter.setPen(QColor("#f4f4f4"))
            painter.drawText(int(card.left() + 24), int(card.top() + 42), f"🔠 {name}")

            meta_font = QFont("Segoe UI", 10)
            painter.setFont(meta_font)
            painter.setPen(QColor("#b8c0cc"))
            size_text = f"{len(font_data):,} bytes" if font_data else "not exposed"
            painter.drawText(int(card.left() + 26), int(card.top() + 68), f"Preview font: {loaded_family}  •  {loaded_note}  •  embedded data: {size_text}")

            sample_family = loaded_family
            y = int(card.top() + 124)

            def draw_sample(text, size, bold=False, colour="#f2f2f2", dy=56):
                nonlocal y
                f = QFont(sample_family, size)
                f.setBold(bool(bold))
                painter.setFont(f)
                painter.setPen(QColor(colour))
                painter.drawText(int(card.left() + 28), y, text)
                y += dy

            draw_sample("The quick brown fox jumps over the lazy dog", 24, False, "#ffffff", 58)
            draw_sample("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 18, False, "#dfe8ff", 42)
            draw_sample("abcdefghijklmnopqrstuvwxyz", 18, False, "#dfe8ff", 42)
            draw_sample("0123456789  ! ? @ # £ $ % & * ( ) [ ]", 17, False, "#d8ffe0", 42)
            draw_sample("Unity UI  •  Score: 12345  •  Player_01", 18, True, "#ffd980", 46)

            # Glyph strip
            painter.setFont(QFont(sample_family, 30))
            painter.setPen(QColor("#ffffff"))
            strip = "Aa Bb Cc 123"
            painter.drawText(int(card.left() + 28), int(card.bottom() - 52), strip)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#8f98a8"))
            painter.drawText(int(card.left() + 28), int(card.bottom() - 22), "Font preview is approximate; Unity/TMP may use atlas materials, glyph rects, fallback fonts or runtime dynamic rendering.")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append(f"\n🔠 Preview: font sample card using {loaded_note}.")

        def preview_18t_symbolic(self, rec):
            """Simple educational preview card for non-mesh inspectors added in v1.8t."""
            self.preview_stack.setCurrentWidget(self.preview)
            t = getattr(rec, "type_name", "")
            name = getattr(rec, "name", "")
            try:
                data = self._ov_read(rec)
            except Exception:
                data = None

            def get(*names, default=None):
                return self._ov_get(data, *names, default=default) if data is not None else default

            lines = [f"{friendly_type_name(t)}", "", str(name), ""]
            if t == "SpriteMask":
                lines.extend([
                    "2D sprite masking/stencil component.",
                    "",
                    "It usually does not draw anything itself.",
                    "It defines where matching SpriteRenderers are allowed to appear.",
                ])
                sprite = get("m_Sprite", "sprite", default=None)
                if sprite is not None:
                    lines.append("")
                    lines.append(f"Mask sprite reference: {sprite}")
            elif t == "LineRenderer":
                lines.extend([
                    "Runtime/generated line ribbon.",
                    "",
                    "Common uses: lasers, ropes, path guides, aim lines, debug rays.",
                ])
                positions = get("m_Positions", "positions", default=None)
                try:
                    lines.append(f"Saved positions: {len(positions)}")
                except Exception:
                    pass
            elif t == "TrailRenderer":
                lines.extend([
                    "Runtime/generated trail ribbon.",
                    "",
                    "Common uses: motion streaks, sword trails, projectile trails, smoke/energy ribbons.",
                ])
                time = get("m_Time", "time", default=None)
                if time is not None:
                    lines.append(f"Trail lifetime/time: {time}")
            elif t == "Rigidbody":
                lines.extend([
                    "Physics body.",
                    "",
                    "Colliders define the shape; Rigidbody defines mass, gravity, kinematic/simulated behaviour and collision movement.",
                ])
                for label, names in (("Mass", ("m_Mass", "mass")), ("Use gravity", ("m_UseGravity", "useGravity")), ("Kinematic", ("m_IsKinematic", "isKinematic"))):
                    value = get(*names, default=None)
                    if value is not None:
                        lines.append(f"{label}: {value}")
            elif t in ("SphereCollider", "CapsuleCollider", "MeshCollider"):
                lines.extend([
                    "Invisible physics/trigger volume.",
                    "",
                    "This affects collision, clicking, blocking or trigger events; it is not the visible mesh.",
                ])
                radius = get("m_Radius", "radius", default=None)
                height = get("m_Height", "height", default=None)
                if radius is not None:
                    lines.append(f"Radius: {radius}")
                if height is not None:
                    lines.append(f"Height: {height}")
            elif t == "PhysicMaterial":
                lines.extend([
                    "Physics surface material.",
                    "",
                    "Controls friction and bounce when used by Collider components.",
                ])
            elif t == "TextAsset":
                lines.extend([
                    "Text/config/data asset.",
                    "",
                    "The inspector below shows a readable text or hex preview where possible.",
                ])
                try:
                    script = get("m_Script", "script", "m_Data", "data", default=None)
                    if isinstance(script, str):
                        sample = script[:500]
                    elif isinstance(script, (bytes, bytearray)):
                        sample = bytes(script[:500]).decode("utf-8", "replace")
                    else:
                        sample = ""
                    if sample:
                        lines.extend(["", "Preview:", sample])
                except Exception:
                    pass
            elif t == "PlayableDirector":
                lines.extend([
                    "Timeline / Playable controller.",
                    "",
                    "It can drive cutscenes, camera moves, audio cues, object activation and higher-level animation sequences.",
                ])
            else:
                lines.append("Symbolic preview for this inspector type.")

            self.preview.setText("\n".join(lines))


        def _collider_preview_base(self, title: str, rec, extra_bits: list[str] | None = None):
            """Create a common QPixmap/painter and style colours for collider previews."""
            from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont
            from PySide6.QtCore import QPointF, Qt

            view_size = self.preview.size()
            w = max(420, int(view_size.width() or 640))
            h = max(300, int(view_size.height() or 360))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            colours = {
                "bg_grid": QColor(52, 56, 60),
                "cyan": QColor(88, 210, 224),
                "cyan_soft": QColor(88, 210, 224, 42),
                "cyan_mid": QColor(88, 210, 224, 118),
                "amber": QColor(232, 184, 88),
                "amber_soft": QColor(232, 184, 88, 46),
                "red": QColor(216, 100, 100),
                "text": QColor(230, 234, 238),
                "muted": QColor(166, 174, 181),
                "axis_x": QColor(230, 105, 105),
                "axis_y": QColor(112, 214, 130),
                "axis_z": QColor(115, 156, 238),
            }

            painter.setPen(QPen(colours["bg_grid"], 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(colours["text"])
            painter.drawText(22, 36, title)

            if extra_bits:
                painter.setFont(QFont("Segoe UI", 9))
                painter.setPen(colours["muted"])
                painter.drawText(22, 58, "  •  ".join(str(x) for x in extra_bits if x))

            # Local axes glyph.
            ax0 = QPointF(70, h - 70)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(colours["axis_x"], 2))
            painter.drawLine(ax0, QPointF(ax0.x() + 38, ax0.y() + 13)); painter.drawText(QPointF(ax0.x() + 43, ax0.y() + 18), "X")
            painter.setPen(QPen(colours["axis_y"], 2))
            painter.drawLine(ax0, QPointF(ax0.x(), ax0.y() - 42)); painter.drawText(QPointF(ax0.x() - 8, ax0.y() - 48), "Y")
            painter.setPen(QPen(colours["axis_z"], 2))
            painter.drawLine(ax0, QPointF(ax0.x() - 34, ax0.y() + 18)); painter.drawText(QPointF(ax0.x() - 48, ax0.y() + 25), "Z")

            return pix, painter, colours, w, h

        def preview_sphere_collider(self, rec):
            """Draw a scaled local-space sphere collider volume."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"SphereCollider\n\n{rec.name}\n\nCould not read SphereCollider data for preview.")
                return

            center = self._box_preview_vec3(self._ov_get(data, "m_Center", "center", default=None), (0.0, 0.0, 0.0))
            radius = abs(self._box_preview_float(self._ov_get(data, "m_Radius", "radius", default=1.0), 1.0) or 1.0)
            if radius <= 0.000001:
                radius = 1.0
            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)
            is_trigger = bool(self._ov_get(data, "m_IsTrigger", "isTrigger", default=False))

            bits = [
                f"radius {self._box_preview_fmt(radius)}",
                f"diameter {self._box_preview_fmt(radius * 2.0)}",
                f"center {self._box_preview_fmt(center[0])}, {self._box_preview_fmt(center[1])}, {self._box_preview_fmt(center[2])}",
                "trigger" if is_trigger else "solid collider",
            ]
            if enabled is not None and not bool(enabled):
                bits.append("disabled")

            pix, painter, c, w, h = self._collider_preview_base("SphereCollider volume", rec, bits)
            from PySide6.QtGui import QColor, QPen, QBrush, QFont
            from PySide6.QtCore import QPointF, Qt

            edge = c["amber"] if is_trigger else c["cyan"]
            fill = c["amber_soft"] if is_trigger else c["cyan_soft"]
            pen = QPen(edge, 2.2)
            if is_trigger:
                pen.setStyle(Qt.DashLine)

            # Fit sphere and offset origin line into preview.
            max_extent = max(radius * 2.0, abs(center[0]) + radius, abs(center[1]) + radius, abs(center[2]) + radius, 0.000001)
            scale = min(w * 0.30, h * 0.34) / max_extent
            cx = w * 0.52
            cy = h * 0.56

            def project(pt):
                x, y, z = pt
                px = cx + (x - z) * scale * 0.86
                py = cy + (x + z) * scale * 0.34 - y * scale * 0.92
                return QPointF(px, py)

            origin = project((0.0, 0.0, 0.0))
            sphere_center = project(center)
            r_px = max(12.0, radius * scale)

            # Offset line from local origin to collider center.
            painter.setPen(QPen(QColor(210, 210, 210, 150), 1.2))
            painter.drawLine(origin, sphere_center)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(edge.red(), edge.green(), edge.blue(), 90), 1.2))
            # Three great circles: front circle plus two ellipses as sphere cues.
            painter.drawEllipse(sphere_center, r_px, r_px)
            painter.drawEllipse(sphere_center, r_px, r_px * 0.34)
            painter.drawEllipse(sphere_center, r_px * 0.34, r_px)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(pen)
            painter.drawEllipse(sphere_center, r_px, r_px)

            painter.setPen(QPen(edge, 1.6))
            painter.drawLine(QPointF(sphere_center.x() - r_px, sphere_center.y()), QPointF(sphere_center.x() + r_px, sphere_center.y()))
            painter.drawText(QPointF(sphere_center.x() + r_px + 8, sphere_center.y() - 4), f"r {self._box_preview_fmt(radius)}")

            painter.setBrush(QBrush(QColor(230, 230, 230)))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(sphere_center, 4, 4)
            painter.setBrush(QBrush(QColor(110, 110, 110)))
            painter.drawEllipse(origin, 3, 3)

            painter.setPen(c["muted"])
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 24, "Invisible local-space sphere used for collision, trigger volumes, range/detection zones and simple physics contact.")
            if enabled is not None and not bool(enabled):
                painter.setPen(c["red"])
                painter.drawText(w - 200, h - 24, "SphereCollider disabled")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n◯ Preview: scaled SphereCollider wire sphere drawn from local center and radius fields.")

        def preview_capsule_collider(self, rec):
            """Draw a scaled local-space capsule collider volume."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"CapsuleCollider\n\n{rec.name}\n\nCould not read CapsuleCollider data for preview.")
                return

            center = self._box_preview_vec3(self._ov_get(data, "m_Center", "center", default=None), (0.0, 0.0, 0.0))
            radius = abs(self._box_preview_float(self._ov_get(data, "m_Radius", "radius", default=0.5), 0.5) or 0.5)
            height = abs(self._box_preview_float(self._ov_get(data, "m_Height", "height", default=2.0), 2.0) or 2.0)
            direction = int(self._box_preview_float(self._ov_get(data, "m_Direction", "direction", default=1), 1) or 1)
            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)
            is_trigger = bool(self._ov_get(data, "m_IsTrigger", "isTrigger", default=False))
            axis_name = {0: "X", 1: "Y", 2: "Z"}.get(direction, "Y")

            bits = [
                f"radius {self._box_preview_fmt(radius)}",
                f"height {self._box_preview_fmt(height)}",
                f"axis {axis_name}",
                f"center {self._box_preview_fmt(center[0])}, {self._box_preview_fmt(center[1])}, {self._box_preview_fmt(center[2])}",
                "trigger" if is_trigger else "solid collider",
            ]
            if enabled is not None and not bool(enabled):
                bits.append("disabled")

            pix, painter, c, w, h = self._collider_preview_base("CapsuleCollider volume", rec, bits)
            from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainterPath
            from PySide6.QtCore import QPointF, QRectF, Qt

            edge = c["amber"] if is_trigger else c["cyan"]
            fill = c["amber_soft"] if is_trigger else c["cyan_soft"]
            pen = QPen(edge, 2.2)
            if is_trigger:
                pen.setStyle(Qt.DashLine)

            scale = min(w * 0.30, h * 0.42) / max(height, radius * 2.0, 0.000001)
            body_h = max(0.0, height - radius * 2.0) * scale
            r_px = max(10.0, radius * scale)

            cx = w * 0.52 + center[0] * scale * 0.32 - center[2] * scale * 0.32
            cy = h * 0.56 - center[1] * scale * 0.45

            # 2D schematic: true orientation in text, clean vertical capsule in drawing.
            top = cy - body_h / 2.0 - r_px
            left = cx - r_px
            width = r_px * 2.0
            total_h = body_h + r_px * 2.0

            path = QPainterPath()
            path.moveTo(cx, top)
            path.arcTo(QRectF(left, top, width, width), 90, 180)
            path.lineTo(left, top + r_px + body_h)
            path.arcTo(QRectF(left, top + body_h, width, width), 180, 180)
            path.lineTo(cx + r_px, top + r_px)
            path.closeSubpath()

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(edge.red(), edge.green(), edge.blue(), 90), 1.2))
            painter.drawPath(path)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(pen)
            painter.drawPath(path)

            painter.setPen(QPen(edge, 1.6))
            painter.drawLine(QPointF(cx, top), QPointF(cx, top + total_h))
            painter.drawText(QPointF(cx + r_px + 10, cy), f"h {self._box_preview_fmt(height)}")
            painter.drawLine(QPointF(cx, top + total_h * 0.28), QPointF(cx + r_px, top + total_h * 0.28))
            painter.drawText(QPointF(cx + r_px + 8, top + total_h * 0.28 - 4), f"r {self._box_preview_fmt(radius)}")

            # Local origin and collider center hint.
            painter.setBrush(QBrush(QColor(230, 230, 230)))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(QPointF(cx, cy), 4, 4)

            painter.setPen(c["muted"])
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 24, f"Invisible capsule collider. Direction field says the capsule is aligned to local {axis_name}.")
            if enabled is not None and not bool(enabled):
                painter.setPen(c["red"])
                painter.drawText(w - 205, h - 24, "CapsuleCollider disabled")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n⬭ Preview: scaled CapsuleCollider schematic drawn from local center, radius, height and direction fields.")

        def preview_mesh_collider(self, rec):
            """Preview a MeshCollider by following its linked Mesh when possible."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"MeshCollider\n\n{rec.name}\n\nCould not read MeshCollider data for preview.")
                return
            mesh_pptr = self._ov_get(data, "m_Mesh", "mesh", default=None)
            mesh_rec = self._hydrate_pptr_for_preview(mesh_pptr)
            convex = self._ov_get(data, "m_Convex", "convex", default=None)
            is_trigger = self._ov_get(data, "m_IsTrigger", "isTrigger", default=None)
            if mesh_rec is not None and getattr(mesh_rec, "type_name", "") == "Mesh":
                self.preview_mesh(mesh_rec)
                self.info.append(
                    f"\n▧ MeshCollider preview source: {rec.name} -> collision Mesh {mesh_rec.name}\n"
                    f"Convex: {convex}   Trigger: {is_trigger}\n"
                    "This is the collision mesh reference, not necessarily the visible artwork mesh."
                )
                return

            self.preview_18t_symbolic(rec)
            self.info.append("\n▧ MeshCollider preview note: linked collision Mesh could not be resolved, so symbolic preview was used.")


        def preview_box_collider(self, rec):
            """Draw a simple CAD-style 3D box for BoxCollider components."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"BoxCollider\n\n{rec.name}\n\nCould not read BoxCollider data for preview.")
                return

            center = self._box_preview_vec3(self._ov_get(data, "m_Center", "center", default=None), (0.0, 0.0, 0.0))
            size = self._box_preview_vec3(self._ov_get(data, "m_Size", "size", default=None), (1.0, 1.0, 1.0))
            size = tuple(abs(float(x)) for x in size)
            if max(size) <= 0.000001:
                size = (1.0, 1.0, 1.0)
            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)
            is_trigger = bool(self._ov_get(data, "m_IsTrigger", "isTrigger", default=False))

            from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont
            from PySide6.QtCore import QPointF, Qt

            view_size = self.preview.size()
            w = max(420, int(view_size.width() or 640))
            h = max(300, int(view_size.height() or 360))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 60)
            cyan = QColor(88, 210, 224)
            cyan_soft = QColor(88, 210, 224, 42)
            cyan_mid = QColor(88, 210, 224, 118)
            amber = QColor(232, 184, 88)
            red = QColor(216, 100, 100)
            text = QColor(230, 234, 238)
            muted = QColor(166, 174, 181)
            axis_x = QColor(230, 105, 105)
            axis_y = QColor(112, 214, 130)
            axis_z = QColor(115, 156, 238)

            # Subtle grid background, like the camera frustum preview.
            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "BoxCollider volume")

            painter.setFont(QFont("Segoe UI", 9))
            bits = [
                f"size {self._box_preview_fmt(size[0])} × {self._box_preview_fmt(size[1])} × {self._box_preview_fmt(size[2])}",
                f"center {self._box_preview_fmt(center[0])}, {self._box_preview_fmt(center[1])}, {self._box_preview_fmt(center[2])}",
                "trigger" if is_trigger else "solid collider",
            ]
            if enabled is not None and not bool(enabled):
                bits.append("disabled")
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(bits))

            sx, sy, sz = size
            hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
            corners = {
                "lll": (-hx, -hy, -hz), "rll": ( hx, -hy, -hz), "rrl": ( hx, -hy,  hz), "lrl": (-hx, -hy,  hz),
                "llu": (-hx,  hy, -hz), "rlu": ( hx,  hy, -hz), "rru": ( hx,  hy,  hz), "lru": (-hx,  hy,  hz),
            }

            # Fit the real collider proportions into the available preview area.
            max_dim = max(sx, sy, sz, 0.000001)
            base_scale = min(w * 0.30, h * 0.34) / max_dim
            cx = w * 0.50
            cy = h * 0.57

            def project(pt):
                x, y, z = pt
                # Simple isometric projection, centered on local collider center.
                px = cx + (x - z) * base_scale * 0.86
                py = cy + (x + z) * base_scale * 0.34 - y * base_scale * 0.92
                return QPointF(px, py)

            p = {name: project(val) for name, val in corners.items()}
            faces = [
                ("top", [p["llu"], p["rlu"], p["rru"], p["lru"]]),
                ("left", [p["lll"], p["lrl"], p["lru"], p["llu"]]),
                ("right", [p["rll"], p["rrl"], p["rru"], p["rlu"]]),
                ("front", [p["lrl"], p["rrl"], p["rru"], p["lru"]]),
            ]

            fill = QColor(232, 184, 88, 50) if is_trigger else cyan_soft
            edge = amber if is_trigger else cyan
            edge_mid = QColor(edge.red(), edge.green(), edge.blue(), 118)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(edge_mid, 1.2))
            for _name, poly in faces:
                painter.drawPolygon(QPolygonF(poly))

            edges = [
                ("lll", "rll"), ("rll", "rrl"), ("rrl", "lrl"), ("lrl", "lll"),
                ("llu", "rlu"), ("rlu", "rru"), ("rru", "lru"), ("lru", "llu"),
                ("lll", "llu"), ("rll", "rlu"), ("rrl", "rru"), ("lrl", "lru"),
            ]
            pen = QPen(edge, 2.2)
            if is_trigger:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            for a, b in edges:
                painter.drawLine(p[a], p[b])

            # Draw collider center. Offset is represented by showing the local origin and actual center.
            origin = project((-center[0], -center[1], -center[2]))
            actual_center = project((0.0, 0.0, 0.0))
            painter.setPen(QPen(QColor(210, 210, 210, 150), 1.2))
            painter.drawLine(origin, actual_center)
            painter.setBrush(QBrush(QColor(230, 230, 230)))
            painter.setPen(QPen(QColor(30, 30, 30), 1))
            painter.drawEllipse(actual_center, 4, 4)
            painter.setBrush(QBrush(QColor(110, 110, 110)))
            painter.drawEllipse(origin, 3, 3)

            # Local axes glyph.
            ax0 = QPointF(70, h - 70)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(axis_x, 2))
            painter.drawLine(ax0, QPointF(ax0.x() + 38, ax0.y() + 13)); painter.drawText(QPointF(ax0.x() + 43, ax0.y() + 18), "X")
            painter.setPen(QPen(axis_y, 2))
            painter.drawLine(ax0, QPointF(ax0.x(), ax0.y() - 42)); painter.drawText(QPointF(ax0.x() - 8, ax0.y() - 48), "Y")
            painter.setPen(QPen(axis_z, 2))
            painter.drawLine(ax0, QPointF(ax0.x() - 34, ax0.y() + 18)); painter.drawText(QPointF(ax0.x() - 48, ax0.y() + 25), "Z")

            # Footer explanation.
            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            footer = "Invisible local-space box used for physics, triggers, click zones and interaction volumes."
            painter.drawText(22, h - 24, footer)
            if enabled is not None and not bool(enabled):
                painter.setPen(red)
                painter.drawText(w - 190, h - 24, "BoxCollider disabled")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n🎞 Preview: scaled CAD-style BoxCollider wire box drawn from local center and size fields.")


        def _light_preview_float(self, value, default=None):
            try:
                v = float(value)
            except Exception:
                return default
            try:
                import math
                if not math.isfinite(v):
                    return default
            except Exception:
                pass
            return v

        def _light_preview_color(self, value, default=(1.0, 0.92, 0.72, 1.0)):
            if value is None:
                return default
            if all(hasattr(value, c) for c in ("r", "g", "b")):
                try:
                    return (float(value.r), float(value.g), float(value.b), float(getattr(value, "a", 1.0)))
                except Exception:
                    return default
            if all(hasattr(value, c) for c in ("x", "y", "z")):
                try:
                    return (float(value.x), float(value.y), float(value.z), float(getattr(value, "w", 1.0)))
                except Exception:
                    return default
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                try:
                    return (float(value[0]), float(value[1]), float(value[2]), float(value[3]) if len(value) >= 4 else 1.0)
                except Exception:
                    return default
            return default

        def _light_preview_qcolor(self, rgba, alpha=255):
            def ch(v):
                try:
                    return max(0, min(255, int(round(float(v) * 255.0))))
                except Exception:
                    return 255
            return QColor(ch(rgba[0]), ch(rgba[1]), ch(rgba[2]), int(alpha))


        def _lod_preview_get(self, obj, *names, default=None):
            if obj is None:
                return default
            if isinstance(obj, dict):
                for name in names:
                    if name in obj:
                        return obj[name]
            for name in names:
                if hasattr(obj, name):
                    try:
                        return getattr(obj, name)
                    except Exception:
                        pass
            return default

        def _lod_preview_as_list(self, value):
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                return list(value)
            return []

        def _lod_preview_float(self, value, default=None):
            try:
                import math
                f = float(value)
                return f if math.isfinite(f) else default
            except Exception:
                return default

        def _lod_preview_triangle_estimate(self, mesh_rec):
            if mesh_rec is None:
                return None
            data = self._ov_read(mesh_rec)
            if data is None:
                return None
            submeshes = self._lod_preview_get(data, "m_SubMeshes", "sub_meshes", default=None)
            if not isinstance(submeshes, list):
                return None
            total = 0
            for sm in submeshes:
                ic = self._lod_preview_get(sm, "indexCount", "m_IndexCount", "index_count", default=None)
                try:
                    total += int(ic or 0)
                except Exception:
                    pass
            return total // 3 if total else None

        def _lod_preview_mesh_for_renderer(self, renderer_rec):
            if renderer_rec is None:
                return None
            data = self._ov_read(renderer_rec)
            if data is None:
                return None
            if renderer_rec.type_name == "SkinnedMeshRenderer":
                mesh = self._lod_preview_get(data, "m_Mesh", "mesh", default=None)
                rec = self._ov_resolve(mesh)
                return rec if rec is not None and rec.type_name == "Mesh" else None
            go = self._lod_preview_get(data, "m_GameObject", "gameObject", "game_object", default=None)
            go_rec = self._ov_resolve(go)
            for mf in self._ov_records_with_gameobject("MeshFilter", go_rec or self._ov_pptr_path_id(go)):
                mf_data = self._ov_read(mf)
                mesh = self._lod_preview_get(mf_data, "m_Mesh", "mesh", default=None) if mf_data is not None else None
                rec = self._ov_resolve(mesh)
                if rec is not None and rec.type_name == "Mesh":
                    return rec
            return None

        def _lod_preview_rows(self, rec):
            data = self._ov_read(rec)
            if data is None:
                return []
            lods = self._lod_preview_as_list(self._lod_preview_get(data, "m_LODs", "lods", "LODs", default=None))
            rows = []
            for i, lod in enumerate(lods):
                threshold = self._lod_preview_float(self._lod_preview_get(lod, "screenRelativeHeight", "m_ScreenRelativeHeight", "screen_relative_height", default=None), None)
                fade = self._lod_preview_get(lod, "fadeTransitionWidth", "m_FadeTransitionWidth", "fade_transition_width", default=None)
                renderers = self._lod_preview_as_list(self._lod_preview_get(lod, "m_Renderers", "renderers", "Renderers", default=None))
                tris = 0
                known = False
                names = []
                for r_pptr in renderers:
                    r_rec = self._ov_resolve(r_pptr)
                    if r_rec is not None:
                        names.append(r_rec.name)
                    mesh_rec = self._lod_preview_mesh_for_renderer(r_rec)
                    tri = self._lod_preview_triangle_estimate(mesh_rec)
                    if tri is not None:
                        tris += tri
                        known = True
                rows.append({
                    "index": i,
                    "threshold": threshold,
                    "fade": fade,
                    "renderer_count": len(renderers),
                    "triangles": tris if known else None,
                    "renderer_names": names,
                })
            return rows

        def preview_lod_group(self, rec):
            """Draw an educational Level Of Detail summary for Unity LODGroup components."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"LODGroup\n\n{rec.name}\n\nCould not read LODGroup data for preview.")
                return

            rows = self._lod_preview_rows(rec)
            view_size = self.preview.size()
            w = max(760, int(view_size.width() or 760))
            h = max(340, int(view_size.height() or 380))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 60)
            text = QColor(232, 236, 240)
            muted = QColor(166, 174, 181)
            green = QColor(116, 205, 135)
            amber = QColor(236, 186, 85)
            blue = QColor(105, 160, 235)
            red = QColor(216, 100, 100)
            panel = QColor(44, 48, 52)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 34, "LODGroup / Level Of Detail")
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(muted)
            painter.drawText(22, 56, "Unity chooses a cheaper renderer/mesh set as the object becomes smaller on screen.")

            if not rows:
                painter.setPen(QPen(amber, 2))
                painter.drawRoundedRect(28, 90, w - 56, 110, 10, 10)
                painter.setPen(text)
                painter.drawText(48, 125, "No LOD array was exposed for this object.")
                painter.setPen(muted)
                painter.drawText(48, 150, "The inspector may still show raw references/relationships.")
                painter.end()
                self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return

            chart_x = 150
            chart_y = 92
            chart_w = max(260, w - 220)
            row_h = 38
            max_rows = min(len(rows), max(1, (h - chart_y - 94) // row_h))
            max_tri = max([r["triangles"] or 0 for r in rows] + [1])

            painter.setPen(QPen(muted, 1))
            painter.drawLine(chart_x, chart_y - 10, chart_x + chart_w, chart_y - 10)
            painter.drawText(chart_x, chart_y - 18, "screen size threshold →")
            painter.drawText(chart_x + chart_w - 42, chart_y - 18, "100%")

            for visible_i, r in enumerate(rows[:max_rows]):
                y = chart_y + visible_i * row_h
                idx = r["index"]
                threshold = r["threshold"]
                tris = r["triangles"]
                rc = r["renderer_count"]
                pct = max(0.0, min(1.0, float(threshold))) if threshold is not None else 0.0
                bar_w = max(3, int(chart_w * pct)) if threshold is not None else 0

                painter.setPen(text)
                painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
                painter.drawText(24, y + 22, f"LOD{idx}")
                painter.setFont(QFont("Segoe UI", 8))
                pct_text = f"{pct * 100:.1f}%" if threshold is not None else "-"
                painter.setPen(muted)
                painter.drawText(72, y + 22, pct_text)

                painter.setBrush(QBrush(panel))
                painter.setPen(QPen(bg_grid, 1))
                painter.drawRoundedRect(chart_x, y + 4, chart_w, 20, 5, 5)
                if idx == 0:
                    colour = green
                elif idx == len(rows) - 1:
                    colour = red if getattr(r, "billboard", False) else amber
                else:
                    colour = blue
                if bar_w:
                    painter.setBrush(QBrush(colour))
                    painter.setPen(QPen(colour.darker(125), 1))
                    painter.drawRoundedRect(chart_x, y + 4, bar_w, 20, 5, 5)

                cost_text = f"{rc} renderer(s)"
                if tris is not None:
                    cost_text += f", ~{tris:,} tris"
                    # Small triangle-cost gauge at right, independent of screen threshold.
                    gw = int(90 * (tris / max_tri)) if max_tri else 0
                    gx = chart_x + chart_w - 96
                    painter.setBrush(QBrush(QColor(90, 95, 102)))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(gx, y + 28, 90, 5, 2, 2)
                    painter.setBrush(QBrush(colour))
                    painter.drawRoundedRect(gx, y + 28, max(2, gw), 5, 2, 2)
                painter.setPen(muted)
                painter.drawText(chart_x + 8, y + 38, cost_text)

            bottom_y = chart_y + max_rows * row_h + 26
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(text)
            painter.drawText(24, bottom_y, "How to read this:")
            painter.setPen(muted)
            painter.drawText(24, bottom_y + 22, "LOD0 is normally close/high-detail. Later LODs are cheaper versions for distance viewing.")
            painter.drawText(24, bottom_y + 42, "The screen percentage is the approximate projected size threshold, not a fixed world distance.")
            if len(rows) > max_rows:
                painter.setPen(amber)
                painter.drawText(24, bottom_y + 64, f"Preview shows first {max_rows} of {len(rows)} LOD level(s); inspector lists more detail.")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n📉 Preview: LODGroup thresholds and rough renderer/triangle cost per level.")


        def _light_preview_type_name(self, value):
            try:
                n = int(value)
            except Exception:
                return "Light", None
            names = {
                0: "Spot Light",
                1: "Directional Light / sun",
                2: "Point Light / bulb",
                3: "Area Light",
                4: "Rectangle Light",
                5: "Disc Light",
            }
            return names.get(n, f"Light type {n}"), n

        def preview_light(self, rec):
            """Draw a symbolic light influence diagram for Unity Light components."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"Light\n\n{rec.name}\n\nCould not read Light data for preview.")
                return

            raw_type = self._ov_get(data, "m_Type", "type", "lightType", default=None)
            type_name, type_id = self._light_preview_type_name(raw_type)
            colour = self._light_preview_color(self._ov_get(data, "m_Color", "color", default=None))
            intensity = self._light_preview_float(self._ov_get(data, "m_Intensity", "intensity", default=None), 1.0)
            range_value = self._light_preview_float(self._ov_get(data, "m_Range", "range", default=None), 10.0)
            spot_angle = self._light_preview_float(self._ov_get(data, "m_SpotAngle", "spotAngle", default=None), 30.0)
            inner_spot_angle = self._light_preview_float(self._ov_get(data, "m_InnerSpotAngle", "innerSpotAngle", default=None), None)
            shadows = self._ov_get(data, "m_Shadows", "shadows", default=None)
            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)
            mode = self._ov_get(data, "m_Lightmapping", "lightmapping", "lightmapBakeType", default=None)
            cookie = self._ov_get(data, "m_Cookie", "cookie", default=None)

            view_size = self.preview.size()
            w = max(640, int(view_size.width() or 760))
            h = max(320, int(view_size.height() or 360))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 60)
            text = QColor(232, 236, 240)
            muted = QColor(166, 174, 181)
            red = QColor(216, 100, 100)
            amber = QColor(236, 186, 85)
            blue = QColor(100, 155, 235)
            light_col = self._light_preview_qcolor(colour, 230)
            light_soft = self._light_preview_qcolor(colour, 52)
            light_mid = self._light_preview_qcolor(colour, 120)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "Light influence")
            painter.setFont(QFont("Segoe UI", 9))

            mode_label = "mode -"
            try:
                mode_i = int(mode)
                mode_label = {0: "realtime", 1: "mixed", 2: "baked", 4: "baked"}.get(mode_i, f"mode {mode_i}")
            except Exception:
                if mode is not None:
                    mode_label = str(mode)
            shadow_label = "no shadows"
            try:
                shadow_label = {0: "no shadows", 1: "hard shadows", 2: "soft shadows"}.get(int(shadows), f"shadows {shadows}")
            except Exception:
                if shadows is not None:
                    shadow_label = str(shadows)
            bits = [type_name, f"intensity {self._box_preview_fmt(intensity, 2)}", mode_label, shadow_label]
            if enabled is not None and not bool(enabled):
                bits.append("disabled")
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(bits))

            # Drawing area origin.
            cx = int(w * 0.50)
            cy = int(h * 0.56)

            if type_id == 1:
                # Directional light: position is mostly irrelevant; direction/rotation matters.
                painter.setPen(QPen(light_mid, 2))
                painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
                for i in range(6):
                    y = int(h * 0.25 + i * h * 0.085)
                    x0 = int(w * 0.25 + (i % 2) * 18)
                    x1 = int(w * 0.72 + (i % 2) * 18)
                    painter.drawLine(x0, y - 34, x1, y + 42)
                    # arrow head
                    painter.drawLine(x1, y + 42, x1 - 18, y + 34)
                    painter.drawLine(x1, y + 42, x1 - 3, y + 22)
                painter.setBrush(QBrush(light_soft))
                painter.setPen(QPen(light_col, 2.2))
                painter.drawEllipse(QPointF(int(w * 0.22), int(h * 0.22)), 34, 34)
                painter.setPen(muted)
                painter.drawText(22, h - 48, "Directional lights behave like sunlight: direction matters; local position usually does not.")

            elif type_id == 0:
                # Spot light cone.
                cone = max(8.0, min(120.0, float(spot_angle or 30.0)))
                t = max(0.0, min(1.0, (cone - 10.0) / 110.0))
                far_x = int(w * 0.70)
                far_w = int(w * (0.12 + 0.20 * t))
                top = QPointF(far_x, cy - far_w)
                bottom = QPointF(far_x, cy + far_w)
                origin = QPointF(int(w * 0.25), cy)
                poly = QPolygonF([origin, top, bottom])
                painter.setBrush(QBrush(light_soft))
                painter.setPen(QPen(light_mid, 1.5))
                painter.drawPolygon(poly)
                painter.setPen(QPen(light_col, 2.4))
                painter.drawLine(origin, top)
                painter.drawLine(origin, bottom)
                painter.drawArc(int(origin.x()) - 17, int(origin.y()) - 17, 34, 34, -35 * 16, 70 * 16)
                painter.setBrush(QBrush(light_col))
                painter.drawEllipse(origin, 7, 7)
                painter.setPen(muted)
                painter.drawText(int(origin.x()) + 22, int(origin.y()) - 14, f"spot {self._box_preview_fmt(spot_angle, 1)}°")
                if inner_spot_angle is not None:
                    painter.drawText(int(origin.x()) + 22, int(origin.y()) + 4, f"inner {self._box_preview_fmt(inner_spot_angle, 1)}°")
                painter.drawText(int(far_x) - 30, int(cy + far_w + 28), f"range {self._box_preview_fmt(range_value, 2)}")

            elif type_id in (3, 4, 5):
                # Area/rectangle/disc light: panel source.
                rect_w = int(w * 0.26)
                rect_h = int(h * 0.23)
                panel_rect = QRectF(cx - rect_w / 2, cy - rect_h / 2, rect_w, rect_h)
                painter.setBrush(QBrush(light_soft))
                painter.setPen(QPen(light_col, 2.4))
                if type_id == 5:
                    painter.drawEllipse(panel_rect)
                else:
                    painter.drawRoundedRect(panel_rect, 8, 8)
                # Soft falloff rays.
                painter.setPen(QPen(light_mid, 1.2))
                for i in range(7):
                    px = panel_rect.left() + (i / 6.0) * panel_rect.width()
                    painter.drawLine(QPointF(px, panel_rect.bottom()), QPointF(px - rect_w * 0.35 + i * rect_w * 0.12, panel_rect.bottom() + h * 0.21))
                painter.setPen(muted)
                painter.drawText(22, h - 48, "Area lights represent a surface source. In many mobile/VR projects they are baked or pipeline-dependent.")

            else:
                # Point light/default: range sphere/bulb.
                radius = int(min(w, h) * 0.28)
                painter.setBrush(QBrush(light_soft))
                painter.setPen(QPen(light_mid, 1.4))
                painter.drawEllipse(QPointF(cx, cy), radius, radius)
                painter.setPen(QPen(light_mid, 1.0, Qt.DashLine))
                painter.drawEllipse(QPointF(cx, cy), int(radius * 0.70), int(radius * 0.28))
                painter.drawEllipse(QPointF(cx, cy), int(radius * 0.28), int(radius * 0.70))
                painter.setBrush(QBrush(light_col))
                painter.setPen(QPen(QColor(30, 30, 30), 1))
                painter.drawEllipse(QPointF(cx, cy), 12, 12)
                painter.setPen(muted)
                painter.drawText(cx + radius - 40, cy + radius + 24, f"range {self._box_preview_fmt(range_value, 2)}")

            # Small legend / local transform axes.
            ax0 = QPointF(70, h - 74)
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(QColor(230, 105, 105), 2))
            painter.drawLine(ax0, QPointF(ax0.x() + 38, ax0.y() + 13)); painter.drawText(QPointF(ax0.x() + 43, ax0.y() + 18), "X")
            painter.setPen(QPen(QColor(112, 214, 130), 2))
            painter.drawLine(ax0, QPointF(ax0.x(), ax0.y() - 42)); painter.drawText(QPointF(ax0.x() - 8, ax0.y() - 48), "Y")
            painter.setPen(QPen(QColor(115, 156, 238), 2))
            painter.drawLine(ax0, QPointF(ax0.x() - 34, ax0.y() + 18)); painter.drawText(QPointF(ax0.x() - 48, ax0.y() + 25), "Z")

            if cookie is not None and self._ov_pptr_path_id(cookie) not in (None, 0):
                painter.setPen(amber)
                painter.drawText(w - 190, 58, "cookie texture")
            if enabled is not None and not bool(enabled):
                painter.setPen(red)
                painter.drawText(w - 170, h - 24, "Light disabled")

            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 24, "Symbolic preview only: UBE shows influence shape; Unity's final lighting depends on shader, lightmaps, probes and render pipeline.")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n💡 Preview: symbolic Light influence shape drawn from type, range, spot angle, colour, shadows and bake mode.")



        def _particle_preview_module(self, data, *names):
            for name in names:
                value = self._ov_get(data, name, f"m_{name}", default=None)
                if value is not None:
                    return value
            return None

        def _particle_preview_value(self, value, default="-"):
            if value is None:
                return default
            if isinstance(value, bool):
                return "yes" if value else "no"
            if isinstance(value, (int, float, str)):
                try:
                    return self._box_preview_fmt(float(value), 2)
                except Exception:
                    return str(value)
            # MinMaxCurve-like constants.
            scalar = self._ov_get(value, "scalar", "m_Scalar", "constant", "m_Constant", default=None)
            min_scalar = self._ov_get(value, "minScalar", "m_MinScalar", "constantMin", "m_ConstantMin", default=None)
            max_scalar = self._ov_get(value, "maxScalar", "m_MaxScalar", "constantMax", "m_ConstantMax", default=None)
            if scalar is not None:
                return self._particle_preview_value(scalar, default)
            if min_scalar is not None or max_scalar is not None:
                return f"{self._particle_preview_value(min_scalar, default)}–{self._particle_preview_value(max_scalar, default)}"
            if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
                try:
                    return f"{float(value.x):.2f}, {float(value.y):.2f}, {float(value.z):.2f}"
                except Exception:
                    pass
            if hasattr(value, "r") and hasattr(value, "g") and hasattr(value, "b"):
                try:
                    return f"RGB {float(value.r):.2f}, {float(value.g):.2f}, {float(value.b):.2f}"
                except Exception:
                    pass
            if isinstance(value, (list, tuple)):
                return f"{len(value)} item(s)"
            return default

        def _particle_preview_shape_label(self, value):
            try:
                n = int(value)
            except Exception:
                return str(value) if value is not None else "emitter"
            names = {
                0: "sphere", 1: "sphere shell", 2: "hemisphere", 3: "hemisphere shell",
                4: "cone", 5: "box", 6: "mesh", 7: "cone shell", 8: "cone volume",
                9: "cone volume shell", 10: "circle", 11: "circle edge", 12: "edge",
                13: "mesh renderer", 14: "skinned mesh renderer", 15: "box shell", 16: "box edge",
                17: "donut", 18: "rectangle", 19: "sprite", 20: "sprite renderer",
            }
            return names.get(n, f"shape {n}")

        def _particle_preview_render_mode_label(self, value):
            try:
                n = int(value)
            except Exception:
                return str(value) if value is not None else "renderer -"
            names = {0: "billboard", 1: "stretched billboard", 2: "horizontal billboard", 3: "vertical billboard", 4: "mesh", 5: "none"}
            return names.get(n, f"mode {n}")

        def _particle_system_for_renderer_preview(self, renderer_rec):
            data = self._ov_read(renderer_rec)
            if data is None:
                return None
            go = self._ov_get(data, "m_GameObject", "gameObject", default=None)
            go_rec = self._ov_resolve(go)
            systems = self._ov_records_with_gameobject("ParticleSystem", go_rec or self._ov_pptr_path_id(go))
            return systems[0] if systems else None

        def _particle_renderer_for_system_preview(self, system_rec):
            data = self._ov_read(system_rec)
            if data is None:
                return None
            go = self._ov_get(data, "m_GameObject", "gameObject", default=None)
            go_rec = self._ov_resolve(go)
            renderers = self._ov_records_with_gameobject("ParticleSystemRenderer", go_rec or self._ov_pptr_path_id(go))
            return renderers[0] if renderers else None

        def preview_particle_system(self, rec):
            """Draw a symbolic particle emitter preview for ParticleSystem/ParticleSystemRenderer."""
            import math
            self.preview_stack.setCurrentWidget(self.preview)
            system_rec = rec if rec.type_name == "ParticleSystem" else self._particle_system_for_renderer_preview(rec)
            renderer_rec = rec if rec.type_name == "ParticleSystemRenderer" else self._particle_renderer_for_system_preview(rec)
            data = self._ov_read(system_rec or rec)
            renderer_data = self._ov_read(renderer_rec) if renderer_rec is not None else None
            if data is None and renderer_data is None:
                self.preview.clear()
                self.preview.setText(f"Particle System\n\n{rec.name}\n\nCould not read particle data for preview.")
                return

            initial = self._particle_preview_module(data, "InitialModule", "initialModule") if data is not None else None
            emission = self._particle_preview_module(data, "EmissionModule", "emissionModule") if data is not None else None
            shape = self._particle_preview_module(data, "ShapeModule", "shapeModule") if data is not None else None
            duration = self._ov_get(data, "lengthInSec", "m_LengthInSec", "duration", "m_Duration", default=None) if data is not None else None
            looping = self._ov_get(data, "looping", "m_Looping", default=None) if data is not None else None
            if looping is None and initial is not None:
                looping = self._ov_get(initial, "looping", "m_Looping", default=None)
            max_particles = self._ov_get(data, "maxNumParticles", "m_MaxNumParticles", "maxParticles", "m_MaxParticles", default=None) if data is not None else None
            start_life = self._ov_get(initial, "startLifetime", "m_StartLifetime", default=None) if initial is not None else None
            start_speed = self._ov_get(initial, "startSpeed", "m_StartSpeed", default=None) if initial is not None else None
            start_size = self._ov_get(initial, "startSize", "m_StartSize", default=None) if initial is not None else None
            start_colour = self._ov_get(initial, "startColor", "m_StartColor", "startColour", "m_StartColour", default=None) if initial is not None else None
            rate = self._ov_get(emission, "rateOverTime", "m_RateOverTime", "rateOverTimeMultiplier", "m_RateOverTimeMultiplier", default=None) if emission is not None else None
            shape_type = self._ov_get(shape, "type", "m_Type", "shapeType", "m_ShapeType", default=None) if shape is not None else None
            radius = self._ov_get(shape, "radius", "m_Radius", default=None) if shape is not None else None
            angle = self._ov_get(shape, "angle", "m_Angle", default=None) if shape is not None else None
            render_mode = self._ov_get(renderer_data, "m_RenderMode", "renderMode", default=None) if renderer_data is not None else None
            materials = self._ov_as_list(self._ov_get(renderer_data, "m_Materials", "materials", default=None)) if renderer_data is not None else []
            mesh = self._ov_get(renderer_data, "m_Mesh", "mesh", default=None) if renderer_data is not None else None
            has_mesh = self._ov_pptr_path_id(mesh) not in (None, 0)

            view_size = self.preview.size()
            w = max(760, int(view_size.width() or 760))
            h = max(340, int(view_size.height() or 380))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 60)
            text = QColor(232, 236, 240)
            muted = QColor(166, 174, 181)
            glow = QColor(135, 205, 245)
            glow_soft = QColor(135, 205, 245, 42)
            amber = QColor(236, 186, 85)
            green = QColor(116, 205, 135)
            panel = QColor(44, 48, 52)
            red = QColor(216, 100, 100)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "Particle System")
            painter.setFont(QFont("Segoe UI", 9))
            bits = []
            if duration is not None:
                bits.append(f"duration {self._particle_preview_value(duration)}s")
            if looping is not None:
                bits.append("looping" if bool(looping) else "one-shot")
            if max_particles is not None:
                bits.append(f"max {self._particle_preview_value(max_particles)} particles")
            if render_mode is not None:
                bits.append(self._particle_preview_render_mode_label(render_mode))
            if not bits:
                bits.append("symbolic emitter preview")
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(bits))

            cx = int(w * 0.43)
            base_y = int(h * 0.73)
            emitter_w = int(w * 0.18)
            emitter_h = int(h * 0.10)
            shape_label = self._particle_preview_shape_label(shape_type)

            # Draw symbolic emitter shape.
            painter.setBrush(QBrush(QColor(90, 95, 102, 90)))
            painter.setPen(QPen(QColor(130, 138, 145), 2))
            if "box" in shape_label or "rectangle" in shape_label:
                rect = QRectF(cx - emitter_w / 2, base_y - emitter_h / 2, emitter_w, emitter_h)
                painter.drawRoundedRect(rect, 8, 8)
                painter.setPen(muted)
                painter.drawText(int(rect.left()), int(rect.bottom()) + 22, "box / area emitter")
            elif "sphere" in shape_label or "circle" in shape_label or "donut" in shape_label:
                painter.drawEllipse(QPointF(cx, base_y), emitter_w / 2, emitter_w / 3)
                painter.setPen(muted)
                painter.drawText(cx - 52, base_y + 48, "round emitter")
            elif "mesh" in shape_label or has_mesh:
                poly = QPolygonF([QPointF(cx - 70, base_y + 16), QPointF(cx - 28, base_y - 38), QPointF(cx + 34, base_y - 12), QPointF(cx + 70, base_y + 24)])
                painter.drawPolygon(poly)
                painter.setPen(muted)
                painter.drawText(cx - 48, base_y + 50, "mesh emitter")
            else:
                cone = QPolygonF([QPointF(cx - 62, base_y), QPointF(cx + 62, base_y), QPointF(cx, int(h * 0.25))])
                painter.setBrush(QBrush(glow_soft))
                painter.setPen(QPen(QColor(135, 205, 245, 110), 2))
                painter.drawPolygon(cone)
                painter.setPen(muted)
                painter.drawText(cx - 42, base_y + 28, "cone emitter")

            # Draw particles with a deterministic spiral/cloud.
            try:
                count_hint = int(float(max_particles)) if max_particles is not None else 120
            except Exception:
                count_hint = 120
            count = max(28, min(180, count_hint // 8 if count_hint > 300 else count_hint))
            painter.setPen(Qt.NoPen)
            for i in range(count):
                t = i / max(1, count - 1)
                # Spread from emitter upward; no random module needed, deterministic preview.
                spread = math.sin(i * 12.9898) * 0.5 + math.sin(i * 3.17) * 0.5
                side = spread * (40 + 210 * t)
                px = cx + side
                py = base_y - (40 + 210 * t) + math.cos(i * 5.11) * 18
                size = 2.0 + (1.0 - t) * 4.0
                alpha = int(55 + (1.0 - t) * 130)
                colour = QColor(glow.red(), glow.green(), glow.blue(), alpha)
                painter.setBrush(QBrush(colour))
                painter.drawEllipse(QPointF(px, py), size, size)

            # Velocity / upward arrow.
            painter.setPen(QPen(green, 2.2))
            painter.drawLine(QPointF(cx + 118, base_y), QPointF(cx + 118, int(h * 0.30)))
            painter.drawLine(QPointF(cx + 118, int(h * 0.30)), QPointF(cx + 106, int(h * 0.34)))
            painter.drawLine(QPointF(cx + 118, int(h * 0.30)), QPointF(cx + 130, int(h * 0.34)))
            painter.setPen(muted)
            painter.drawText(cx + 132, int(h * 0.34), "motion / lifetime")

            # Settings card.
            painter.setBrush(QBrush(panel))
            painter.setPen(QPen(QColor(78, 84, 90), 1))
            card = QRectF(w - 292, 84, 258, 174)
            painter.drawRoundedRect(card, 10, 10)
            painter.setPen(text)
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(int(card.left()) + 14, int(card.top()) + 25, "Key settings")
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(muted)
            rows = [
                ("Emitter", shape_label),
                ("Rate", self._particle_preview_value(rate)),
                ("Lifetime", self._particle_preview_value(start_life)),
                ("Speed", self._particle_preview_value(start_speed)),
                ("Start size", self._particle_preview_value(start_size)),
                ("Start colour", self._particle_preview_value(start_colour)),
                ("Materials", str(len(materials)) if renderer_data is not None else "renderer not found"),
            ]
            for j, (label, value) in enumerate(rows):
                painter.drawText(int(card.left()) + 14, int(card.top()) + 48 + j * 18, f"{label}: {value}")

            if has_mesh:
                painter.setPen(amber)
                painter.drawText(w - 238, 58, "mesh particle/emitter reference")
            if renderer_rec is None:
                painter.setPen(red)
                painter.drawText(w - 252, h - 44, "No ParticleSystemRenderer found on same GameObject")

            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 24, "Symbolic preview only: exact particles depend on time, random seed, material shader, camera billboarding and runtime modules.")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n✨ Preview: symbolic ParticleSystem emitter/cloud drawn from lifetime, emission, shape and renderer fields.")

        def _reflection_preview_mode_label(self, value):
            try:
                n = int(value)
                return {0: "baked", 1: "custom cubemap", 2: "realtime"}.get(n, f"mode {n}")
            except Exception:
                return str(value) if value is not None else "mode -"

        def preview_reflection_probe(self, rec):
            """Draw an educational cubemap/volume preview for Unity ReflectionProbe components."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"ReflectionProbe\n\n{rec.name}\n\nCould not read ReflectionProbe data for preview.")
                return

            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)
            mode = self._ov_get(data, "m_Mode", "mode", "m_Type", "type", default=None)
            resolution = self._ov_get(data, "m_Resolution", "resolution", default=None)
            box_projection = self._ov_get(data, "m_BoxProjection", "boxProjection", default=None)
            hdr = self._ov_get(data, "m_HDR", "hdr", default=None)
            blend = self._light_preview_float(self._ov_get(data, "m_BlendDistance", "blendDistance", default=None), 0.0)
            intensity = self._light_preview_float(self._ov_get(data, "m_IntensityMultiplier", "intensityMultiplier", "m_Intensity", default=None), 1.0)
            box_size = self._box_preview_vec3(self._ov_get(data, "m_BoxSize", "boxSize", "m_Size", "size", default=None), (1.0, 1.0, 1.0))
            box_offset = self._box_preview_vec3(self._ov_get(data, "m_BoxOffset", "boxOffset", "m_Center", "center", default=None), (0.0, 0.0, 0.0))
            custom_tex = self._ov_get(data, "m_CustomBakedTexture", "customBakedTexture", "m_CustomTexture", default=None)
            baked_tex = self._ov_get(data, "m_BakedTexture", "bakedTexture", default=None)
            has_cubemap = self._ov_pptr_path_id(custom_tex) not in (None, 0) or self._ov_pptr_path_id(baked_tex) not in (None, 0)

            view_size = self.preview.size()
            w = max(760, int(view_size.width() or 760))
            h = max(340, int(view_size.height() or 380))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg_grid = QColor(52, 56, 60)
            text = QColor(232, 236, 240)
            muted = QColor(166, 174, 181)
            cyan = QColor(98, 190, 220)
            cyan_soft = QColor(98, 190, 220, 45)
            cyan_mid = QColor(98, 190, 220, 125)
            amber = QColor(236, 186, 85)
            red = QColor(216, 100, 100)
            panel = QColor(44, 48, 52)

            painter.setPen(QPen(bg_grid, 1))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "Reflection Probe")
            painter.setFont(QFont("Segoe UI", 9))
            bits = [self._reflection_preview_mode_label(mode)]
            if resolution is not None:
                bits.append(f"{resolution}px cubemap")
            bits.append("box projection" if bool(box_projection) else "spherical/simple projection")
            bits.append("HDR" if bool(hdr) else "LDR")
            if enabled is not None and not bool(enabled):
                bits.append("disabled")
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(bits))

            cx = int(w * 0.50)
            cy = int(h * 0.54)
            sx, sy, sz = box_size
            max_dim = max(abs(sx), abs(sy), abs(sz), 0.001)
            bw = int((0.32 + 0.18 * abs(sx) / max_dim) * w)
            bh = int((0.22 + 0.16 * abs(sy) / max_dim) * h)
            dx = int((0.10 + 0.07 * abs(sz) / max_dim) * w)
            dy = int((0.06 + 0.04 * abs(sz) / max_dim) * h)
            left = cx - bw // 2
            top = cy - bh // 2
            front = QRectF(left, top, bw, bh)
            back = QRectF(left + dx, top - dy, bw, bh)

            # Blend shell around the influence box.
            blend_px = int(max(0.0, min(1.0, blend / max_dim if max_dim else 0.0)) * 70)
            if blend_px > 0:
                painter.setBrush(QBrush(QColor(98, 190, 220, 22)))
                painter.setPen(QPen(QColor(98, 190, 220, 70), 1.0, Qt.DashLine))
                painter.drawRoundedRect(QRectF(front.left() - blend_px, front.top() - blend_px, front.width() + blend_px * 2, front.height() + blend_px * 2), 14, 14)

            painter.setBrush(QBrush(cyan_soft))
            painter.setPen(QPen(cyan_mid, 1.5))
            painter.drawRect(back)
            painter.drawRect(front)
            for a, b in ((front.topLeft(), back.topLeft()), (front.topRight(), back.topRight()), (front.bottomLeft(), back.bottomLeft()), (front.bottomRight(), back.bottomRight())):
                painter.drawLine(a, b)
            painter.setPen(QPen(cyan, 2.2))
            painter.drawRect(front)

            # Cubemap symbol in centre: six little faces around a probe point.
            painter.setBrush(QBrush(QColor(210, 240, 250, 185)))
            painter.setPen(QPen(QColor(22, 32, 36), 1))
            probe = QPointF(cx + int(box_offset[0] / max_dim * 60), cy - int(box_offset[1] / max_dim * 40))
            painter.drawEllipse(probe, 8, 8)
            painter.setBrush(QBrush(QColor(98, 190, 220, 85)))
            face = 18
            for ox, oy in ((0, -33), (0, 33), (-33, 0), (33, 0), (-18, -18), (18, 18)):
                painter.drawRoundedRect(QRectF(probe.x() + ox - face/2, probe.y() + oy - face/2, face, face), 3, 3)
            painter.setPen(muted)
            painter.drawText(int(probe.x()) + 16, int(probe.y()) - 12, "probe / cubemap")

            painter.setPen(QPen(QColor(230, 105, 105), 2))
            ax0 = QPointF(70, h - 74)
            painter.drawLine(ax0, QPointF(ax0.x() + 38, ax0.y() + 13)); painter.drawText(QPointF(ax0.x() + 43, ax0.y() + 18), "X")
            painter.setPen(QPen(QColor(112, 214, 130), 2))
            painter.drawLine(ax0, QPointF(ax0.x(), ax0.y() - 42)); painter.drawText(QPointF(ax0.x() - 8, ax0.y() - 48), "Y")
            painter.setPen(QPen(QColor(115, 156, 238), 2))
            painter.drawLine(ax0, QPointF(ax0.x() - 34, ax0.y() + 18)); painter.drawText(QPointF(ax0.x() - 48, ax0.y() + 25), "Z")

            painter.setBrush(QBrush(panel))
            painter.setPen(QPen(QColor(78, 84, 90), 1))
            card = QRectF(w - 270, 86, 238, 118)
            painter.drawRoundedRect(card, 10, 10)
            painter.setPen(text)
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(int(card.left()) + 14, int(card.top()) + 26, "Key settings")
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(muted)
            painter.drawText(int(card.left()) + 14, int(card.top()) + 48, f"Box size {self._box_preview_fmt(sx, 2)}, {self._box_preview_fmt(sy, 2)}, {self._box_preview_fmt(sz, 2)}")
            painter.drawText(int(card.left()) + 14, int(card.top()) + 68, f"Blend distance {self._box_preview_fmt(blend, 2)}")
            painter.drawText(int(card.left()) + 14, int(card.top()) + 88, f"Intensity {self._box_preview_fmt(intensity, 2)}")
            painter.drawText(int(card.left()) + 14, int(card.top()) + 108, "Cubemap ref: yes" if has_cubemap else "Cubemap ref: none exposed")

            if has_cubemap:
                painter.setPen(amber)
                painter.drawText(w - 190, 58, "cubemap texture linked")
            if enabled is not None and not bool(enabled):
                painter.setPen(red)
                painter.drawText(w - 210, h - 24, "ReflectionProbe disabled")

            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(22, h - 24, "Symbolic preview only: reflections depend on material shader, probe blending, lightmaps and the render pipeline.")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n🪞 Preview: symbolic ReflectionProbe cubemap/blend volume drawn from size, offset, blend, mode and cubemap references.")

        def _camera_preview_float(self, value):
            try:
                v = float(value)
            except Exception:
                return None
            try:
                import math
                if not math.isfinite(v):
                    return None
            except Exception:
                pass
            return v

        def _camera_preview_vec2(self, value):
            if value is None:
                return None
            if hasattr(value, "x") and hasattr(value, "y"):
                try:
                    return (float(value.x), float(value.y))
                except Exception:
                    return None
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                try:
                    return (float(value[0]), float(value[1]))
                except Exception:
                    return None
            return None

        def _camera_preview_fov_from_focal(self, sensor_mm, focal_mm):
            try:
                import math
                sensor_mm = float(sensor_mm)
                focal_mm = float(focal_mm)
                if sensor_mm <= 0 or focal_mm <= 0:
                    return None
                return math.degrees(2.0 * math.atan(sensor_mm / (2.0 * focal_mm)))
            except Exception:
                return None

        def _camera_preview_lens_class(self, equiv_focal, h_fov):
            f = equiv_focal
            if f is not None:
                if f < 20:
                    return "ultra-wide"
                if f < 35:
                    return "wide-angle"
                if f < 70:
                    return "normal"
                if f < 135:
                    return "short telephoto"
                return "telephoto"
            if h_fov is not None:
                if h_fov > 80:
                    return "wide-angle"
                if h_fov > 40:
                    return "normal"
                return "telephoto"
            return "camera view"

        def _camera_preview_fmt(self, value, digits=1):
            if value is None:
                return "-"
            try:
                return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
            except Exception:
                return str(value)

        def preview_camera(self, rec):
            """Draw a small CAD-style camera frustum diagram in the preview pane."""
            self.preview_stack.setCurrentWidget(self.preview)
            data = self._ov_read(rec)
            if data is None:
                self.preview.clear()
                self.preview.setText(f"Camera\n\n{rec.name}\n\nCould not read camera data for preview.")
                return

            focal = self._camera_preview_float(self._ov_get(data, "m_FocalLength", "focalLength", default=None))
            sensor = self._camera_preview_vec2(self._ov_get(data, "m_SensorSize", "sensorSize", default=None))
            fov_value = self._camera_preview_float(self._ov_get(data, "field of view", "fieldOfView", "m_FieldOfView", "m_FOV", default=None))
            ortho = bool(self._ov_get(data, "orthographic", "m_Orthographic", default=False))
            ortho_size = self._camera_preview_float(self._ov_get(data, "orthographic size", "orthographicSize", "m_OrthographicSize", default=None))
            near_clip = self._camera_preview_float(self._ov_get(data, "near clip plane", "nearClipPlane", "m_NearClipPlane", default=None))
            far_clip = self._camera_preview_float(self._ov_get(data, "far clip plane", "farClipPlane", "m_FarClipPlane", default=None))
            enabled = self._ov_get(data, "m_Enabled", "enabled", default=None)

            h_fov = v_fov = equiv35 = None
            if focal is not None and sensor is not None:
                import math
                sw, sh = sensor
                h_fov = self._camera_preview_fov_from_focal(sw, focal)
                v_fov = self._camera_preview_fov_from_focal(sh, focal)
                diag = math.sqrt(sw * sw + sh * sh)
                if diag > 0:
                    equiv35 = focal * (43.266615 / diag)
            elif fov_value is not None:
                v_fov = fov_value
                h_fov = fov_value

            view_size = self.preview.size()
            w = max(760, int(view_size.width() or 760))
            h = max(320, int(view_size.height() or 320))
            pix = QPixmap(w, h)
            pix.fill(QColor(31, 33, 36))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            bg = QColor(31, 33, 36)
            grid = QColor(52, 56, 60)
            teal = QColor(83, 219, 211)
            teal_soft = QColor(83, 219, 211, 54)
            teal_faint = QColor(83, 219, 211, 105)
            text = QColor(228, 232, 235)
            muted = QColor(165, 172, 178)
            amber = QColor(230, 181, 90)
            red = QColor(216, 100, 100)

            # Subtle CAD/grid background.
            painter.setPen(QPen(grid, 1))
            step = 40
            for x in range(0, w, step):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, step):
                painter.drawLine(0, y, w, y)

            title_font = QFont("Segoe UI", 14)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(text)
            painter.drawText(22, 36, "Camera view / frustum")

            small_font = QFont("Segoe UI", 9)
            painter.setFont(small_font)
            lens_class = self._camera_preview_lens_class(equiv35 if equiv35 is not None else focal, h_fov)
            summary_bits = []
            if ortho:
                summary_bits.append("orthographic")
                if ortho_size is not None:
                    summary_bits.append(f"view height ≈ {self._camera_preview_fmt(ortho_size * 2.0)} units")
            else:
                if focal is not None and sensor is not None:
                    summary_bits.append(f"{self._camera_preview_fmt(focal)}mm lens")
                    summary_bits.append(f"{self._camera_preview_fmt(sensor[0])}×{self._camera_preview_fmt(sensor[1])}mm sensor")
                if h_fov is not None and v_fov is not None:
                    summary_bits.append(f"FOV ≈ {self._camera_preview_fmt(h_fov)}° × {self._camera_preview_fmt(v_fov)}°")
                summary_bits.append(lens_class)
            if enabled is not None and not bool(enabled):
                summary_bits.append("disabled in scene")
            painter.setPen(muted)
            painter.drawText(22, 58, "  •  ".join(summary_bits))

            # Drawing area. Use a point camera on the left and a wireframe frustum to the right.
            cx = int(w * 0.17)
            cy = int(h * 0.54)

            if ortho:
                # Orthographic: a parallel viewing box, not a cone.
                box_w = int(w * 0.35)
                box_h = int(h * 0.46)
                skew_x = int(w * 0.08)
                skew_y = int(h * -0.08)
                x0 = int(w * 0.36)
                y0 = int(h * 0.30)
                front = [QPointF(x0, y0), QPointF(x0 + box_w, y0), QPointF(x0 + box_w, y0 + box_h), QPointF(x0, y0 + box_h)]
                back = [QPointF(x0 + skew_x, y0 + skew_y), QPointF(x0 + box_w + skew_x, y0 + skew_y), QPointF(x0 + box_w + skew_x, y0 + box_h + skew_y), QPointF(x0 + skew_x, y0 + box_h + skew_y)]
                painter.setBrush(QBrush(teal_soft))
                painter.setPen(QPen(teal_faint, 1.4))
                painter.drawPolygon(QPolygonF(front))
                painter.drawPolygon(QPolygonF(back))
                painter.setPen(QPen(teal, 2))
                for a, b in zip(front, back):
                    painter.drawLine(a, b)
                for rect in (front, back):
                    for i in range(4):
                        painter.drawLine(rect[i], rect[(i + 1) % 4])
                painter.setPen(QPen(muted, 1))
                painter.drawText(x0, y0 + box_h + 32, "parallel orthographic view box")
            else:
                main_fov = h_fov if h_fov is not None else v_fov
                if main_fov is None:
                    main_fov = 45.0
                # Map FOV to a pleasing visible cone width. A longer lens makes a narrow frustum.
                t = max(0.0, min(1.0, (float(main_fov) - 18.0) / (90.0 - 18.0)))
                cone_scale = 0.48 + 0.72 * t
                far_cx = int(w * (0.68 - 0.06 * t))
                far_cy = int(h * 0.54)
                far_w = int(w * 0.28 * cone_scale)
                far_h = int(h * 0.58 * cone_scale)
                skew_x = int(w * 0.08)
                skew_y = int(h * -0.11)

                # A 3D-ish far plane rectangle.
                p0 = QPointF(far_cx - far_w * 0.48, far_cy - far_h * 0.44)
                p1 = QPointF(far_cx + far_w * 0.48, far_cy - far_h * 0.34)
                p2 = QPointF(far_cx + far_w * 0.35, far_cy + far_h * 0.48)
                p3 = QPointF(far_cx - far_w * 0.55, far_cy + far_h * 0.38)
                far_poly = QPolygonF([p0, p1, p2, p3])

                # Lens/sensor hint, no full camera model.
                lens = QPointF(cx, cy)
                sensor_back = QPointF(cx - 42, cy)
                painter.setPen(QPen(QColor(105, 112, 116), 3))
                painter.drawLine(sensor_back, lens)
                painter.setBrush(QBrush(QColor(82, 88, 92)))
                painter.setPen(QPen(QColor(130, 137, 140), 2))
                painter.drawEllipse(lens, 11, 11)
                painter.setBrush(QBrush(QColor(72, 76, 79)))
                painter.drawRoundedRect(cx - 56, cy - 30, 12, 60, 4, 4)

                # Frustum fill and wire.
                painter.setBrush(QBrush(teal_soft))
                painter.setPen(QPen(teal_faint, 1.2))
                painter.drawPolygon(far_poly)
                painter.setPen(QPen(teal, 2))
                for p in (p0, p1, p2, p3):
                    painter.drawLine(lens, p)
                for a, b in ((p0, p1), (p1, p2), (p2, p3), (p3, p0)):
                    painter.drawLine(a, b)

                # Near clip hint.
                near_t = 0.22
                npts = [QPointF(lens.x() + (p.x() - lens.x()) * near_t, lens.y() + (p.y() - lens.y()) * near_t) for p in (p0, p1, p2, p3)]
                painter.setPen(QPen(QColor(116, 231, 224, 150), 1.5))
                for i in range(4):
                    painter.drawLine(npts[i], npts[(i + 1) % 4])

                # Dimension-ish focal length indicator.
                painter.setPen(QPen(amber, 1.5))
                ydim = cy + 52
                painter.drawLine(sensor_back.x(), ydim, lens.x(), ydim)
                painter.drawLine(sensor_back.x(), ydim - 5, sensor_back.x(), ydim + 5)
                painter.drawLine(lens.x(), ydim - 5, lens.x(), ydim + 5)
                if focal is not None:
                    painter.setPen(amber)
                    painter.drawText(int(sensor_back.x()) - 6, ydim + 21, f"focal length {self._camera_preview_fmt(focal)}mm")

                painter.setPen(muted)
                if near_clip is not None:
                    painter.drawText(int(npts[3].x()) - 5, int(npts[3].y()) + 24, f"near {self._camera_preview_fmt(near_clip)}")
                if far_clip is not None:
                    painter.drawText(int(p3.x()), int(p3.y()) + 28, f"far {self._camera_preview_fmt(far_clip)}")

                # Top-right mini comparison: wide vs telephoto cone.
                mini_x = int(w * 0.78)
                mini_y = 76
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(muted)
                painter.drawText(mini_x - 28, mini_y - 18, "lens feel")
                painter.setPen(QPen(QColor(105, 112, 116), 1))
                painter.drawLine(mini_x, mini_y + 10, mini_x + 70, mini_y - 8)
                painter.drawLine(mini_x, mini_y + 10, mini_x + 70, mini_y + 28)
                painter.drawText(mini_x + 77, mini_y + 14, "wide")
                painter.setPen(QPen(teal, 2))
                narrow = max(7, min(25, int((main_fov or 45) / 3)))
                painter.drawLine(mini_x, mini_y + 58, mini_x + 70, mini_y + 58 - narrow)
                painter.drawLine(mini_x, mini_y + 58, mini_x + 70, mini_y + 58 + narrow)
                painter.drawText(mini_x + 77, mini_y + 62, lens_class)

            # Footer rule of thumb.
            painter.setPen(muted)
            painter.setFont(QFont("Segoe UI", 9))
            footer = "Short focal length = wide cone.  Long focal length = narrow/zoomed cone.  Sensor size changes the cone too."
            painter.drawText(22, h - 24, footer)
            if enabled is not None and not bool(enabled):
                painter.setPen(red)
                painter.drawText(w - 190, h - 24, "Camera component disabled")

            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info.append("\n🎞 Preview: CAD-style camera frustum model drawn from focal length / sensor / projection fields.")

        def object_view_types(self) -> tuple[str, ...]:
            return ("GameObject", "Transform", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer", "MonoBehaviour")

        def relationship_flow_auto_types(self) -> tuple[str, ...]:
            """Asset types whose most useful preview is normally relationship wiring.

            Dedicated texture, mesh, camera, collider, audio and material previews
            retain priority.  Any asset can still open this diagram through the
            tree context menu.
            """
            return (
                "AnimationClip",
                "Animation",
                "Animator",
                "AnimatorController",
                "AnimatorOverrideController",
                "RuntimeAnimatorController",
                "AudioMixerController",
                "AudioMixerGroupController",
                "AudioMixerSnapshotController",
                "AudioMixerEffectController",
            )

        def _flow_record_key(self, rec):
            if rec is None:
                return ("", "", 0, "")
            return (
                str(getattr(rec, "source_file", "") or ""),
                str(getattr(rec, "source_name", "") or ""),
                int(getattr(rec, "path_id", 0) or 0),
                str(getattr(rec, "type_name", "") or ""),
            )

        def _flow_all_records(self, *type_names: str):
            if self.bundle_index is None:
                return []
            out = []
            seen = set()
            local = getattr(self.bundle_index, "objects_by_type", {}) or {}
            external = getattr(self.bundle_index, "external_records_by_type", {}) or {}
            for type_name in type_names:
                for rec in list(local.get(type_name, [])) + list(external.get(type_name, [])):
                    key = self._flow_record_key(rec)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(rec)
            return out

        def _flow_resolve_relationship_record(self, relationship, incoming: bool = False):
            if self.bundle_index is None or relationship is None:
                return None
            pid = getattr(relationship, "source_path_id" if incoming else "target_path_id", None)
            source_name = str(
                getattr(relationship, "source_source_name" if incoming else "target_source_name", "") or ""
            )
            if pid in (None, 0):
                return None
            if source_name:
                rec = getattr(self.bundle_index, "record_by_source_path_id", {}).get((source_name, int(pid)))
                if rec is not None:
                    return rec
                for candidate in self._flow_all_records(
                    "GameObject", "Transform", "RectTransform", "AnimationClip", "Animation", "Animator",
                    "AnimatorController", "AnimatorOverrideController", "Material", "Shader", "Texture2D",
                    "Mesh", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer", "MonoBehaviour", "Avatar",
                    "ParticleSystem", "ParticleSystemRenderer", "Sprite", "SpriteRenderer", "AudioClip",
                ):
                    if int(getattr(candidate, "path_id", 0) or 0) == int(pid) and str(getattr(candidate, "source_name", "") or "") == source_name:
                        return candidate
            return self._ov_resolve(int(pid))

        def _flow_link_for_record(self, rec, text: str | None = None) -> str:
            if rec is None:
                return ""
            label = text or getattr(rec, "name", "") or f"PathID {getattr(rec, 'path_id', '-')}"
            label = escape(str(label))
            pid = int(getattr(rec, "path_id", 0) or 0)
            source_name = str(getattr(rec, "source_name", "") or "")
            exact_rec = None
            if self.bundle_index is not None:
                exact_rec = getattr(self.bundle_index, "record_by_source_path_id", {}).get((source_name, pid))
            local_exact = exact_rec is rec or (
                exact_rec is not None and self._flow_record_key(exact_rec) == self._flow_record_key(rec)
            )
            if local_exact:
                return f"<a href='ube://asset/{pid}'>{label}</a>"
            source_file = getattr(rec, "source_file", None)
            if source_file:
                enc = quote(str(source_file), safe="")
                return f"<a href='ube://external/{enc}/{pid}'>{label}</a>"
            return label

        def _flow_item(self, relation: str, rec=None, title: str = "", note: str = ""):
            return {
                "relation": str(relation or "Related"),
                "record": rec,
                "title": str(title or (getattr(rec, "name", "") if rec is not None else "Related item")),
                "note": str(note or ""),
            }

        def _flow_unique_items(self, items):
            out = []
            seen = set()
            for item in items:
                rec = item.get("record")
                key = (self._flow_record_key(rec), item.get("relation", ""), item.get("title", "")) if rec is not None else (
                    "text", item.get("relation", ""), item.get("title", ""), item.get("note", "")
                )
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
            return out

        def _flow_transform_context(self, rec):
            """Return root, direct parent and direct child GameObjects for rec."""
            go_rec = self._ov_owning_gameobject(rec)
            if rec is not None and getattr(rec, "type_name", "") == "Transform":
                go_rec = self._ov_gameobject_for_transform(rec) or go_rec
                transform = rec
            elif rec is not None and getattr(rec, "type_name", "") == "RectTransform":
                go_rec = self._ov_gameobject_for_transform(rec) or go_rec
                transform = rec
            else:
                transform = self._ov_transform_for_gameobject(go_rec) if go_rec is not None else None

            if transform is None:
                return go_rec, None, None, []

            ancestors = []
            current = transform
            visited = set()
            for _ in range(64):
                key = self._flow_record_key(current)
                if key in visited:
                    break
                visited.add(key)
                data = self._ov_read(current)
                if data is None:
                    break
                parent_pptr = self._ov_get(data, "m_Father", "father", default=None)
                parent = _resolve_record(self.bundle_index, parent_pptr)
                if parent is None:
                    break
                parent_go = self._ov_gameobject_for_transform(parent)
                ancestors.append(parent_go or parent)
                current = parent

            direct_parent = ancestors[0] if ancestors else None
            root_parent = ancestors[-1] if ancestors else None

            children = []
            data = self._ov_read(transform)
            if data is not None:
                for child_pptr in self._ov_as_list(self._ov_get(data, "m_Children", "children", default=None)):
                    child_tr = _resolve_record(self.bundle_index, child_pptr)
                    if child_tr is None:
                        continue
                    children.append(self._ov_gameobject_for_transform(child_tr) or child_tr)
            return go_rec, root_parent, direct_parent, children

        def _flow_path_record_index(self):
            """Map animation-relative hierarchy suffixes to clickable GameObjects."""
            try:
                return _anim_build_path_record_index(self.bundle_index)
            except Exception:
                return {}

        def _flow_animation_clip_targets(self, rec):
            out = []
            data = self._ov_read(rec)
            if data is None:
                return out
            binding_const = self._ov_get(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
            generic = self._ov_as_list(self._ov_get(binding_const, "genericBindings", "m_GenericBindings", default=None)) if binding_const is not None else []
            if not generic:
                return out
            hash_index = _anim_build_path_hash_index(self.bundle_index)
            path_records = self._flow_path_record_index()
            grouped = {}
            for binding in generic:
                try:
                    path_hash = int(self._ov_get(binding, "path", "m_Path", default=0) or 0) & 0xFFFFFFFF
                except Exception:
                    path_hash = 0
                type_id = _anim_binding_type_id(binding)
                target_type = ANIMATION_BINDING_TYPE_NAMES.get(type_id, f"TypeID {type_id}" if type_id is not None else "Asset")
                prop = _anim_binding_property_text(binding)
                candidates = hash_index.get(path_hash, [])
                if not candidates:
                    title = f"Unresolved hash {path_hash}"
                    grouped.setdefault((title, None), set()).add(f"{prop} [{target_type}]")
                    continue
                for path, _bundle_label, _source_name in candidates:
                    matches = path_records.get(path, [])
                    target_rec = matches[0] if matches else None
                    grouped.setdefault((path, self._flow_record_key(target_rec) if target_rec is not None else None), set()).add(
                        f"{prop} [{target_type}]"
                    )
            for (path, rec_key), props in grouped.items():
                target_rec = None
                path_matches = path_records.get(path, [])
                if rec_key is not None:
                    for candidate in path_matches:
                        if self._flow_record_key(candidate) == rec_key:
                            target_rec = candidate
                            break
                leaf = path.rsplit("/", 1)[-1]
                note = "; ".join(sorted(props)[:3])
                if len(props) > 3:
                    note += f"; +{len(props) - 3} more channels"
                if path != leaf:
                    note = f"{path} — {note}"
                if len(path_matches) > 1:
                    note += f" · {len(path_matches)} matching hierarchy instances"
                out.append(self._flow_item("Animated target", target_rec, leaf, note))
            return out

        def _flow_animation_clip_users(self, clip_rec):
            out = []
            clip_key = self._flow_record_key(clip_rec)
            for controller in self._flow_all_records("AnimatorController", "AnimatorOverrideController"):
                data = self._ov_read(controller)
                if data is None:
                    continue
                try:
                    refs = _animctrl_unique_clip_refs(data, self.bundle_index)
                except Exception:
                    refs = []
                for _pptr, candidate in refs:
                    if candidate is not None and self._flow_record_key(candidate) == clip_key:
                        out.append(self._flow_item("Used by controller", controller))
                        break
            for animation in self._flow_all_records("Animation"):
                data = self._ov_read(animation)
                if data is None:
                    continue
                refs = [self._ov_get(data, "m_Animation", "animation", default=None)]
                refs.extend(self._ov_as_list(self._ov_get(data, "m_Animations", "animations", default=None)))
                for pptr in refs:
                    candidate = _resolve_record(self.bundle_index, pptr)
                    if candidate is not None and self._flow_record_key(candidate) == clip_key:
                        out.append(self._flow_item("Played by Animation", animation))
                        break
            return out

        def _flow_known_direct_refs(self, rec):
            out = []
            data = self._ov_read(rec)
            if data is None:
                return out
            type_name = str(getattr(rec, "type_name", "") or "")

            field_specs = []
            if type_name == "Animator":
                field_specs = [
                    ("Controller", ("m_Controller", "controller")),
                    ("Avatar", ("m_Avatar", "avatar")),
                ]
            elif type_name == "Animation":
                field_specs = [("Default clip", ("m_Animation", "animation"))]
            elif type_name in ("MeshFilter",):
                field_specs = [("Mesh", ("m_Mesh", "mesh"))]
            elif type_name in ("MeshRenderer", "SkinnedMeshRenderer", "ParticleSystemRenderer"):
                field_specs = [("Mesh", ("m_Mesh", "mesh")), ("Root bone", ("m_RootBone", "root_bone"))]
            elif type_name == "Material":
                field_specs = [("Shader", ("m_Shader", "shader"))]
            elif type_name in ("SpriteRenderer", "SpriteMask"):
                field_specs = [("Sprite", ("m_Sprite", "sprite"))]
            elif type_name == "PlayableDirector":
                field_specs = [("Playable asset", ("m_PlayableAsset", "playableAsset"))]

            for relation, names in field_specs:
                pptr = self._ov_get(data, *names, default=None)
                target = _resolve_record(self.bundle_index, pptr)
                if target is not None:
                    out.append(self._flow_item(relation, target))

            if type_name == "Animation":
                for pptr in self._ov_as_list(self._ov_get(data, "m_Animations", "animations", default=None)):
                    target = _resolve_record(self.bundle_index, pptr)
                    if target is not None:
                        out.append(self._flow_item("Animation clip", target))

            if type_name in ("MeshRenderer", "SkinnedMeshRenderer", "ParticleSystemRenderer"):
                for slot, pptr in enumerate(self._ov_as_list(self._ov_get(data, "m_Materials", "materials", default=None))):
                    target = _resolve_record(self.bundle_index, pptr)
                    if target is not None:
                        out.append(self._flow_item(f"Material slot {slot}", target))

            if type_name == "SkinnedMeshRenderer":
                bones = self._ov_as_list(self._ov_get(data, "m_Bones", "bones", default=None))
                for slot, pptr in enumerate(bones[:6]):
                    target = _resolve_record(self.bundle_index, pptr)
                    if target is not None:
                        out.append(self._flow_item(f"Bone {slot}", target))
                if len(bones) > 6:
                    out.append(self._flow_item("Bones", None, f"+{len(bones) - 6} more bones", "Open the inspector for the complete bone list."))

            if type_name in ("AnimatorController", "AnimatorOverrideController"):
                try:
                    refs = _animctrl_unique_clip_refs(data, self.bundle_index)
                except Exception:
                    refs = []
                for _pptr, target in refs:
                    if target is not None:
                        out.append(self._flow_item("Animation clip", target))
            return out

        def _flow_controller_users(self, rec):
            if getattr(rec, "type_name", "") not in ("AnimatorController", "AnimatorOverrideController"):
                return []
            key = self._flow_record_key(rec)
            out = []
            for animator in self._flow_all_records("Animator"):
                data = self._ov_read(animator)
                if data is None:
                    continue
                target = _resolve_record(self.bundle_index, self._ov_get(data, "m_Controller", "controller", default=None))
                if target is not None and self._flow_record_key(target) == key:
                    out.append(self._flow_item("Used by Animator", animator))
            return out

        def _flow_asset_graph_items(self, rec):
            incoming = []
            outgoing = []
            try:
                for rel in self.asset_graph.used_by(rec, self.bundle_index):
                    target = self._flow_resolve_relationship_record(rel, incoming=True)
                    if target is not None:
                        incoming.append(self._flow_item(getattr(rel, "relationship", "Used by"), target))
                for rel in self.asset_graph.references(rec, self.bundle_index):
                    target = self._flow_resolve_relationship_record(rel, incoming=False)
                    if target is not None:
                        outgoing.append(self._flow_item(getattr(rel, "relationship", "References"), target))
            except Exception:
                pass
            return incoming, outgoing

        def _flow_collect(self, rec):
            upstream = []
            downstream = []

            go_rec, root_parent, direct_parent, hierarchy_children = self._flow_transform_context(rec)
            if root_parent is not None and self._flow_record_key(root_parent) != self._flow_record_key(direct_parent):
                upstream.append(self._flow_item("Root parent", root_parent))
            if direct_parent is not None:
                upstream.append(self._flow_item("Direct parent", direct_parent))
            if go_rec is not None and self._flow_record_key(go_rec) != self._flow_record_key(rec):
                upstream.append(self._flow_item("Owning GameObject", go_rec))

            type_name = str(getattr(rec, "type_name", "") or "")
            if type_name in ("GameObject", "Transform", "RectTransform"):
                if go_rec is not None:
                    for comp in self._ov_component_records_for_gameobject(go_rec):
                        if self._flow_record_key(comp) != self._flow_record_key(rec):
                            downstream.append(self._flow_item("Component", comp))
                for child in hierarchy_children:
                    downstream.append(self._flow_item("Direct child", child))

            if type_name == "AnimationClip":
                upstream.extend(self._flow_animation_clip_users(rec))
                downstream.extend(self._flow_animation_clip_targets(rec))
            elif type_name in ("AnimatorController", "AnimatorOverrideController"):
                upstream.extend(self._flow_controller_users(rec))

            downstream.extend(self._flow_known_direct_refs(rec))
            graph_in, graph_out = self._flow_asset_graph_items(rec)
            upstream.extend(graph_in)
            downstream.extend(graph_out)

            return self._flow_unique_items(upstream), self._flow_unique_items(downstream)

        def _flow_box_html(self, item, selected: bool = False) -> str:
            rec = item.get("record")
            relation = escape(str(item.get("relation", "Related")))
            title = str(item.get("title", "") or "Related item")
            note = str(item.get("note", "") or "")
            if rec is not None:
                title_html = self._flow_link_for_record(rec, title)
                type_text = friendly_type_name(str(getattr(rec, "type_name", "") or "Asset"))
                pid_text = f"PathID {getattr(rec, 'path_id', '-')}"
                source_name = str(getattr(rec, "source_name", "") or "")
                meta = f"{escape(type_text)} · {escape(pid_text)}"
                if source_name:
                    meta += f" · {escape(source_name)}"
            else:
                title_html = escape(title)
                meta = ""
            css_class = "flowbox selected" if selected else "flowbox"
            bits = [f"<div class='{css_class}'>", f"<div class='relation'>{relation}</div>", f"<div class='boxtitle'>{title_html}</div>"]
            if meta:
                bits.append(f"<div class='meta'>{meta}</div>")
            if note:
                bits.append(f"<div class='note'>{escape(note)}</div>")
            bits.append("</div>")
            return "".join(bits)

        def _relationship_flow_columns(self, item_count: int) -> int:
            """Choose a safe card count per row for the current preview width.

            QTextBrowser uses Qt's rich-text engine, whose CSS flex/grid support
            varies between Qt releases.  A width-aware table is predictable on
            Windows and prevents the last cards becoming one-character columns.
            """
            if item_count <= 0:
                return 1
            try:
                viewport_width = int(self.relationship_view.viewport().width())
            except Exception:
                viewport_width = 900
            # Allow for body margins, table cell spacing and the vertical scrollbar.
            usable_width = max(220, viewport_width - 54)
            preferred_card_width = 230
            columns = max(1, usable_width // preferred_card_width)
            return max(1, min(5, int(item_count), int(columns)))

        def _flow_lane_html(self, title: str, items, empty_text: str, max_items: int = 10) -> str:
            shown = list(items[:max_items])
            rows = []
            if shown:
                columns = self._relationship_flow_columns(len(shown))
                cell_width = max(1, int(100 / columns))
                for start in range(0, len(shown), columns):
                    row_items = shown[start:start + columns]
                    cells = [
                        f"<td valign='top' width='{cell_width}%'>{self._flow_box_html(item)}</td>"
                        for item in row_items
                    ]
                    # Keep a partial final row aligned with the rows above instead
                    # of stretching its last one or two cards across the full width.
                    for _ in range(columns - len(row_items)):
                        cells.append(f"<td class='flow-spacer' width='{cell_width}%'></td>")
                    rows.append(f"<tr>{''.join(cells)}</tr>")
            else:
                rows.append(f"<tr><td><div class='empty'>{escape(empty_text)}</div></td></tr>")
            more = ""
            if len(items) > max_items:
                more = f"<div class='more'>+ {len(items) - max_items} more relationships are listed in the inspector below.</div>"
            return (
                f"<div class='lane-title'>{escape(title)}</div>"
                f"<table class='lane' width='100%' cellspacing='7'>{''.join(rows)}</table>{more}"
            )

        def _relationship_flow_css(self) -> str:
            return """
                body { background:#17191c; color:#ddd; font-family:'Segoe UI',Arial,sans-serif; margin:14px; }
                a { color:#7ec8ff; text-decoration:none; font-weight:600; }
                .flow-title { font-size:20px; font-weight:700; color:#f2f2f2; margin-bottom:3px; }
                .hint { color:#9ea6ad; margin-bottom:10px; }
                .lane-title { color:#c6cbd0; font-weight:700; text-align:center; margin:7px 0 2px 0; }
                table.lane { border-collapse:separate; table-layout:fixed; }
                table.lane td { vertical-align:top; }
                .flow-spacer { border:0; background:transparent; }
                .flowbox { border:1px solid #59616a; background:#24282d; padding:8px; min-width:180px; }
                .flowbox.selected { border:2px solid #68b9e8; background:#21303a; padding:11px; }
                .relation { color:#8ea1ae; font-size:10px; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
                .boxtitle { color:#eef3f6; font-size:13px; font-weight:700; }
                .selected .boxtitle { font-size:16px; }
                .meta { color:#8f979e; font-size:10px; margin-top:4px; }
                .note { color:#bdc4ca; font-size:10px; margin-top:5px; }
                .arrow { color:#68b9e8; font-size:23px; font-weight:700; text-align:center; margin:1px; }
                .centre { width:72%; margin-left:14%; margin-right:14%; }
                .empty { color:#777f86; text-align:center; border:1px dashed #42484e; padding:8px; }
                .more { color:#8e969d; text-align:center; font-size:10px; margin:2px 0 7px 0; }
                .legend { color:#8e969d; font-size:10px; border-top:1px solid #34393e; padding-top:7px; margin-top:9px; }
            """

        def _refresh_relationship_flow_layout(self):
            """Re-render the active flow after a resize has settled."""
            self._relationship_flow_refresh_pending = False
            rec = getattr(self, "_relationship_flow_record", None)
            if rec is None:
                return
            try:
                if self.preview_stack.currentWidget() is not self.relationship_view:
                    return
            except Exception:
                return
            self.preview_relationship_flow(
                rec,
                forced=bool(getattr(self, "_relationship_flow_forced", False)),
                announce=False,
            )

        def preview_relationship_flow(self, rec, forced: bool = False, announce: bool = True):
            if rec is None:
                return False
            self._relationship_flow_record = rec
            self._relationship_flow_forced = bool(forced)
            try:
                self._relationship_flow_last_width = int(self.relationship_view.viewport().width())
            except Exception:
                self._relationship_flow_last_width = 0
            upstream, downstream = self._flow_collect(rec)
            centre = self._flow_item("Selected asset", rec)
            html = [f"<html><body><style>{self._relationship_flow_css()}</style>"]
            html.append("<div class='flow-title'>🔗 Relationship Flow</div>")
            html.append(
                "<div class='hint'>A deliberately shallow view: nearest root/parent/owner above, selected asset in the centre, "
                "and one direct descendant/reference layer below. Click any blue box title to jump there.</div>"
            )
            html.append(self._flow_lane_html("Root / parent / owner / used by", upstream, "No direct parent, owner, or known user was resolved."))
            html.append("<div class='arrow'>▼</div>")
            html.append(
                "<table width='100%' cellspacing='0'><tr><td width='14%'></td><td width='72%'>"
                + self._flow_box_html(centre, selected=True)
                + "</td><td width='14%'></td></tr></table>"
            )
            html.append("<div class='arrow'>▼</div>")
            html.append(self._flow_lane_html("Direct children / components / references / animation targets", downstream, "No direct child or reference was exposed by the decoder."))
            html.append(
                "<div class='legend'>This is a navigation aid, not a complete Unity dependency graph. "
                "The inspector below retains the full component, binding, hierarchy and PathID details. "
                "Right-click any asset and choose <b>Show relationship flow</b> to use this view even when another preview exists.</div>"
            )
            html.append("</body></html>")
            self.relationship_view.setHtml("".join(html))
            self.preview_stack.setCurrentWidget(self.relationship_view)
            if announce:
                try:
                    prefix = "Relationship flow" if not forced else "Relationship flow opened"
                    self.statusBar().showMessage(f"{prefix}: {getattr(rec, 'name', 'asset')} — {len(upstream)} upstream, {len(downstream)} downstream", 4000)
                except Exception:
                    pass
            return True

        def _ov_get(self, obj, *names, default=None):
            if obj is None:
                return default
            for name in names:
                if hasattr(obj, name):
                    try:
                        return getattr(obj, name)
                    except Exception:
                        pass
            return default

        def _ov_as_list(self, value):
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                return list(value)
            return []

        def _ov_read(self, rec):
            try:
                return rec.object.read()
            except Exception:
                return None

        def _ov_pair_key_value(self, item):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                return item[0], item[1]
            for a, b in (("key", "value"), ("first", "second"), ("Key", "Value")):
                if hasattr(item, a) and hasattr(item, b):
                    return getattr(item, a), getattr(item, b)
            return None, item

        def _ov_pptr_path_id(self, pptr):
            if pptr is None:
                return None
            for name in ("path_id", "pathID", "m_PathID", "PathID"):
                value = self._ov_get(pptr, name, default=None)
                if value is not None:
                    try:
                        return int(value)
                    except Exception:
                        return None
            return None

        def _ov_pptr_file_id(self, pptr):
            if pptr is None:
                return None
            for name in ("file_id", "fileID", "m_FileID", "FileID"):
                value = self._ov_get(pptr, name, default=None)
                if value is not None:
                    try:
                        return int(value)
                    except Exception:
                        return None
            return None

        def _ov_pptr_external_source_name(self, pptr):
            """Best-effort name of the external SerializedFile selected by FileID.

            Unity FileID values are 1-based indices into the source SerializedFile's
            external table.  UnityPy versions expose that table under slightly
            different attribute names, so keep this diagnostic deliberately
            defensive.  It is informational only and never changes resolution.
            """
            fid = self._ov_pptr_file_id(pptr)
            if fid in (None, 0):
                return ""
            assets_file = (
                getattr(pptr, "assetsfile", None)
                or getattr(pptr, "assets_file", None)
                or getattr(pptr, "assetsFile", None)
            )
            if assets_file is None:
                return ""
            externals = None
            for name in ("externals", "m_Externals", "external_files", "externalFiles"):
                try:
                    value = getattr(assets_file, name)
                except Exception:
                    value = None
                if value is not None:
                    externals = value
                    break
            rows = self._ov_as_list(externals)
            if not rows or int(fid) < 1 or int(fid) > len(rows):
                return ""
            item = rows[int(fid) - 1]
            for name in ("path", "name", "file_name", "fileName", "m_PathName", "m_FileName"):
                value = self._ov_get(item, name, default=None)
                if value:
                    text = str(value).replace("\\", "/").rstrip("/")
                    return text.rsplit("/", 1)[-1]
            text = str(item or "").strip()
            return text if text and text != "None" else ""

        def _ov_component_pptr(self, item):
            return self._ov_get(item, "component", "m_Component", default=item)

        def _ov_record_key(self, rec):
            if rec is None:
                return ("", None)
            return (
                str(getattr(rec, "source_name", "") or ""),
                getattr(rec, "path_id", None),
            )

        def _ov_pptr_target_key(self, pptr):
            """Resolve a PPtr to its exact SerializedFile + PathID identity.

            UnityFS bundles may contain several internal SerializedFiles that reuse
            the same PathID.  Using only record_by_path_id can therefore connect a
            Transform to the wrong sibling object, which is especially destructive
            for hierarchy reconstruction and repeated mesh instances.
            """
            if pptr is None or isinstance(pptr, int):
                return None
            try:
                target = pptr.deref()
                pid = int(getattr(target, "path_id", None))
                source = str(getattr(getattr(target, "assets_file", None), "name", "") or "")
                if source:
                    return (source, pid)
            except Exception:
                pass
            try:
                pid = self._ov_pptr_path_id(pptr)
                assets_file = getattr(pptr, "assetsfile", None) or getattr(pptr, "assets_file", None)
                source = str(getattr(assets_file, "name", "") or "")
                if source and pid is not None:
                    return (source, int(pid))
            except Exception:
                pass
            return None

        def _ov_pptr_points_to_record(self, pptr, rec) -> bool:
            if pptr is None or rec is None:
                return False
            target_key = self._ov_pptr_target_key(pptr)
            if target_key is not None:
                return target_key == self._ov_record_key(rec)
            return self._ov_pptr_path_id(pptr) == getattr(rec, "path_id", None)

        def _ov_resolve(self, pptr_or_pid):
            if self.bundle_index is None:
                return None
            if not isinstance(pptr_or_pid, int):
                target_key = self._ov_pptr_target_key(pptr_or_pid)
                if target_key is not None:
                    rec = getattr(self.bundle_index, "record_by_source_path_id", {}).get(target_key)
                    if rec is not None:
                        return rec
            pid = pptr_or_pid if isinstance(pptr_or_pid, int) else self._ov_pptr_path_id(pptr_or_pid)
            if pid is None:
                return None
            rec = getattr(self.bundle_index, "record_by_path_id", {}).get(pid)
            if rec is not None:
                return rec
            return getattr(self.bundle_index, "external_record_by_path_id", {}).get(pid)

        def _ov_external_bundle(self, pid):
            if self.bundle_index is None or pid is None:
                return None
            return getattr(self.bundle_index, "external_bundle_by_path_id", {}).get(pid)

        def _ov_asset_link(self, pptr_or_pid, fallback_type="Asset") -> str:
            pid = pptr_or_pid if isinstance(pptr_or_pid, int) else self._ov_pptr_path_id(pptr_or_pid)
            file_id = None if isinstance(pptr_or_pid, int) else self._ov_pptr_file_id(pptr_or_pid)
            if pid in (None, 0):
                return "<span style='color:#777'>-</span>"
            rec = self._ov_resolve(pptr_or_pid)
            if rec is not None:
                label = escape(display_name_with_icon(rec.name, rec.type_name))
                is_local = self.bundle_index is not None and pid in getattr(self.bundle_index, "record_by_path_id", {})
                if is_local:
                    return f"<a href='ube://asset/{pid}'>{label}</a> <span class='muted'>(PathID {pid})</span>"
                ext = self._ov_external_bundle(pid)
                if ext is not None:
                    enc = quote(str(ext), safe="")
                    return f"<a href='ube://external/{enc}/{pid}'>{label}</a> <span class='external'>External</span> <span class='muted'>({escape(Path(str(ext)).name)}, PathID {pid})</span>"
                return f"<span>{label}</span> <span class='external'>External</span> <span class='muted'>(PathID {pid})</span>"
            rec = self._lazy_resolve_pathid_from_project_index(int(pid))
            if rec is not None:
                label = escape(display_name_with_icon(rec.name, rec.type_name))
                ext = self._ov_external_bundle(pid)
                if ext is not None:
                    enc = quote(str(ext), safe="")
                    return f"<a href='ube://external/{enc}/{pid}'>{label}</a> <span class='external'>Index</span> <span class='muted'>({escape(Path(str(ext)).name)}, PathID {pid})</span>"
                return f"<span>{label}</span> <span class='external'>Index</span> <span class='muted'>(PathID {pid})</span>"
            fid = f", FileID {file_id}" if file_id is not None else ""
            lookup_hint = ""
            if self._find_pathid_index_root() is not None:
                lookup_hint = f" <span class='muted'>(not in lazy index lookup)</span>"
            return f"<span class='unresolved'>PathID {escape(str(pid))}{escape(fid)} unresolved</span>{lookup_hint}"

        def _ov_vec3(self, value) -> str:
            if value is None:
                return "-"
            try:
                x = getattr(value, "x")
                y = getattr(value, "y")
                z = getattr(value, "z")
                return f"{float(x):.4g}, {float(y):.4g}, {float(z):.4g}"
            except Exception:
                pass
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                try:
                    return f"{float(value[0]):.4g}, {float(value[1]):.4g}, {float(value[2]):.4g}"
                except Exception:
                    pass
            return escape(str(value))

        def _ov_component_records_for_gameobject(self, go_rec):
            data = self._ov_read(go_rec)
            if data is None:
                return []
            out = []
            for item in self._ov_as_list(self._ov_get(data, "m_Components", "m_Component", default=None)):
                rec = self._ov_resolve(self._ov_component_pptr(item))
                if rec is not None:
                    out.append(rec)
            return out

        def _ov_records_with_gameobject(self, type_name: str, go_rec_or_pid):
            if self.bundle_index is None or go_rec_or_pid is None:
                return []
            go_rec = go_rec_or_pid if not isinstance(go_rec_or_pid, int) else None
            go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else go_rec_or_pid
            out = []
            for rec in getattr(self.bundle_index, "objects_by_type", {}).get(type_name, []):
                data = self._ov_read(rec)
                if data is None:
                    continue
                go_pptr = self._ov_get(data, "m_GameObject", "game_object", default=None)
                if go_rec is not None:
                    if self._ov_pptr_points_to_record(go_pptr, go_rec):
                        out.append(rec)
                elif self._ov_pptr_path_id(go_pptr) == go_pid:
                    out.append(rec)
            return out

        def _ov_gameobject_for_transform(self, transform_rec):
            if transform_rec is None:
                return None
            data = self._ov_read(transform_rec)
            if data is None:
                return None
            return self._ov_resolve(self._ov_get(data, "m_GameObject", "game_object", default=None))

        def _ov_transform_for_gameobject(self, go_rec):
            if go_rec is None:
                return None
            components = self._ov_component_records_for_gameobject(go_rec)
            transform = next((c for c in components if c.type_name == "Transform"), None)
            if transform is not None:
                return transform
            # Fallback for stripped component lists: search local Transform records that
            # point back to this GameObject. This is safe because it only touches the
            # currently loaded bundle, not the whole project index.
            matches = self._ov_records_with_gameobject("Transform", go_rec)
            return matches[0] if matches else None
        def _ov_vec3_tuple(self, value, default=(0.0, 0.0, 0.0)):
            if value is None:
                return default
            try:
                return (float(getattr(value, "x")), float(getattr(value, "y")), float(getattr(value, "z")))
            except Exception:
                pass
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                try:
                    return (float(value[0]), float(value[1]), float(value[2]))
                except Exception:
                    pass
            return default

        def _ov_quat_tuple(self, value, default=(0.0, 0.0, 0.0, 1.0)):
            if value is None:
                return default
            try:
                return (float(getattr(value, "x")), float(getattr(value, "y")), float(getattr(value, "z")), float(getattr(value, "w")))
            except Exception:
                pass
            if isinstance(value, (list, tuple)) and len(value) >= 4:
                try:
                    return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
                except Exception:
                    pass
            return default

        @staticmethod
        def _ov_mat_identity():
            return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

        @staticmethod
        def _ov_mat_mul(a, b):
            out = [[0.0, 0.0, 0.0, 0.0] for _ in range(4)]
            try:
                for r in range(4):
                    for c in range(4):
                        out[r][c] = sum(float(a[r][k]) * float(b[k][c]) for k in range(4))
                return out
            except Exception:
                return a

        @staticmethod
        def _ov_mat_inverse_affine(matrix):
            """Invert an affine row-major 4x4 matrix.

            The accumulated 3x3 basis may include non-uniform scale or shear, so
            strict hierarchy reconstruction cannot assume a pure rotation inverse.
            """
            try:
                m = [[float(matrix[r][c]) for c in range(4)] for r in range(4)]
                a00, a01, a02 = m[0][0], m[0][1], m[0][2]
                a10, a11, a12 = m[1][0], m[1][1], m[1][2]
                a20, a21, a22 = m[2][0], m[2][1], m[2][2]
                det = (
                    a00 * (a11 * a22 - a12 * a21)
                    - a01 * (a10 * a22 - a12 * a20)
                    + a02 * (a10 * a21 - a11 * a20)
                )
                if abs(det) < 1e-12:
                    return None
                inv_det = 1.0 / det
                b00 = (a11 * a22 - a12 * a21) * inv_det
                b01 = (a02 * a21 - a01 * a22) * inv_det
                b02 = (a01 * a12 - a02 * a11) * inv_det
                b10 = (a12 * a20 - a10 * a22) * inv_det
                b11 = (a00 * a22 - a02 * a20) * inv_det
                b12 = (a02 * a10 - a00 * a12) * inv_det
                b20 = (a10 * a21 - a11 * a20) * inv_det
                b21 = (a01 * a20 - a00 * a21) * inv_det
                b22 = (a00 * a11 - a01 * a10) * inv_det
                tx, ty, tz = m[0][3], m[1][3], m[2][3]
                return [
                    [b00, b01, b02, -(b00 * tx + b01 * ty + b02 * tz)],
                    [b10, b11, b12, -(b10 * tx + b11 * ty + b12 * tz)],
                    [b20, b21, b22, -(b20 * tx + b21 * ty + b22 * tz)],
                    [0.0, 0.0, 0.0, 1.0],
                ]
            except Exception:
                return None

        def _ov_trs_matrix(self, pos, quat, scale):
            """Build a simple Unity-style local TRS matrix for preview assembly."""
            px, py, pz = pos or (0.0, 0.0, 0.0)
            x, y, z, w = quat or (0.0, 0.0, 0.0, 1.0)
            sx, sy, sz = scale or (1.0, 1.0, 1.0)
            try:
                length = (x*x + y*y + z*z + w*w) ** 0.5
                if length > 1e-8:
                    x, y, z, w = x/length, y/length, z/length, w/length
            except Exception:
                x, y, z, w = 0.0, 0.0, 0.0, 1.0

            xx, yy, zz = x*x, y*y, z*z
            xy, xz, yz = x*y, x*z, y*z
            wx, wy, wz = w*x, w*y, w*z

            # Row-major matrix that transforms column-style point arithmetic in preview_3d.
            return [
                [(1.0 - 2.0*(yy + zz)) * sx, (2.0*(xy - wz)) * sy,       (2.0*(xz + wy)) * sz,       float(px)],
                [(2.0*(xy + wz)) * sx,       (1.0 - 2.0*(xx + zz)) * sy, (2.0*(yz - wx)) * sz,       float(py)],
                [(2.0*(xz - wy)) * sx,       (2.0*(yz + wx)) * sy,       (1.0 - 2.0*(xx + yy)) * sz, float(pz)],
                [0.0, 0.0, 0.0, 1.0],
            ]

        def _ov_transform_local_matrix(self, transform_rec):
            data = self._ov_read(transform_rec)
            if data is None:
                return self._ov_mat_identity()
            pos = self._ov_vec3_tuple(self._ov_get(data, "m_LocalPosition", "localPosition", "local_position", default=None), (0.0, 0.0, 0.0))
            rot = self._ov_quat_tuple(self._ov_get(data, "m_LocalRotation", "localRotation", "local_rotation", default=None), (0.0, 0.0, 0.0, 1.0))
            scale = self._ov_vec3_tuple(self._ov_get(data, "m_LocalScale", "localScale", "local_scale", default=None), (1.0, 1.0, 1.0))
            return self._ov_trs_matrix(pos, rot, scale)

        def _ov_child_transform_records(self, transform_rec):
            data = self._ov_read(transform_rec)
            if data is None:
                return []
            out = []
            for child_pptr in self._ov_as_list(self._ov_get(data, "m_Children", "children", default=None)):
                child_tr = self._ov_resolve(child_pptr)
                if child_tr is not None and child_tr.type_name in ("Transform", "RectTransform"):
                    out.append(child_tr)
            return out

        def _ov_render_variant_mesh_signature(self, mesh_rec):
            """Return a conservative structural signature for variant detection.

            The signature deliberately excludes raw vertex/UV bytes: alternative
            visual variants are expected to use different geometry or atlas UVs,
            while retaining the same topology, bounds and skinning layout.
            """
            if mesh_rec is None or getattr(mesh_rec, "type_name", "") != "Mesh":
                return None
            data = self._ov_read(mesh_rec)
            if data is None:
                return None

            vertex_data = self._ov_get(data, "m_VertexData", "vertex_data", default=None)
            vertex_count = self._ov_get(
                vertex_data,
                "m_VertexCount",
                "vertexCount",
                "vertex_count",
                default=None,
            )
            try:
                vertex_count = int(vertex_count)
            except Exception:
                return None
            if vertex_count <= 0:
                return None

            submesh_signature = []
            for submesh in self._ov_as_list(
                self._ov_get(data, "m_SubMeshes", "sub_meshes", default=None)
            ):
                try:
                    submesh_signature.append((
                        int(self._ov_get(submesh, "indexCount", "m_IndexCount", "index_count", default=0) or 0),
                        int(self._ov_get(submesh, "topology", "m_Topology", default=0) or 0),
                        int(self._ov_get(submesh, "vertexCount", "m_VertexCount", "vertex_count", default=0) or 0),
                    ))
                except Exception:
                    return None
            if not submesh_signature:
                return None

            def vector_signature(value):
                if value is None:
                    return None
                out = []
                for axis in ("x", "y", "z"):
                    try:
                        out.append(round(float(self._ov_get(value, axis, default=0.0) or 0.0), 5))
                    except Exception:
                        return None
                return tuple(out)

            bounds = self._ov_get(data, "m_LocalAABB", "localAABB", "local_aabb", default=None)
            bounds_signature = None
            if bounds is not None:
                center = vector_signature(self._ov_get(bounds, "m_Center", "center", default=None))
                extent = vector_signature(self._ov_get(bounds, "m_Extent", "extent", default=None))
                if center is not None and extent is not None:
                    bounds_signature = (center, extent)

            bind_pose_count = len(self._ov_as_list(
                self._ov_get(data, "m_BindPose", "bindPose", "bind_poses", default=None)
            ))
            blend_shape_data = self._ov_get(data, "m_Shapes", "shapes", default=None)
            blend_shape_vertices = len(self._ov_as_list(
                self._ov_get(blend_shape_data, "vertices", "m_Vertices", default=None)
            )) if blend_shape_data is not None else 0

            return (
                vertex_count,
                tuple(submesh_signature),
                bounds_signature,
                int(bind_pose_count),
                int(blend_shape_vertices),
            )

        def _animation_overlapping_variant_set(self, items: list[dict]):
            """Identify mutually-exclusive imported render alternatives.

            Some FBX/prefab animation owners keep several numbered complete rigs
            active in the serialized common bundle.  Runtime code chooses one,
            but an isolated bundle preview otherwise draws all alternatives in the
            same space.  The detector is intentionally strict and only recognises
            matching numbered namespaces, identical transforms and equivalent mesh
            structure on distinct SkinnedMeshRenderer assets.
            """
            candidates = []
            for item in items or []:
                if not isinstance(item, dict):
                    return None
                rec = item.get("record")
                go_rec = self._ov_owning_gameobject(rec)
                if go_rec is None:
                    return None
                components = self._ov_component_records_for_gameobject(go_rec)
                skinned = next(
                    (component for component in components if getattr(component, "type_name", "") == "SkinnedMeshRenderer"),
                    None,
                )
                if skinned is None:
                    return None
                mesh_rec = self._ov_attached_mesh_record(skinned)
                mesh_signature = self._ov_render_variant_mesh_signature(mesh_rec)
                if mesh_signature is None:
                    return None
                candidates.append({
                    "name": str(item.get("name") or getattr(go_rec, "name", "")),
                    "matrix": item.get("matrix"),
                    "is_skinned": True,
                    "mesh_key": self._ov_record_key(mesh_rec),
                    "mesh_signature": mesh_signature,
                })
            try:
                return detect_overlapping_render_variants(candidates)
            except Exception:
                return None

        def _ov_renderable_items_from_selection(
            self,
            rec,
            limit: int = 120,
            max_depth: int = 10,
            include_root: bool = True,
        ):
            """Return every render instance beneath one selected asset.

            Unlike the original multi-select path, this follows transform-only
            GameObjects down to their visible descendants.  Every returned row is
            a distinct renderer instance with a matrix relative to the selected
            object's Transform; shared Mesh PathIDs are deliberately not collapsed.
            """
            if rec is None:
                return []
            if getattr(rec, "type_name", "") == "Mesh":
                return [{
                    "record": rec,
                    "transform": None,
                    "matrix": self._ov_mat_identity(),
                    "strict_matrix": self._ov_mat_identity(),
                    "name": getattr(rec, "name", "Mesh"),
                    "instance_key": ("mesh",) + self._ov_record_key(rec),
                }]

            go_rec = self._ov_owning_gameobject(rec)
            if go_rec is None:
                return []
            root_tr = self._ov_transform_for_gameobject(go_rec)
            if root_tr is None:
                return []

            out: list[dict] = []
            visited: set[tuple[str, int | None]] = set()

            if include_root and self._ov_attached_mesh_record(rec) is not None:
                out.append({
                    "record": rec,
                    "transform": root_tr,
                    "matrix": self._ov_mat_identity(),
                    "strict_matrix": self._ov_mat_identity(),
                    "name": getattr(go_rec, "name", getattr(rec, "name", "Object")),
                    "instance_key": ("render",) + self._ov_record_key(root_tr) + self._ov_record_key(go_rec),
                })

            def walk(transform_rec, parent_matrix, depth: int):
                if transform_rec is None or len(out) >= limit or depth > max_depth:
                    return
                key = self._ov_record_key(transform_rec)
                if key in visited:
                    return
                visited.add(key)

                local = self._ov_transform_local_matrix(transform_rec)
                matrix = self._ov_mat_mul(parent_matrix, local)
                child_go = self._ov_gameobject_for_transform(transform_rec)
                if child_go is not None and self._ov_attached_mesh_record(child_go) is not None:
                    strict_matrix = self._ov_strict_relative_matrix(root_tr, transform_rec)
                    out.append({
                        "record": child_go,
                        "transform": transform_rec,
                        "matrix": matrix,
                        "strict_matrix": strict_matrix if strict_matrix is not None else matrix,
                        "name": getattr(child_go, "name", "Object"),
                        "instance_key": ("render",) + self._ov_record_key(transform_rec) + self._ov_record_key(child_go),
                    })

                for grand in self._ov_child_transform_records(transform_rec):
                    walk(grand, matrix, depth + 1)

            for child_tr in self._ov_child_transform_records(root_tr):
                walk(child_tr, self._ov_mat_identity(), 1)
            return out

        def _ov_renderable_descendant_items(self, rec, limit: int = 120, max_depth: int = 10):
            """Return visible descendants relative to a transform-only preview root."""
            return self._ov_renderable_items_from_selection(
                rec,
                limit=limit,
                max_depth=max_depth,
                include_root=False,
            )

        def _ov_parent_transform_record(self, transform_rec):
            data = self._ov_read(transform_rec)
            if data is None:
                return None
            return self._ov_resolve(self._ov_get(data, "m_Father", "father", default=None))

        def _ov_transform_chain_to_root(self, transform_rec, limit: int = 160):
            chain = []
            seen = set()
            current = transform_rec
            while current is not None and len(chain) < limit:
                key = self._ov_record_key(current)
                if key in seen:
                    break
                seen.add(key)
                chain.append(current)
                current = self._ov_parent_transform_record(current)
            return chain

        def _ov_transform_world_matrix(self, transform_rec):
            """Return the full local-to-world matrix for one Transform."""
            if transform_rec is None:
                return self._ov_mat_identity()
            chain = self._ov_transform_chain_to_root(transform_rec)
            if not chain:
                return self._ov_mat_identity()
            matrix = self._ov_mat_identity()
            for tr in reversed(chain):
                matrix = self._ov_mat_mul(matrix, self._ov_transform_local_matrix(tr))
            return matrix

        def _ov_strict_relative_matrix(self, preview_root_tr, target_tr):
            """Return inverse(preview-root world) × target world for K mode."""
            if target_tr is None:
                return self._ov_mat_identity()
            if preview_root_tr is None:
                return self._ov_transform_world_matrix(target_tr)
            if self._ov_record_key(preview_root_tr) == self._ov_record_key(target_tr):
                return self._ov_mat_identity()
            root_world = self._ov_transform_world_matrix(preview_root_tr)
            target_world = self._ov_transform_world_matrix(target_tr)
            root_inverse = self._ov_mat_inverse_affine(root_world)
            if root_inverse is None:
                return None
            return self._ov_mat_mul(root_inverse, target_world)

        def _ov_nearest_common_transform(self, transforms: list):
            clean = [tr for tr in transforms or [] if tr is not None]
            if not clean:
                return None
            chains = [self._ov_transform_chain_to_root(tr) for tr in clean]
            if not chains or any(not chain for chain in chains):
                return None
            other_keys = [{self._ov_record_key(item) for item in chain} for chain in chains[1:]]
            for candidate in chains[0]:
                key = self._ov_record_key(candidate)
                if all(key in keys for keys in other_keys):
                    return candidate
            return None

        def _ov_matrix_from_ancestor(self, ancestor_tr, target_tr):
            """Return target local-to-ancestor matrix, excluding ancestor's own TRS."""
            if target_tr is None:
                return self._ov_mat_identity()
            ancestor_key = self._ov_record_key(ancestor_tr) if ancestor_tr is not None else None
            target_key = self._ov_record_key(target_tr)
            if ancestor_key is not None and target_key == ancestor_key:
                return self._ov_mat_identity()

            path = []
            seen = set()
            current = target_tr
            found = ancestor_tr is None
            while current is not None and len(path) < 160:
                key = self._ov_record_key(current)
                if key in seen:
                    break
                seen.add(key)
                if ancestor_key is not None and key == ancestor_key:
                    found = True
                    break
                path.append(current)
                current = self._ov_parent_transform_record(current)

            if not found:
                return None
            matrix = self._ov_mat_identity()
            for tr in reversed(path):
                matrix = self._ov_mat_mul(matrix, self._ov_transform_local_matrix(tr))
            return matrix

        def _ov_multi_selection_render_items(self, records: list, limit_per_selection: int = 120):
            """Assemble selected objects in the coordinate frame of their common parent."""
            clean = self.unique_records(records or [])[:4]
            rows = []
            for selection_index, rec in enumerate(clean):
                go_rec = self._ov_owning_gameobject(rec)
                tr_rec = self._ov_transform_for_gameobject(go_rec) if go_rec is not None else None
                rows.append((selection_index, rec, go_rec, tr_rec))

            transforms = [row[3] for row in rows if row[3] is not None]
            common_tr = self._ov_nearest_common_transform(transforms) if len(transforms) >= 2 else None
            common_go = self._ov_gameobject_for_transform(common_tr) if common_tr is not None else None
            common_name = getattr(common_go, "name", "Shared authored coordinates") if common_go is not None else "Shared authored coordinates"

            items: list[dict] = []
            rendered_selections: set[int] = set()
            skipped: list[str] = []
            seen_instances = set()

            for selection_index, rec, go_rec, tr_rec in rows:
                selection_name = str(getattr(go_rec or rec, "name", f"Selection {selection_index + 1}"))
                if getattr(rec, "type_name", "") == "Mesh":
                    base_matrix = self._ov_mat_identity()
                elif tr_rec is not None and common_tr is not None:
                    base_matrix = self._ov_matrix_from_ancestor(common_tr, tr_rec)
                    if base_matrix is None:
                        skipped.append(f"{selection_name}: Transform is outside the shared hierarchy")
                        continue
                else:
                    # Separate roots/raw records retain their authored local geometry.
                    base_matrix = self._ov_mat_identity()

                local_items = self._ov_renderable_items_from_selection(
                    rec,
                    limit=limit_per_selection,
                    max_depth=12,
                    include_root=True,
                )
                if not local_items:
                    skipped.append(f"{selection_name}: no direct renderer or renderable descendants")
                    continue

                for local_item in local_items:
                    local_matrix = local_item.get("matrix") or self._ov_mat_identity()
                    combined = self._ov_mat_mul(base_matrix, local_matrix)
                    target_tr = local_item.get("transform")
                    if common_tr is not None and target_tr is not None:
                        strict_combined = self._ov_strict_relative_matrix(common_tr, target_tr)
                    else:
                        local_strict = local_item.get("strict_matrix") or local_matrix
                        strict_combined = self._ov_mat_mul(base_matrix, local_strict)
                    if strict_combined is None:
                        strict_combined = combined
                    instance_key = (
                        selection_index,
                        local_item.get("instance_key"),
                        self._ov_record_key(local_item.get("transform")),
                    )
                    if instance_key in seen_instances:
                        continue
                    seen_instances.add(instance_key)
                    item = dict(local_item)
                    child_name = str(item.get("name") or getattr(item.get("record"), "name", "Object"))
                    item.update({
                        "matrix": combined,
                        "strict_matrix": strict_combined,
                        "selection_index": selection_index,
                        "selection_name": selection_name,
                        "name": selection_name if len(local_items) == 1 else f"{selection_name} / {child_name}",
                    })
                    items.append(item)
                    rendered_selections.add(selection_index)

            return {
                "items": items,
                "rendered_selection_count": len(rendered_selections),
                "selection_count": len(clean),
                "common_transform": common_tr,
                "common_name": common_name,
                "skipped": skipped,
            }


        def _ov_gameobject_has_component_type(self, go_rec, type_name: str) -> bool:
            try:
                return any(getattr(c, "type_name", "") == type_name for c in self._ov_component_records_for_gameobject(go_rec))
            except Exception:
                return False

        @staticmethod
        def _ov_lod_sort_key_from_name(name: str):
            text = str(name or "")
            m = re.search(r"(?:^|[_\-. ])LOD\s*([0-9]+)(?:$|[_\-. ])", text, re.IGNORECASE)
            if m:
                try:
                    return (0, int(m.group(1)), text.lower())
                except Exception:
                    return (0, 999, text.lower())
            # Some authoring tools use names like Low/Med/High, but keep those
            # after clear LOD0/LOD1/LOD2 names so the visible order stays sensible.
            lowered = text.lower()
            for idx, token in enumerate(("high", "medium", "med", "low")):
                if token in lowered:
                    return (1, idx, lowered)
            return (2, 999, lowered)

        def _ov_lod_preview_items_from_group_items(self, group_items: list[dict]) -> list[dict]:
            """Return material-aware LOD child items sorted by LOD number/name.

            A parent with an LODGroup should normally display one child renderer at
            a time, not all child renderers together.  Group preview uses debug
            colours by design, while LOD inspection is more educational when the
            chosen child is shown through its real SkinnedMeshRenderer/MeshRenderer
            material context.
            """
            out = []
            for item in group_items or []:
                if not isinstance(item, dict):
                    continue
                rec = item.get("record")
                if rec is None:
                    continue
                name = str(item.get("name") or getattr(rec, "name", ""))
                # Prefer clear LOD children.  If a game stores an LODGroup with
                # unnamed children, keep the renderable child list as a fallback.
                if re.search(r"LOD\s*[0-9]+", name, re.IGNORECASE):
                    out.append(dict(item, name=name))
            if not out:
                out = [dict(item) for item in (group_items or []) if isinstance(item, dict) and item.get("record") is not None]
            out.sort(key=lambda item: self._ov_lod_sort_key_from_name(str(item.get("name") or getattr(item.get("record"), "name", ""))))
            return out

        def _ov_component_badges(self, go_rec) -> str:
            """Short human summary for a child GameObject row."""
            if go_rec is None:
                return ""
            comps = self._ov_component_records_for_gameobject(go_rec)
            if not comps:
                return "<span class='muted'>no component list</span>"
            names = [c.type_name for c in comps]
            badges = []
            for type_name, label in (
                ("Transform", "Transform"),
                ("MeshFilter", "Mesh Link"),
                ("MeshRenderer", "Renderer"),
                ("SkinnedMeshRenderer", "Skinned Renderer"),
                ("MeshCollider", "Collider"),
                ("MonoBehaviour", "Script"),
                ("Light", "Light"),
                ("AudioSource", "Audio"),
                ("Canvas", "Canvas"),
            ):
                if type_name in names:
                    badges.append(label)
            if not badges:
                badges = [friendly_type_name(n) for n in names[:5]]
            if len(names) > len(badges):
                extra = max(0, len(names) - len(badges))
                if extra:
                    badges.append(f"+{extra}")
            return "<span class='badge'>" + "</span> <span class='badge'>".join(escape(str(x)) for x in badges[:8]) + "</span>"


        def _gameobject_components_html(self, go_rec) -> str | None:
            """Clickable component list for GameObject inspectors.

            The plain text inspector is still useful when copied out, but in the UI
            the component rows should behave like Unity's inspector: click the
            Transform, LODGroup, Light, Renderer, script, etc. directly instead of
            hunting for its PathID in the tree/search box.
            """
            if go_rec is None or getattr(go_rec, "type_name", "") != "GameObject":
                return None
            data = self._ov_read(go_rec)
            if data is None:
                return None
            items = self._ov_as_list(self._ov_get(data, "m_Components", "m_Component", default=None))
            if not items:
                return "<div class='collapsed'>No component list found on this GameObject.</div>"

            parts = ["<ol style='margin-top:5px; padding-left:24px'>"]
            for i, item in enumerate(items):
                pptr = self._ov_component_pptr(item)
                comp_rec = self._ov_resolve(pptr)
                if comp_rec is not None:
                    link = self._ov_asset_link(getattr(comp_rec, "path_id", None), "Component")
                    type_text = friendly_type_name(getattr(comp_rec, "type_name", "Component"))
                    parts.append(
                        f"<li><span class='muted'>{i}:</span> "
                        f"<span class='badge'>{escape(type_text)}</span> {link}</li>"
                    )
                else:
                    pid = self._ov_pptr_path_id(pptr)
                    parts.append(
                        f"<li><span class='muted'>{i}:</span> "
                        f"<span class='unresolved'>unresolved component PathID {escape(str(pid))}</span></li>"
                    )
            parts.append("</ol>")
            parts.append(
                "<div class='collapsed'>Click a component to inspect its own data, such as an LODGroup, Light, Renderer, Collider, Script, or Transform.</div>"
            )
            return "".join(parts)

        def _animation_owner_html(self, rec) -> list[str]:
            """Clickable owner card for the AnimationClip currently previewed.

            Animation ownership is resolved during preview because the correct
            GameObject may come from a Legacy Animation component, an Animator,
            a clip-name fallback, or the coherent target hierarchy.  Once that
            evidence is available, expose it as a normal UBE asset link so the
            user can jump directly to the owner without searching by name.
            """
            if rec is None or getattr(rec, "type_name", "") != "AnimationClip":
                return []
            owner = getattr(self, "animation_owner_gameobject", None)
            clip_key = getattr(self, "animation_owner_clip_key", None)
            if owner is None or clip_key != self._ov_record_key(rec):
                return []
            summary = str(getattr(self, "animation_owner_resolution_summary", "") or "").strip()
            owner_link = self._ov_asset_link(getattr(owner, "path_id", 0), "GameObject")
            parts = [
                "<div class='card'>",
                "<div class='head'>🎬 Animation owner</div>",
                f"<div><span class='muted'>Resolved owner:</span> {owner_link}</div>",
            ]
            if summary:
                parts.append(f"<div class='collapsed' style='margin-top:5px'>Resolution: {escape(summary)}</div>")
            parts.append(
                "<div class='collapsed' style='margin-top:5px'>Click the owner to inspect the GameObject, its components, hierarchy, audio helpers and other scene relationships.</div>"
            )
            parts.append("</div>")
            return parts

        def _component_owner_html(self, rec) -> list[str]:
            """Quick clickable owner card for component records.

            Many Unity components have an m_GameObject back-reference. Showing it as
            a link saves searching when the user starts from an LODGroup, Light,
            Renderer, Collider, AudioSource, MonoBehaviour, etc.
            """
            if rec is None or getattr(rec, "type_name", "") in ("GameObject", "Transform"):
                return []
            data = self._ov_read(rec)
            if data is None:
                return []
            go_pptr = self._ov_get(data, "m_GameObject", "gameObject", "game_object", default=None)
            go_pid = self._ov_pptr_path_id(go_pptr)
            if go_pid in (None, 0):
                return []
            return [
                "<div class='card'>",
                "<div class='head'>🧭 Quick links</div>",
                f"<div><span class='muted'>Owning GameObject:</span> {self._ov_asset_link(go_pptr, 'GameObject')}</div>",
                "<div class='collapsed' style='margin-top:5px'>Use this link to jump back to the scene object that owns this component.</div>",
                "</div>",
            ]

        def _ov_child_summary_html(self, child_transform_rec) -> str:
            if child_transform_rec is None:
                return "<span class='unresolved'>unresolved child Transform</span>"
            child_go = self._ov_gameobject_for_transform(child_transform_rec)
            if child_go is None:
                return f"{self._ov_asset_link(child_transform_rec.path_id, 'Transform')} <span class='muted'>(no GameObject link)</span>"
            return (
                f"{self._ov_asset_link(child_go.path_id, 'GameObject')} "
                f"<span class='muted'>via</span> {self._ov_asset_link(child_transform_rec.path_id, 'Transform')} "
                f"{self._ov_component_badges(child_go)}"
            )

        def _object_hierarchy_html(self, rec) -> list[str]:
            """Clickable parent/child navigation for GameObjects and Transforms.

            This is intentionally separate from the plain-text inspector because
            hierarchy rows are most useful as clickable links. It answers the
            common Unity question: where is this item in the scene tree, and what
            child object should I drill into next?
            """
            if rec is None or rec.type_name not in ("GameObject", "Transform"):
                return []

            go_rec = rec if rec.type_name == "GameObject" else self._ov_gameobject_for_transform(rec)
            transform = rec if rec.type_name == "Transform" else self._ov_transform_for_gameobject(go_rec)
            if transform is None:
                return []

            tr_data = self._ov_read(transform)
            if tr_data is None:
                return []

            parent_pptr = self._ov_get(tr_data, "m_Father", "father", default=None)
            parent_tr = self._ov_resolve(parent_pptr)
            parent_go = self._ov_gameobject_for_transform(parent_tr) if parent_tr is not None else None
            children = self._ov_as_list(self._ov_get(tr_data, "m_Children", "children", default=None))

            parts = [
                "<div class='card'>",
                "<div class='head'>🌳 Object hierarchy</div>",
            ]
            if go_rec is not None:
                parts.append(f"<div><span style='color:#bbb'>Object:</span> {self._ov_asset_link(go_rec.path_id, 'GameObject')}</div>")
            parts.append(f"<div><span style='color:#bbb'>Transform:</span> {self._ov_asset_link(transform.path_id, 'Transform')}</div>")
            if parent_tr is not None or parent_go is not None:
                parts.append("<div style='margin-top:5px'><b>Parent</b><br>")
                if parent_go is not None:
                    parts.append(f"{self._ov_asset_link(parent_go.path_id, 'GameObject')} <span class='muted'>via</span> {self._ov_asset_link(parent_tr.path_id, 'Transform')}")
                else:
                    parts.append(self._ov_asset_link(parent_pptr, 'Transform'))
                parts.append("</div>")
            else:
                parts.append("<div style='margin-top:5px'><b>Parent</b><br><span class='muted'>Scene/root transform or parent not resolved.</span></div>")

            parts.append(f"<div style='margin-top:7px'><b>Children ({len(children)})</b>")
            if children:
                parts.append("<ol style='margin-top:5px; padding-left:24px'>")
                for child in children[:80]:
                    child_tr = self._ov_resolve(child)
                    parts.append(f"<li>{self._ov_child_summary_html(child_tr)}</li>")
                if len(children) > 80:
                    parts.append(f"<li><span class='muted'>... {len(children) - 80} more children</span></li>")
                parts.append("</ol>")
            else:
                parts.append("<br><span class='muted'>No child transforms. This is a leaf node in this part of the scene tree.</span>")
            parts.append("</div>")
            parts.append("<div class='collapsed' style='margin-top:6px'>Tip: container objects such as Hole01_Fish and FishSchools usually have no renderer themselves; click their children to reach the actual visible mesh, script/controller, or nested group.</div>")
            parts.append("</div>")
            return parts

        def _ov_owning_gameobject(self, rec):
            if rec is None:
                return None
            if rec.type_name == "GameObject":
                return rec
            data = self._ov_read(rec)
            if data is None:
                return None
            return self._ov_resolve(self._ov_get(data, "m_GameObject", "game_object", default=None))

        def _ov_material_summary_html(self, mat_pptr, slot: int) -> str:
            pid = self._ov_pptr_path_id(mat_pptr)
            mat_rec = self._ov_resolve(mat_pptr)
            if mat_rec is None:
                return f"<li>Slot {slot}: {self._ov_asset_link(mat_pptr, 'Material')}</li>"

            bits = [f"<li><b>Slot {slot}:</b> {self._ov_asset_link(pid, 'Material')}"]
            data = self._ov_read(mat_rec)
            if data is not None:
                shader = self._ov_get(data, "m_Shader", "shader", default=None)
                if shader is not None:
                    bits.append(f"<br><span class='muted'>Shader:</span> {self._ov_asset_link(shader, 'Shader')}")
                saved = self._ov_get(data, "m_SavedProperties", "saved_properties", default=None)
                if saved is not None:
                    tex_rows = []
                    for item in self._ov_as_list(self._ov_get(saved, "m_TexEnvs", "tex_envs", default=None)):
                        key, value = self._ov_pair_key_value(item)
                        key_text = str(key) if key is not None else "Texture"
                        texture = self._ov_get(value, "m_Texture", "texture", default=value)
                        tex_pid = self._ov_pptr_path_id(texture)
                        if tex_pid not in (None, 0):
                            tex_rows.append((key_text, texture))
                    if tex_rows:
                        bits.append("<br><span class='muted'>Textures:</span><ul class='sublist'>")
                        for key_text, texture in tex_rows[:10]:
                            bits.append(f"<li>{escape(key_text)} → {self._ov_asset_link(texture, 'Texture')}</li>")
                        if len(tex_rows) > 10:
                            bits.append(f"<li>... {len(tex_rows) - 10} more texture slots</li>")
                        bits.append("</ul>")

                    interesting_floats = []
                    for item in self._ov_as_list(self._ov_get(saved, "m_Floats", "floats", default=None)):
                        key, value = self._ov_pair_key_value(item)
                        if key is None:
                            continue
                        name = str(key)
                        lname = name.lower()
                        if any(token in lname for token in ("textureindex", "basemapintensity", "boost", "emis", "glow", "caustic", "flap")):
                            interesting_floats.append((name, value))
                    if interesting_floats:
                        bits.append("<br><span class='muted'>Key floats:</span> ")
                        bits.append(escape(", ".join(f"{k}={v}" for k, v in interesting_floats[:12])))

                    interesting_colours = []
                    for item in self._ov_as_list(self._ov_get(saved, "m_Colors", "colors", default=None)):
                        key, value = self._ov_pair_key_value(item)
                        if key is None:
                            continue
                        name = str(key)
                        lname = name.lower()
                        if any(token in lname for token in ("base", "tint", "eye", "bio", "emis", "glow", "color", "colour")):
                            interesting_colours.append((name, value))
                    if interesting_colours:
                        bits.append("<br><span class='muted'>Key colours:</span><ul class='sublist'>")
                        for name, value in interesting_colours[:8]:
                            bits.append(f"<li>{escape(name)} = {escape(str(value))}</li>")
                        if len(interesting_colours) > 8:
                            bits.append(f"<li>... {len(interesting_colours) - 8} more colours</li>")
                        bits.append("</ul>")
            bits.append("</li>")
            return "".join(bits)


        def _ov_attached_mesh_record(self, rec):
            """Return the Mesh record used by a GameObject/component, if there is one.

            The detailed Object/Component chain belongs in the inspector below.
            The preview panel should show the useful visual result: the mesh attached
            to this object, even when the selected item is a GameObject, Transform,
            MeshFilter, MeshRenderer, or SkinnedMeshRenderer.
            """
            if rec is None:
                return None

            # Direct MeshFilter selection.
            if rec.type_name == "MeshFilter":
                data = self._ov_read(rec)
                mesh_pptr = self._ov_get(data, "m_Mesh", "mesh", default=None) if data is not None else None
                mesh_rec = self._ov_resolve(mesh_pptr)
                return mesh_rec if mesh_rec is not None and mesh_rec.type_name == "Mesh" else None

            # Direct SkinnedMeshRenderer selection.
            if rec.type_name == "SkinnedMeshRenderer":
                data = self._ov_read(rec)
                mesh_pptr = self._ov_get(data, "m_Mesh", "mesh", default=None) if data is not None else None
                mesh_rec = self._ov_resolve(mesh_pptr)
                return mesh_rec if mesh_rec is not None and mesh_rec.type_name == "Mesh" else None

            go_rec = self._ov_owning_gameobject(rec)
            if go_rec is None:
                return None

            components = self._ov_component_records_for_gameobject(go_rec)
            go_pid = go_rec.path_id

            mesh_filter = next((c for c in components if c.type_name == "MeshFilter"), None)
            skinned = next((c for c in components if c.type_name == "SkinnedMeshRenderer"), None)

            if mesh_filter is None:
                filters = self._ov_records_with_gameobject("MeshFilter", go_rec)
                mesh_filter = filters[0] if filters else None
            if skinned is None:
                skinned_renderers = self._ov_records_with_gameobject("SkinnedMeshRenderer", go_rec)
                skinned = skinned_renderers[0] if skinned_renderers else None

            if mesh_filter is not None:
                mf_data = self._ov_read(mesh_filter)
                mesh_pptr = self._ov_get(mf_data, "m_Mesh", "mesh", default=None) if mf_data is not None else None
                mesh_rec = self._ov_resolve(mesh_pptr)
                if mesh_rec is not None and mesh_rec.type_name == "Mesh":
                    return mesh_rec

            if skinned is not None:
                sm_data = self._ov_read(skinned)
                mesh_pptr = self._ov_get(sm_data, "m_Mesh", "mesh", default=None) if sm_data is not None else None
                mesh_rec = self._ov_resolve(mesh_pptr)
                if mesh_rec is not None and mesh_rec.type_name == "Mesh":
                    return mesh_rec

            return None

        def preview_object_attached_mesh(self, rec):
            """Preview the mesh attached to an object/component.

            This avoids duplicating the Object inspector in the preview area.
            The bottom inspector remains the place for Transform / MeshFilter /
            Renderer / Material chain details; the top panel becomes visual again.
            """
            self._hydrate_object_external_render_assets(rec)
            mesh_rec = self._ov_attached_mesh_record(rec)
            if mesh_rec is not None:
                self.preview_stack.setCurrentWidget(self.preview_3d)
                # Preview through the selected Object/component when possible, so
                # the viewer uses that object's renderer Material and recognised base-colour slot (_BaseMap/_ColorMap/_MainTex)
                # rather than only the raw shared Mesh asset.
                if hasattr(self.preview_3d, "load_object_record"):
                    self.preview_3d.load_object_record(rec, self.bundle_index, self.asset_graph)
                else:
                    self.preview_3d.load_mesh_record(mesh_rec, self.bundle_index, self.asset_graph)
                return True

            # Transform-only parent/group objects are common in Unity scenes.  If this
            # object has renderable descendants, show the assembled child meshes in
            # the 3D preview so the user can see the intended prop/group.
            group_items = self._ov_renderable_descendant_items(rec)
            if group_items:
                is_lod_parent = bool(getattr(rec, "type_name", "") == "GameObject" and self._ov_gameobject_has_component_type(rec, "LODGroup"))
                if is_lod_parent and hasattr(self.preview_3d, "load_lod_child_records"):
                    lod_items = self._ov_lod_preview_items_from_group_items(group_items)
                    if lod_items:
                        self.preview_stack.setCurrentWidget(self.preview_3d)
                        lod_label = self.preview_3d.load_lod_child_records(
                            getattr(rec, "name", "LODGroup"),
                            lod_items,
                            self.bundle_index,
                            self.asset_graph,
                            start_index=0,
                        )
                        try:
                            if lod_label:
                                self.statusBar().showMessage(f"3D preview: {lod_label}; press I to cycle {len(lod_items)} LOD child mesh(es)", 5500)
                            else:
                                self.statusBar().showMessage(f"LOD preview: showing LOD0-style child; press I to cycle {len(lod_items)} LOD child mesh(es)", 4500)
                        except Exception:
                            pass
                        return True

                if hasattr(self.preview_3d, "load_object_group_records"):
                    self.preview_stack.setCurrentWidget(self.preview_3d)
                    uv_channel = int(getattr(getattr(self, "preview_3d", None), "uv_channel", 0) or 0)
                    self.preview_3d.load_object_group_records(
                        getattr(rec, "name", "Group"),
                        group_items,
                        self.bundle_index,
                        self.asset_graph,
                        uv_channel=uv_channel,
                    )
                    try:
                        self.statusBar().showMessage(f"Group preview: {len(group_items)} renderable child mesh(es)", 3500)
                    except Exception:
                        pass
                    return True

            # A transform-only parent, script holder or non-rendering component
            # benefits more from a clickable hierarchy/reference diagram than a
            # static "no preview" message.
            self.preview_relationship_flow(rec)
            return False

        def preview_object_view(self, rec):
            """Small visual Object/Render Chain panel in the preview area.

            This is deliberately not a full scene viewer.  It answers the common
            question: which GameObject owns this component, which mesh does it use,
            and which renderer/material/texture chain draws it?
            """
            go_rec = self._ov_owning_gameobject(rec)
            selected_note = f"Selected: {escape(friendly_type_name(rec.type_name))} - {escape(rec.name)} <span class='muted'>(PathID {rec.path_id})</span>"
            if go_rec is None:
                html = f"""
                <html><body><style>{self._object_view_css()}</style>
                <div class='card'><div class='title'>🎲 Object View</div>{selected_note}<br><br>
                <span class='muted'>This item is not linked to a GameObject, so there is no object chain to display.</span></div>
                </body></html>
                """
                self.object_view.setHtml(html)
                return

            go_data = self._ov_read(go_rec)
            components = self._ov_component_records_for_gameobject(go_rec)
            go_pid = go_rec.path_id
            transform = next((c for c in components if c.type_name == "Transform"), None)
            mesh_filter = next((c for c in components if c.type_name == "MeshFilter"), None)
            mesh_renderer = next((c for c in components if c.type_name == "MeshRenderer"), None)
            skinned = next((c for c in components if c.type_name == "SkinnedMeshRenderer"), None)

            # Some stripped/serialized data can omit the GameObject component list.
            # Fall back to matching components that point back to the same GameObject.
            if mesh_filter is None:
                filters = self._ov_records_with_gameobject("MeshFilter", go_rec)
                mesh_filter = filters[0] if filters else None
            if mesh_renderer is None:
                renderers = self._ov_records_with_gameobject("MeshRenderer", go_rec)
                mesh_renderer = renderers[0] if renderers else None
            if skinned is None:
                skinned_renderers = self._ov_records_with_gameobject("SkinnedMeshRenderer", go_rec)
                skinned = skinned_renderers[0] if skinned_renderers else None

            cards = []
            cards.append(f"<div class='card'><div class='title'>🎲 Object View</div>{selected_note}<br>")
            cards.append(f"Object: {self._ov_asset_link(go_pid, 'GameObject')}<br>")
            if go_data is not None:
                active = self._ov_get(go_data, "m_IsActive", "is_active", default="-")
                layer = self._ov_get(go_data, "m_Layer", "layer", default="-")
                tag = self._ov_get(go_data, "m_Tag", "tag", default="-")
                cards.append(f"Active: {escape(str(active))} &nbsp; Layer: {escape(str(layer))} &nbsp; Tag index: {escape(str(tag))}")
            cards.append("</div>")

            cards.append("<div class='card'><div class='title'>🧩 Components</div><ul>")
            if components:
                for i, comp in enumerate(components[:32]):
                    cards.append(f"<li>{i}: {self._ov_asset_link(comp.path_id, comp.type_name)}</li>")
                if len(components) > 32:
                    cards.append(f"<li>... {len(components) - 32} more components</li>")
            else:
                cards.append("<li>No component list found on this GameObject.</li>")
            cards.append("</ul></div>")

            if transform is not None:
                tr_data = self._ov_read(transform)
                cards.append("<div class='card'><div class='title'>↔ Transform</div>")
                cards.append(f"Transform: {self._ov_asset_link(transform.path_id, 'Transform')}<br>")
                if tr_data is not None:
                    cards.append(f"Position: <b>{self._ov_vec3(self._ov_get(tr_data, 'm_LocalPosition', 'local_position', default=None))}</b><br>")
                    cards.append(f"Rotation: {escape(str(self._ov_get(tr_data, 'm_LocalRotation', 'local_rotation', default='-')))}<br>")
                    cards.append(f"Scale: <b>{self._ov_vec3(self._ov_get(tr_data, 'm_LocalScale', 'local_scale', default=None))}</b><br>")
                    cards.append(f"Parent: {self._ov_asset_link(self._ov_get(tr_data, 'm_Father', 'father', default=None), 'Transform')}<br>")
                    children = self._ov_as_list(self._ov_get(tr_data, "m_Children", "children", default=None))
                    cards.append(f"Children: {len(children)}")
                cards.append("</div>")

            cards.append("<div class='card'><div class='title'>🧊 Render Chain</div>")
            has_render_chain = False
            if mesh_filter is not None:
                has_render_chain = True
                mf_data = self._ov_read(mesh_filter)
                mesh = self._ov_get(mf_data, "m_Mesh", "mesh", default=None) if mf_data is not None else None
                cards.append(f"<div class='chain'>Mesh Link / MeshFilter: {self._ov_asset_link(mesh_filter.path_id, 'MeshFilter')}<br>")
                cards.append(f"Mesh: {self._ov_asset_link(mesh, 'Mesh')}</div>")
            if mesh_renderer is not None:
                has_render_chain = True
                mr_data = self._ov_read(mesh_renderer)
                mats = self._ov_as_list(self._ov_get(mr_data, "m_Materials", "materials", default=None)) if mr_data is not None else []
                cards.append(f"<div class='chain'>Renderer / MeshRenderer: {self._ov_asset_link(mesh_renderer.path_id, 'MeshRenderer')}<br>")
                if mr_data is not None:
                    enabled = self._ov_get(mr_data, "m_Enabled", "enabled", default="-")
                    cards.append(f"Enabled: {escape(str(enabled))}<br>")
                cards.append(f"Materials: {len(mats)} slot(s)<ul>")
                if mats:
                    for slot, mat in enumerate(mats[:16]):
                        cards.append(self._ov_material_summary_html(mat, slot))
                    if len(mats) > 16:
                        cards.append(f"<li>... {len(mats) - 16} more materials</li>")
                else:
                    cards.append("<li>No material slots found.</li>")
                cards.append("</ul></div>")
            if skinned is not None:
                has_render_chain = True
                sm_data = self._ov_read(skinned)
                mesh = self._ov_get(sm_data, "m_Mesh", "mesh", default=None) if sm_data is not None else None
                mats = self._ov_as_list(self._ov_get(sm_data, "m_Materials", "materials", default=None)) if sm_data is not None else []
                bones = self._ov_as_list(self._ov_get(sm_data, "m_Bones", "bones", default=None)) if sm_data is not None else []
                cards.append(f"<div class='chain'>Skinned Renderer: {self._ov_asset_link(skinned.path_id, 'SkinnedMeshRenderer')}<br>")
                cards.append(f"Mesh: {self._ov_asset_link(mesh, 'Mesh')}<br>")
                cards.append(f"Bones: {len(bones)}<br>")
                cards.append(f"Materials: {len(mats)} slot(s)<ul>")
                if mats:
                    for slot, mat in enumerate(mats[:16]):
                        cards.append(self._ov_material_summary_html(mat, slot))
                    if len(mats) > 16:
                        cards.append(f"<li>... {len(mats) - 16} more materials</li>")
                else:
                    cards.append("<li>No material slots found.</li>")
                cards.append("</ul></div>")
            if not has_render_chain:
                cards.append("<span class='muted'>No MeshFilter, MeshRenderer, or SkinnedMeshRenderer was found for this object. It may be a parent, locator, trigger, script holder, or hierarchy node.</span>")
            cards.append("</div>")

            cards.append("<div class='hint'>Object View is a quick chain view only. The detailed raw inspector and relationship lists are still below.</div>")
            html = f"<html><body><style>{self._object_view_css()}</style>{''.join(cards)}</body></html>"
            self.object_view.setHtml(html)

        def _object_view_css(self) -> str:
            return """
                body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; color:#eee; background:#202020; }
                a { color:#8ecbff; text-decoration:none; }
                .card { border:1px solid #404040; border-radius:8px; margin:7px; padding:9px 11px; background:#252525; }
                .title { font-weight:700; color:#ffffff; margin-bottom:6px; }
                .chain { border-left:3px solid #555; padding-left:10px; margin:8px 0; }
                .muted { color:#aaa; }
                .external { color:#d9b36c; margin-left:4px; }
                .unresolved { color:#d99797; }
                .hint { color:#aaa; margin:8px; font-style:italic; }
                ul { margin-top:5px; margin-bottom:5px; padding-left:20px; }
                .sublist { margin-top:2px; margin-bottom:2px; }
                .badge { display:inline-block; border:1px solid #555; border-radius:9px; padding:1px 6px; margin-left:4px; color:#ddd; background:#303030; font-size:9pt; }
            """

        def _material_saved_properties(self, mat_rec):
            data = self._ov_read(mat_rec)
            if data is None:
                return None
            return self._ov_get(data, "m_SavedProperties", "saved_properties", default=None)

        def _material_find_color(self, saved, *preferred_names):
            if saved is None:
                return None, None
            wanted = {str(n).lower() for n in preferred_names}
            fallback = None
            for item in self._ov_as_list(self._ov_get(saved, "m_Colors", "colors", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                name = str(key)
                if fallback is None and name.lower() in ("_basecolor", "_color", "_tint"):
                    fallback = (name, value)
                if name.lower() in wanted:
                    return name, value
            return fallback if fallback is not None else (None, None)

        def _material_color_to_css(self, value) -> str | None:
            if value is None:
                return None
            try:
                r = float(getattr(value, "r"))
                g = float(getattr(value, "g"))
                b = float(getattr(value, "b"))
            except Exception:
                try:
                    r, g, b = float(value[0]), float(value[1]), float(value[2])
                except Exception:
                    return None
            def c(v):
                return max(0, min(255, int(round(v * 255.0))))
            return f"#{c(r):02X}{c(g):02X}{c(b):02X}"

        def _material_find_texture_slot(self, saved, *preferred_names):
            if saved is None:
                return None, None, None
            wanted = [str(n).lower() for n in preferred_names]
            rows = []
            for item in self._ov_as_list(self._ov_get(saved, "m_TexEnvs", "tex_envs", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                texture = self._ov_get(value, "m_Texture", "texture", default=value)
                pid = self._ov_pptr_path_id(texture)
                if pid in (None, 0):
                    continue
                rows.append((str(key), texture, pid))
            for pref in wanted:
                for name, texture, pid in rows:
                    if name.lower() == pref:
                        return name, texture, pid
            for pref in wanted:
                for name, texture, pid in rows:
                    if pref.strip("_") in name.lower().strip("_"):
                        return name, texture, pid
            return rows[0] if rows else (None, None, None)

        def _material_key_float_text(self, saved, limit: int = 8) -> str:
            if saved is None:
                return ""
            rows = []
            tokens = ("textureindex", "boost", "emis", "glow", "metal", "smooth", "rough", "caustic", "alpha")
            for item in self._ov_as_list(self._ov_get(saved, "m_Floats", "floats", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                name = str(key)
                if any(t in name.lower() for t in tokens):
                    rows.append(f"{name}={value}")
            return ", ".join(rows[:limit])

        # =====================================================
        # Shader / material intent preview
        # =====================================================
        def _shader_preview_prop_names_from_shader(self, shader_rec) -> set[str]:
            """Return exposed shader property names without decompiling shader source."""
            data = self._ov_read(shader_rec)
            if data is None:
                return set()
            parsed = self._ov_get(data, "m_ParsedForm", "parsed_form", default=None)
            prop_info = self._ov_get(parsed, "m_PropInfo", "prop_info", default=None) if parsed is not None else None
            props = self._ov_as_list(self._ov_get(prop_info, "m_Props", "props", default=None)) if prop_info is not None else []
            names = set()
            for prop in props:
                name = self._ov_get(prop, "m_Name", "name", default=None)
                if name:
                    names.add(str(name))
            return names

        def _shader_preview_shader_name(self, rec) -> str:
            if rec is None:
                return ""
            if getattr(rec, "type_name", "") == "Shader":
                data = self._ov_read(rec)
                name = self._ov_get(data, "m_ParsedForm", "parsed_form", default=None) if data is not None else None
                if name is not None:
                    parsed_name = self._ov_get(name, "m_Name", "name", default=None)
                    if parsed_name:
                        return str(parsed_name)
                return str(getattr(rec, "name", ""))
            if getattr(rec, "type_name", "") == "Material":
                data = self._ov_read(rec)
                shader_pptr = self._ov_get(data, "m_Shader", "shader", default=None) if data is not None else None
                shader_rec = self._ov_resolve(shader_pptr)
                if shader_rec is None:
                    pid = self._ov_pptr_path_id(shader_pptr)
                    if pid not in (None, 0):
                        shader_rec = self._hydrate_external_pathid_from_project_index(int(pid))
                if shader_rec is not None:
                    return self._shader_preview_shader_name(shader_rec)
                return str(shader_pptr or "")
            return str(getattr(rec, "name", ""))

        def _shader_preview_material_float_values(self, saved) -> dict[str, float]:
            out: dict[str, float] = {}
            if saved is None:
                return out
            for item in self._ov_as_list(self._ov_get(saved, "m_Floats", "floats", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                try:
                    out[str(key)] = float(value)
                except Exception:
                    pass
            return out

        def _shader_preview_texture_slot_names(self, saved) -> list[str]:
            names = []
            if saved is None:
                return names
            for item in self._ov_as_list(self._ov_get(saved, "m_TexEnvs", "tex_envs", default=None)):
                key, value = self._ov_pair_key_value(item)
                if key is None:
                    continue
                tex = self._ov_get(value, "m_Texture", "texture", default=value)
                pid = self._ov_pptr_path_id(tex)
                if pid not in (None, 0):
                    names.append(str(key))
            return names

        def _shader_preview_shader_prop_names_and_defaults(self, shader_rec) -> tuple[set[str], dict[str, float], list[str]]:
            data = self._ov_read(shader_rec)
            if data is None:
                return set(), {}, []
            parsed = self._ov_get(data, "m_ParsedForm", "parsed_form", default=None)
            prop_info = self._ov_get(parsed, "m_PropInfo", "prop_info", default=None) if parsed is not None else None
            props = self._ov_as_list(self._ov_get(prop_info, "m_Props", "props", default=None)) if prop_info is not None else []
            names: set[str] = set()
            defaults: dict[str, float] = {}
            textures: list[str] = []
            for prop in props:
                name = self._ov_get(prop, "m_Name", "name", default=None)
                if not name:
                    continue
                name = str(name)
                names.add(name)
                ptype = self._ov_get(prop, "m_Type", "type", default=None)
                if str(ptype) in ("2", "Texture") or "Texture" in str(ptype):
                    textures.append(name)
                # Unity stores four default values; the first value is normally enough for an educational bar.
                for attr in ("m_DefValue", "def_value", "m_DefaultValue", "default_value"):
                    value = self._ov_get(prop, attr, default=None)
                    if value is not None:
                        try:
                            if hasattr(value, "x"):
                                defaults[name] = float(value.x)
                            elif isinstance(value, (list, tuple)) and value:
                                defaults[name] = float(value[0])
                            else:
                                defaults[name] = float(value)
                        except Exception:
                            pass
                        break
            return names, defaults, textures

        def _shader_preview_detect_intent(self, shader_name: str, prop_names: set[str], texture_slots: list[str] | None = None) -> dict[str, object]:
            lower_name = (shader_name or "").lower()
            lower_props = " ".join(sorted(p.lower() for p in prop_names))
            lower_tex = " ".join((texture_slots or [])) .lower()
            text = " ".join((lower_name, lower_props, lower_tex))
            tags: list[str] = []
            category = "surface"
            title = "Generic surface shader"
            colour = (88, 160, 220)

            def has_any(*words: str) -> bool:
                return any(w in text for w in words)

            if has_any("glass", "smudge", "scratch", "fresnel", "roughness", "reflection"):
                category = "glass"
                title = "Glass / reflective surface"
                colour = (93, 210, 230)
                tags.extend(["transparent feel", "fresnel edge", "smudges/scratches"])
            elif has_any("water", "caustic", "foam", "wave", "ocean"):
                category = "water"
                title = "Water / caustics shader"
                colour = (70, 150, 235)
                tags.extend(["animated light", "surface noise", "caustics"])
            elif has_any("grass", "foliage", "leaf", "wind", "deform"):
                category = "foliage"
                title = "Foliage / organic shader"
                colour = (105, 190, 95)
                tags.extend(["wind/deform", "organic breakup", "surface tint"])
            elif has_any("emis", "emission", "glow", "outerglow", "biolum", "light"):
                category = "emissive"
                title = "Glow / emissive shader"
                colour = (255, 185, 72)
                tags.extend(["emission", "glow", "colour boost"])
            elif has_any("ui", "sprite", "canvas", "unlit"):
                category = "ui"
                title = "UI / unlit shader"
                colour = (180, 140, 255)
                tags.extend(["flat/unlit", "screen or panel", "alpha"])
            elif has_any("normal", "bump", "metal", "smooth", "rough", "mask"):
                category = "pbr"
                title = "PBR-style surface shader"
                colour = (160, 170, 185)
                tags.extend(["surface response", "roughness/metal", "normal detail"])
            else:
                tags.extend(["texture inputs", "numeric controls", "compiled passes"])

            # Add extra tags where present, without pretending exact rendering.
            extras = []
            for label, words in (
                ("height fog", ("heightfog",)),
                ("cubemap", ("cubemap",)),
                ("texture array", ("texture2darray", "textureindex")),
                ("vertex colour", ("vertexcolor", "vertex colour", "coloronvertex")),
                ("alpha/cutout", ("alpha", "cutoff", "opacity")),
                ("noise", ("noise",)),
                ("wear", ("wear",)),
            ):
                if any(w in text for w in words):
                    extras.append(label)
            for e in extras:
                if e not in tags:
                    tags.append(e)
            return {"category": category, "title": title, "colour": colour, "tags": tags[:7]}

        def _shader_preview_param(self, values: dict[str, float], names: tuple[str, ...], default: float, min_v: float = 0.0, max_v: float = 1.0) -> float:
            for n in names:
                if n in values:
                    v = values[n]
                    try:
                        if max_v > min_v:
                            return max(0.0, min(1.0, (float(v) - min_v) / (max_v - min_v)))
                    except Exception:
                        pass
            return max(0.0, min(1.0, default))

        def _shader_preview_draw_bar(self, painter, x, y, w, label, amount, colour, text_col, muted_col):
            from PySide6.QtGui import QColor, QPen, QBrush, QFont
            from PySide6.QtCore import QRectF
            painter.setPen(muted_col)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(x, y - 5, label)
            painter.setPen(QPen(QColor(80, 84, 92), 1))
            painter.setBrush(QBrush(QColor(45, 48, 54)))
            painter.drawRoundedRect(QRectF(x, y, w, 9), 4, 4)
            fill_w = max(2, int(w * max(0.0, min(1.0, float(amount)))))
            painter.setPen(QPen(QColor(*colour), 1))
            painter.setBrush(QBrush(QColor(colour[0], colour[1], colour[2], 180)))
            painter.drawRoundedRect(QRectF(x, y, fill_w, 9), 4, 4)
            painter.setPen(text_col)

        def _shader_preview_draw_card(self, rec, *, material_rec=None, saved=None) -> None:
            """Draw a symbolic shader/material intent preview in the top pane.

            This deliberately avoids claiming to recreate Unity/Amplify output.  It draws a small
            school/CAD style model of the shader idea: glass pane, water plane, glow ball, etc.
            """
            from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF, QFont, QLinearGradient, QRadialGradient
            from PySide6.QtCore import QPointF, QRectF, Qt
            import math, random

            shader_rec = rec if getattr(rec, "type_name", "") == "Shader" else None
            if shader_rec is None and material_rec is not None:
                mdata = self._ov_read(material_rec)
                shader_pptr = self._ov_get(mdata, "m_Shader", "shader", default=None) if mdata is not None else None
                shader_rec = self._ov_resolve(shader_pptr)
                if shader_rec is None:
                    pid = self._ov_pptr_path_id(shader_pptr)
                    if pid not in (None, 0):
                        shader_rec = self._hydrate_external_pathid_from_project_index(int(pid))

            shader_name = self._shader_preview_shader_name(shader_rec or rec)
            prop_names: set[str] = set()
            values: dict[str, float] = {}
            texture_slots: list[str] = []
            if shader_rec is not None:
                prop_names, defaults, shader_tex = self._shader_preview_shader_prop_names_and_defaults(shader_rec)
                values.update(defaults)
                texture_slots.extend(shader_tex)
            if saved is not None:
                values.update(self._shader_preview_material_float_values(saved))
                texture_slots.extend(self._shader_preview_texture_slot_names(saved))
                prop_names.update(texture_slots)
                prop_names.update(values.keys())

            intent = self._shader_preview_detect_intent(shader_name, prop_names, texture_slots)
            category = str(intent.get("category", "surface"))
            title = str(intent.get("title", "Shader intent"))
            base_col = tuple(intent.get("colour", (88, 160, 220)))
            tags = [str(x) for x in intent.get("tags", [])]

            rough = self._shader_preview_param(values, ("_Roughness", "_WearRoughness", "_Glossiness"), 0.35)
            refl = self._shader_preview_param(values, ("_ReflectionIntensity", "_ReflectionFresnelScale", "_Specular", "_Metallic"), 0.45, 0.0, 2.0)
            edge = self._shader_preview_param(values, ("_EdgeIntensity", "_OuterGlow_Strength", "_ReflectionFresnelPower"), 0.45, 0.0, 2.0)
            smudge = self._shader_preview_param(values, ("_SmudgeIntensity", "_ScratchesIntensity", "_NoiseIntensity", "_WearIntensity"), 0.2, 0.0, 1.0)
            opacity = self._shader_preview_param(values, ("_Opacity", "_Alpha", "_Surface", "_Blend"), 0.55, 0.0, 2.0)

            view_size = self.preview.size()
            w = max(780, int(view_size.width() or 780))
            h = max(360, int(view_size.height() or 380))
            pix = QPixmap(w, h)
            pix.fill(QColor(28, 30, 35))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing, True)

            text = QColor(232, 236, 240)
            muted = QColor(162, 170, 180)
            grid = QColor(50, 54, 62)
            accent = QColor(base_col[0], base_col[1], base_col[2])
            accent_soft = QColor(base_col[0], base_col[1], base_col[2], 70)

            painter.setPen(QPen(grid, 1))
            for x in range(0, w, 42):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 42):
                painter.drawLine(0, y, w, y)

            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.setPen(text)
            painter.drawText(22, 36, "Shader intent preview")
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(muted)
            shown_name = shader_name or getattr(rec, "name", "")
            if len(shown_name) > 70:
                shown_name = shown_name[:67] + "..."
            painter.drawText(22, 58, shown_name)

            # Left symbolic object area.
            ox = int(w * 0.31)
            oy = int(h * 0.53)
            rng = random.Random(1234)

            # Background checker/scene behind transparent materials.
            if category == "glass":
                sq = 24
                for yy in range(96, h - 70, sq):
                    for xx in range(64, int(w * 0.58), sq):
                        c = QColor(46, 49, 57) if ((xx // sq + yy // sq) % 2) else QColor(68, 72, 82)
                        painter.fillRect(xx, yy, sq, sq, c)

                # Glass pane: slight perspective with bright edges.
                pane = QPolygonF([
                    QPointF(ox - 135, oy - 88), QPointF(ox + 135, oy - 62),
                    QPointF(ox + 110, oy + 92), QPointF(ox - 155, oy + 66),
                ])
                painter.setBrush(QBrush(QColor(base_col[0], base_col[1], base_col[2], int(42 + 80 * opacity))))
                painter.setPen(QPen(QColor(base_col[0], base_col[1], base_col[2], 130), 1.5))
                painter.drawPolygon(pane)
                painter.setPen(QPen(QColor(225, 250, 255, int(80 + 150 * edge)), 3.0))
                painter.drawLine(pane[0], pane[1])
                painter.drawLine(pane[1], pane[2])
                painter.setPen(QPen(QColor(235, 235, 255, int(55 + 140 * refl)), 2.0))
                painter.drawLine(QPointF(ox - 110, oy - 55), QPointF(ox + 82, oy - 36))
                painter.drawLine(QPointF(ox - 82, oy + 12), QPointF(ox + 94, oy + 30))
                painter.setPen(QPen(QColor(245, 245, 245, int(40 + smudge * 140)), 1.1))
                for _ in range(22):
                    x = ox + rng.uniform(-120, 90)
                    y = oy + rng.uniform(-70, 55)
                    painter.drawArc(QRectF(x, y, rng.uniform(14, 42), rng.uniform(4, 16)), 0, int(rng.uniform(90, 230) * 16))
            elif category == "water":
                plane = QPolygonF([QPointF(ox - 170, oy + 45), QPointF(ox + 170, oy + 25), QPointF(ox + 115, oy + 98), QPointF(ox - 190, oy + 112)])
                grad = QLinearGradient(QPointF(ox, oy - 20), QPointF(ox, oy + 110))
                grad.setColorAt(0, QColor(base_col[0], base_col[1], base_col[2], 175))
                grad.setColorAt(1, QColor(15, 45, 90, 210))
                painter.setBrush(QBrush(grad)); painter.setPen(QPen(accent, 1.5)); painter.drawPolygon(plane)
                painter.setPen(QPen(QColor(210, 240, 255, 130), 1.2))
                for i in range(9):
                    yy = oy + 44 + i * 8
                    pts = []
                    for j in range(12):
                        xx = ox - 145 + j * 27
                        pts.append(QPointF(xx, yy + math.sin(j * 0.9 + i) * 5))
                    for a, b in zip(pts, pts[1:]):
                        painter.drawLine(a, b)
            elif category == "emissive":
                rg = QRadialGradient(QPointF(ox, oy), 150)
                rg.setColorAt(0, QColor(base_col[0], base_col[1], base_col[2], 210))
                rg.setColorAt(0.5, QColor(base_col[0], base_col[1], base_col[2], 90))
                rg.setColorAt(1, QColor(base_col[0], base_col[1], base_col[2], 0))
                painter.setBrush(QBrush(rg)); painter.setPen(Qt.NoPen); painter.drawEllipse(QPointF(ox, oy), 150, 150)
                painter.setBrush(QBrush(QColor(base_col[0], base_col[1], base_col[2], 210))); painter.setPen(QPen(QColor(255,255,255,150), 2)); painter.drawEllipse(QPointF(ox, oy), 72, 72)
            elif category == "foliage":
                painter.setPen(QPen(QColor(95, 72, 43), 6)); painter.drawLine(QPointF(ox, oy + 95), QPointF(ox, oy - 50))
                painter.setPen(QPen(accent, 2)); painter.setBrush(QBrush(QColor(base_col[0], base_col[1], base_col[2], 170)))
                for i in range(18):
                    ang = (i / 18.0) * math.pi * 2
                    cx = ox + math.cos(ang) * rng.uniform(35, 110)
                    cy = oy - 20 + math.sin(ang) * rng.uniform(18, 70)
                    painter.drawEllipse(QPointF(cx, cy), rng.uniform(13, 24), rng.uniform(7, 16))
            else:
                # generic lit cube/sphere hybrid
                front = QPolygonF([QPointF(ox-90,oy-70),QPointF(ox+70,oy-70),QPointF(ox+70,oy+70),QPointF(ox-90,oy+70)])
                top = QPolygonF([QPointF(ox-90,oy-70),QPointF(ox-40,oy-120),QPointF(ox+120,oy-120),QPointF(ox+70,oy-70)])
                side = QPolygonF([QPointF(ox+70,oy-70),QPointF(ox+120,oy-120),QPointF(ox+120,oy+20),QPointF(ox+70,oy+70)])
                painter.setPen(QPen(accent, 1.5))
                painter.setBrush(QBrush(QColor(base_col[0],base_col[1],base_col[2],150))); painter.drawPolygon(front)
                painter.setBrush(QBrush(QColor(min(base_col[0]+35,255),min(base_col[1]+35,255),min(base_col[2]+35,255),145))); painter.drawPolygon(top)
                painter.setBrush(QBrush(QColor(max(base_col[0]-35,0),max(base_col[1]-35,0),max(base_col[2]-35,0),145))); painter.drawPolygon(side)

            # Right information card.  Keep this panel deliberately generous: the
            # ingredient chips can vary between shaders and should wrap rather than
            # leaking below the card at shorter preview heights.
            card = QRectF(w * 0.58, 56, w * 0.39, h - 64)
            painter.setPen(QPen(QColor(70, 76, 86), 1.2))
            painter.setBrush(QBrush(QColor(36, 39, 46, 225)))
            painter.drawRoundedRect(card, 10, 10)
            painter.setPen(text); painter.setFont(QFont("Segoe UI", 13, QFont.Bold)); painter.drawText(int(card.left()+18), int(card.top()+30), title)
            painter.setFont(QFont("Segoe UI", 9)); painter.setPen(muted)
            painter.drawText(int(card.left()+18), int(card.top()+51), "Symbolic preview: shows shader intent, not exact Unity output.")

            y = int(card.top() + 76)
            bar_x = int(card.left() + 20)
            bar_w = int(card.width() - 40)
            for label, amount in (
                ("roughness / matte", rough),
                ("reflection / specular", refl),
                ("edge / fresnel", edge),
                ("noise / smudge / wear", smudge),
            ):
                self._shader_preview_draw_bar(painter, bar_x, y, bar_w, label, amount, base_col, text, muted)
                y += 28

            painter.setPen(muted); painter.setFont(QFont("Segoe UI", 9, QFont.Bold)); painter.drawText(bar_x, y + 7, "Detected ingredients")
            y += 24

            # Lay ingredient chips left-to-right and wrap only when the next chip
            # would exceed the card.  This keeps short items on the same line and
            # makes much better use of a wide preview panel.
            painter.setFont(QFont("Segoe UI", 8))
            metrics = painter.fontMetrics()
            chip_x = bar_x
            chip_top = y - 14
            chip_right = int(card.right() - 18)
            chip_gap = 8
            chip_row_height = 24
            for tag in tags:
                chip_w = min(bar_w, max(58, int(metrics.horizontalAdvance(tag)) + 18))
                if chip_x != bar_x and chip_x + chip_w > chip_right:
                    chip_x = bar_x
                    chip_top += chip_row_height
                painter.setPen(QPen(QColor(82, 88, 98), 1)); painter.setBrush(QBrush(QColor(48, 52, 60)))
                tag_rect = QRectF(chip_x, chip_top, chip_w, 22)
                painter.drawRoundedRect(tag_rect, 8, 8)
                painter.setPen(text); painter.drawText(int(tag_rect.left()+8), int(tag_rect.top()+15), tag)
                chip_x += chip_w + chip_gap

            painter.setPen(muted); painter.setFont(QFont("Segoe UI", 8))
            footer = "Shader = visual recipe. Material = this recipe with chosen textures/values."
            painter.drawText(22, h - 24, footer)
            painter.end()
            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        def preview_shader(self, rec):
            self.preview_stack.setCurrentWidget(self.preview)
            self._shader_preview_draw_card(rec)
            self.info.append("\n⚙ Preview: symbolic shader intent card. This is not a Unity/Amplify decompile; it visualises the exposed property recipe.")

        def preview_material(self, rec):
            """Simple educational material preview.

            This is deliberately not a Unity shader emulator.  It shows the most
            useful visual ingredient: _BaseMap / _ColorMap / _MainTex when present, otherwise
            a base-colour swatch.  The inspector below remains the source of truth
            for full texture slots, shader, floats and colours.
            """
            try:
                self._hydrate_material_texture_refs_for_preview(rec)
            except Exception:
                pass

            saved = self._material_saved_properties(rec)
            try:
                shader_name = self._shader_preview_shader_name(rec)
                texture_slots_for_intent = self._shader_preview_texture_slot_names(saved)
                float_names_for_intent = set(self._shader_preview_material_float_values(saved).keys())
                intent = self._shader_preview_detect_intent(shader_name, float_names_for_intent.union(texture_slots_for_intent), texture_slots_for_intent)
                if str(intent.get("category", "surface")) in ("glass", "water", "foliage", "emissive"):
                    self._shader_preview_draw_card(rec, material_rec=rec, saved=saved)
                    self.statusBar().showMessage(f"Material intent preview: {rec.name} | {intent.get('title')}", 5000)
                    return
            except Exception:
                pass

            colour_name, colour_value = self._material_find_color(saved, "_BaseColor", "_Color", "_Tint")
            css_colour = self._material_color_to_css(colour_value) or "#808080"
            tex_name, tex_pptr, tex_pid = self._material_find_texture_slot(
                saved,
                "_BaseMap", "_ColorMap", "_MainTex", "_BaseColorMap",
                "_Albedo", "_BaseTex", "_MainTexture", "_BaseMap1",
            )
            tex_rec = self._ov_resolve(tex_pptr) if tex_pptr is not None else None
            if tex_rec is None and tex_pid not in (None, 0):
                tex_rec = self._hydrate_external_pathid_from_project_index(int(tex_pid))

            title = f"Material\n\n{rec.name}"
            float_text = self._material_key_float_text(saved)

            if tex_rec is not None and getattr(tex_rec, "type_name", "") == "Texture2D":
                try:
                    bundle_sha = self.bundle_index.sha256 if self.bundle_index else None
                    result = get_texture_preview(tex_rec, bundle_sha, size=900)
                    if result and Path(result.path).exists():
                        pix = QPixmap(str(result.path))
                        if not pix.isNull():
                            self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                            msg = f"Material preview: {rec.name} | {tex_name} → {tex_rec.name}"
                            if colour_name:
                                msg += f" | {colour_name} {css_colour}"
                            if float_text:
                                msg += f" | {float_text}"
                            self.statusBar().showMessage(msg, 5000)
                            return
                except Exception:
                    pass

            if tex_rec is not None and getattr(tex_rec, "type_name", "") == "Texture2DArray":
                self.preview.setText(
                    f"{title}\n\n"
                    f"Base texture slot: {tex_name}\n"
                    f"Texture array: {tex_rec.name}\n\n"
                    "This material uses a Texture2DArray.\n"
                    "The inspector shows _TextureIndex / slice information when present.\n\n"
                    f"Base colour: {colour_name or '-'} {css_colour}\n"
                    f"Key values: {float_text or '-'}"
                )
                return

            # A recognised base-colour slot exists, but the referenced texture is
            # outside the currently loaded/indexed bundle set.  Show the real cause
            # instead of making the grey fallback look like a shader failure.
            if tex_name and tex_pid not in (None, 0) and tex_rec is None:
                file_id = self._ov_pptr_file_id(tex_pptr)
                source_name = self._ov_pptr_external_source_name(tex_pptr)
                ref_bits = [f"PathID {tex_pid}"]
                if file_id not in (None, 0):
                    ref_bits.insert(0, f"FileID {file_id}")
                source_line = f"External SerializedFile: {source_name}\n" if source_name else ""
                self.preview.setText(
                    f"{title}\n\n"
                    f"Recognised base-colour slot: {tex_name}\n"
                    f"Texture reference: {', '.join(ref_bits)}\n"
                    f"{source_line}\n"
                    "The mesh/material data is present, but the colour texture is an external dependency that is not loaded.\n\n"
                    "Open or scan the game folder containing the dependency bundles and build/use the PathID index. "
                    "When the referenced texture is available, UBE will use this slot for object preview and OBJ/GLB export."
                )
                try:
                    self.statusBar().showMessage(
                        f"Material colour texture unresolved: {tex_name} → PathID {tex_pid}" +
                        (f" in {source_name}" if source_name else ""),
                        7000,
                    )
                except Exception:
                    pass
                return

            # No base texture: show a large colour swatch using QLabel rich text.
            self.preview.setTextFormat(Qt.RichText)
            self.preview.setText(
                "<div style='font-family: Segoe UI, Arial; color:#ddd; text-align:center'>"
                f"<h2>🎨 Material</h2>"
                f"<h3>{escape(rec.name)}</h3>"
                f"<div style='display:inline-block; width:240px; height:120px; "
                f"border:1px solid #666; border-radius:8px; background:{escape(css_colour)};'>&nbsp;</div>"
                f"<p>Base colour: {escape(colour_name or '-')} {escape(css_colour)}</p>"
                f"<p>Base texture: {escape(str(tex_name or '-'))}</p>"
                f"<p style='color:#aaa'>No previewable Texture2D base map was found. "
                f"Check the inspector for shader properties, texture slots and hidden/default values.</p>"
                f"<p style='color:#aaa'>{escape(float_text)}</p>"
                "</div>"
            )

        def _saved_vgmstream_path(self) -> str:
            try:
                value = QSettings("UBE", "UnityBundleExplorer").value("vgmstream_cli_path", "")
                return str(value or "")
            except Exception:
                return ""

        def _set_audio_message(self, extra: str = "") -> None:
            text = str(self.audio_base_text or "")
            if extra:
                text += "\n\n" + str(extra).strip()
            self.audio_label.setText(text or "Select an AudioClip")

        def _clear_audio_media_source(self, *, wait_for_release: bool = False) -> None:
            """Stop playback and make Qt/FFmpeg release the current preview file."""
            if self.audio_player is not None:
                try:
                    self.audio_player.stop()
                    self.audio_player.setSource(QUrl())
                except Exception:
                    pass

            # QMediaPlayer releases its backend source asynchronously.  Windows
            # will refuse to remove a temporary WAV until FFmpeg has closed the
            # handle, so process a few event turns before deleting preview files.
            if wait_for_release:
                for _ in range(5):
                    try:
                        QApplication.processEvents()
                    except Exception:
                        break
                    time.sleep(0.01)

        def _cleanup_audio_preview_temp(self, *, wait_for_release: bool = True) -> None:
            """Release playback and explicitly retire the audio preview folder."""
            temp_dir = self.audio_temp_dir
            self.audio_temp_dir = None
            if temp_dir is None:
                return

            self._clear_audio_media_source(wait_for_release=wait_for_release)
            try:
                temp_dir.cleanup()
            except Exception:
                # Current preview folders are created with
                # ignore_cleanup_errors=True.  This fallback also protects a
                # folder created by an older in-memory code path during reload.
                try:
                    finalizer = getattr(temp_dir, "_finalizer", None)
                    if finalizer is not None:
                        finalizer.detach()
                except Exception:
                    pass

        def _shutdown_audio_preview(self) -> None:
            """Final audio teardown used by both window close and app shutdown."""
            if self._audio_shutdown_done:
                return
            self._audio_shutdown_done = True

            self._clear_audio_media_source(wait_for_release=True)

            # Detach the audio sink and destroy the multimedia objects before
            # asking Windows to remove the temporary WAV.
            player = self.audio_player
            output = self.audio_output
            if player is not None:
                try:
                    player.setAudioOutput(None)
                except Exception:
                    pass
                try:
                    player.deleteLater()
                except Exception:
                    pass
            if output is not None:
                try:
                    output.deleteLater()
                except Exception:
                    pass
            self.audio_player = None
            self.audio_output = None

            try:
                QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            except Exception:
                pass
            for _ in range(3):
                try:
                    QApplication.processEvents()
                except Exception:
                    break
                time.sleep(0.01)

            self._cleanup_audio_preview_temp(wait_for_release=False)

        def closeEvent(self, event) -> None:
            self._shutdown_audio_preview()
            super().closeEvent(event)

        def _selected_audio_subsong(self) -> int:
            try:
                value = self.audio_subsong_combo.currentData()
                if value is not None:
                    return max(1, int(value))
            except Exception:
                pass
            return 1

        def _selected_audio_subsong_text(self) -> str:
            subsong = self._selected_audio_subsong()
            try:
                label = self.audio_subsong_combo.currentText().strip()
            except Exception:
                label = ""
            return label or f"Sample {subsong}"

        def choose_audio_decoder(self) -> None:
            start = self._saved_vgmstream_path()
            if start:
                try:
                    start = str(Path(start).parent)
                except Exception:
                    pass
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Locate vgmstream command-line decoder",
                start,
                "vgmstream CLI (vgmstream-cli.exe vgmstream-cli);;Executable files (*.exe);;All files (*.*)",
            )
            if not path:
                return

            decoder = find_vgmstream_cli(path)
            if decoder is None:
                QMessageBox.warning(self, "Decoder not found", "The selected vgmstream executable could not be used.")
                return

            self.audio_decoder_path = decoder
            try:
                QSettings("UBE", "UnityBundleExplorer").setValue("vgmstream_cli_path", str(decoder))
            except Exception:
                pass

            result = self.audio_preview_result
            if result is not None and str(getattr(result, "container", "")).upper().startswith("FMOD FSB5"):
                self.audio_play_button.setEnabled(self.audio_player is not None)
                self._set_audio_message(
                    f"Decoder: {decoder}\n"
                    f"Selected: {self._selected_audio_subsong_text()}\n"
                    "Click Play; UBE will decode this FSB5 sample to a temporary WAV."
                )
            else:
                self.statusBar().showMessage(f"vgmstream decoder saved: {decoder}", 3500)

        def on_audio_subsong_changed(self, _index: int = -1) -> None:
            result = self.audio_preview_result
            if result is None or not str(getattr(result, "container", "")).upper().startswith("FMOD FSB5"):
                return
            self._clear_audio_media_source()
            self.audio_decoded_path = None
            self.audio_decoded_subsong = None
            self.audio_stop_button.setEnabled(False)
            self.audio_play_button.setEnabled(self.audio_player is not None and self.audio_decoder_path is not None)
            decoder_line = f"Decoder: {self.audio_decoder_path}" if self.audio_decoder_path else "Decoder: not found"
            self._set_audio_message(
                f"{decoder_line}\n"
                f"Selected: {self._selected_audio_subsong_text()}\n"
                "Click Play to decode this sample to a temporary WAV."
            )

        def stop_current_audio(self) -> None:
            if self.audio_player is not None:
                try:
                    self.audio_player.stop()
                except Exception:
                    pass
            self.audio_stop_button.setEnabled(self.audio_player is not None and self.audio_decoded_path is not None)

        def play_current_audio(self) -> None:
            if self.audio_player is None:
                self._set_audio_message("Qt Multimedia audio playback is unavailable in this Python/PySide6 installation.")
                return

            result = self.audio_preview_result
            if result is None:
                return

            is_fsb5 = str(getattr(result, "container", "")).upper().startswith("FMOD FSB5")
            if not is_fsb5:
                try:
                    self.audio_player.play()
                    self.audio_stop_button.setEnabled(True)
                except Exception as exc:
                    self._set_audio_message(f"Playback failed: {exc}")
                return

            subsong = self._selected_audio_subsong()
            if self.audio_decoded_path is not None and self.audio_decoded_subsong == subsong and Path(self.audio_decoded_path).is_file():
                self.audio_player.setSource(QUrl.fromLocalFile(str(self.audio_decoded_path)))
                self.audio_player.play()
                self.audio_stop_button.setEnabled(True)
                self._set_audio_message(
                    f"Decoder: {self.audio_decoder_path}\n"
                    f"Playing: {self._selected_audio_subsong_text()}\n"
                    f"Temporary WAV: {self.audio_decoded_path}"
                )
                return

            raw_path = getattr(result, "raw_path", None)
            if raw_path is None or not Path(raw_path).is_file():
                self._set_audio_message("The temporary FSB5 source is no longer available. Select the AudioClip again.")
                return

            decoder = find_vgmstream_cli(self.audio_decoder_path or self._saved_vgmstream_path())
            self.audio_decoder_path = decoder
            if decoder is None:
                self.audio_play_button.setEnabled(False)
                self._set_audio_message(
                    "vgmstream-cli was not found. Click Locate vgmstream and select vgmstream-cli.exe, "
                    "or put the complete vgmstream folder beside UBE / under Tools\\vgmstream."
                )
                return

            raw_path = Path(raw_path)
            output_path = raw_path.with_name(f"{raw_path.stem}__sample_{subsong}.wav")
            self.audio_play_button.setEnabled(False)
            self.audio_stop_button.setEnabled(False)
            self._set_audio_message(
                f"Decoder: {decoder}\n"
                f"Decoding {self._selected_audio_subsong_text()} to a temporary WAV..."
            )

            def decode_work(report):
                report(f"Decoding FSB5 audio sample {subsong} with vgmstream...")
                return decode_with_vgmstream(
                    raw_path,
                    output_path,
                    subsong=subsong,
                    decoder_path=decoder,
                )

            tree_was_enabled = self.tree.isEnabled()
            self.tree.setEnabled(False)
            try:
                decode_result = self._run_loading_task_responsive(
                    f"Decoding FSB5 audio sample {subsong}...",
                    decode_work,
                )
            except Exception as exc:
                decode_result = None
                error_text = str(exc)
            else:
                error_text = ""
            finally:
                self.tree.setEnabled(tree_was_enabled)

            self.audio_play_button.setEnabled(True)
            if decode_result is None or not decode_result.ok or decode_result.output_path is None:
                message = error_text or (decode_result.message if decode_result is not None else "Unknown decoder error")
                self.audio_stop_button.setEnabled(False)
                self._set_audio_message(
                    f"Decoder: {decoder}\n"
                    f"Could not decode {self._selected_audio_subsong_text()}:\n{message}"
                )
                self.statusBar().showMessage("FSB5 audio decode failed", 4000)
                return

            self.audio_decoded_path = decode_result.output_path
            self.audio_decoded_subsong = subsong
            self.audio_player.setSource(QUrl.fromLocalFile(str(decode_result.output_path)))
            self.audio_player.play()
            self.audio_stop_button.setEnabled(True)
            self._set_audio_message(
                f"Decoder: {decoder}\n"
                f"Playing: {self._selected_audio_subsong_text()}\n"
                f"Temporary WAV: {decode_result.output_path}"
            )
            self.statusBar().showMessage("FSB5 audio ready", 2500)

        def preview_audio(self, rec):
            ad = audio_details(rec)
            self._cleanup_audio_preview_temp(wait_for_release=True)
            self.audio_play_button.setEnabled(False)
            self.audio_stop_button.setEnabled(False)
            self.audio_decoder_button.setEnabled(False)
            self.audio_subsong_row.setVisible(False)
            self.audio_subsong_combo.blockSignals(True)
            self.audio_subsong_combo.clear()
            self.audio_subsong_combo.blockSignals(False)
            self.audio_preview_result = None
            self.audio_fsb_info = None
            self.audio_decoder_path = None
            self.audio_decoded_path = None
            self.audio_decoded_subsong = None
            self.audio_base_text = ""

            if ad is None:
                self.audio_label.setText("Audio metadata could not be read")
                return

            import tempfile

            self.audio_temp_dir = tempfile.TemporaryDirectory(
                prefix="ube_audio_preview_",
                ignore_cleanup_errors=True,
            )

            def prepare_audio_work(report):
                report(f"Preparing AudioClip preview — {rec.name}...")
                return export_audio_record(rec, self.audio_temp_dir.name)

            tree_was_enabled = self.tree.isEnabled()
            self.tree.setEnabled(False)
            try:
                result = self._run_loading_task_responsive(
                    f"Preparing AudioClip preview — {rec.name}...",
                    prepare_audio_work,
                )
            except Exception as exc:
                self.audio_base_text = f"AudioClip\n\n{rec.name}\n\nPreview preparation failed: {exc}"
                self._set_audio_message()
                return
            finally:
                self.tree.setEnabled(tree_was_enabled)
            self.audio_preview_result = result

            length = "-"
            if ad.length is not None:
                try:
                    length = f"{float(ad.length):.3f}s"
                except Exception:
                    length = str(ad.length)

            text = (
                f"AudioClip\n\n{rec.name}\n\n"
                f"Length: {length}\n"
                f"Channels: {ad.channels if ad.channels is not None else '-'}\n"
                f"Frequency: {ad.frequency if ad.frequency is not None else '-'} Hz\n"
            )

            if not result.ok:
                text += f"\nPreview unavailable:\n{result.message}"
                self.audio_base_text = text
                self._set_audio_message()
                return

            text += f"\nContainer: {result.container}\n"
            if getattr(result, "resource_path", None):
                text += f"External resource: {result.resource_path}\n"
            text += f"Preview/export temp: {result.raw_path}\n"
            is_fsb5 = str(result.container).upper().startswith("FMOD FSB5")

            if not is_fsb5:
                self.audio_base_text = text
                if result.playable_path and self.audio_player is not None:
                    self.audio_player.setSource(QUrl.fromLocalFile(str(result.playable_path)))
                    self.audio_play_button.setEnabled(True)
                    self.audio_stop_button.setEnabled(True)
                    self._set_audio_message("Playable here: yes")
                elif self.audio_player is None:
                    self._set_audio_message("Playable here: no — Qt Multimedia is unavailable.")
                else:
                    self._set_audio_message(
                        "Playable here: no — this original container is not directly supported by Qt. "
                        "Use Export Selected Asset to save it."
                    )
                return

            # FSB5 containers need their codec/setup data reconstructed.  UBE
            # keeps the raw FSB for export and uses vgmstream only as an optional
            # temporary decoder when the user clicks Play.
            self.audio_decoder_button.setEnabled(True)
            fsb_error = ""
            try:
                self.audio_fsb_info = inspect_fsb5_file(result.raw_path)
            except Exception as exc:
                self.audio_fsb_info = None
                fsb_error = str(exc)

            if self.audio_fsb_info is not None:
                info = self.audio_fsb_info
                text += (
                    f"FSB5 version: {info.version}\n"
                    f"FSB5 codec: {info.format_name}\n"
                    f"FSB5 samples/subsongs: {info.sample_count}\n"
                )
                self.audio_subsong_combo.blockSignals(True)
                self.audio_subsong_combo.clear()
                if info.samples:
                    for sample in info.samples:
                        duration = sample.duration_seconds
                        detail_parts = [sample.name]
                        if sample.frequency:
                            detail_parts.append(f"{sample.frequency:,} Hz")
                        detail_parts.append(f"{sample.channels} ch")
                        if duration is not None:
                            detail_parts.append(f"{duration:.3f}s")
                        self.audio_subsong_combo.addItem(" — ".join(detail_parts), sample.index + 1)
                else:
                    for index in range(max(1, info.sample_count)):
                        self.audio_subsong_combo.addItem(f"Sample {index + 1}", index + 1)
                self.audio_subsong_combo.setCurrentIndex(0)
                self.audio_subsong_combo.blockSignals(False)
                self.audio_subsong_row.setVisible(True)
            else:
                text += f"FSB5 parser note: {fsb_error}\n"
                self.audio_subsong_combo.blockSignals(True)
                self.audio_subsong_combo.addItem("Sample 1", 1)
                self.audio_subsong_combo.setCurrentIndex(0)
                self.audio_subsong_combo.blockSignals(False)
                self.audio_subsong_row.setVisible(True)

            self.audio_base_text = text
            self.audio_decoder_path = find_vgmstream_cli(self._saved_vgmstream_path())
            if self.audio_player is None:
                self._set_audio_message(
                    "FSB5 detected, but Qt Multimedia is unavailable in this Python/PySide6 installation."
                )
                return

            if self.audio_decoder_path is None:
                self.audio_play_button.setEnabled(False)
                self._set_audio_message(
                    "FSB5 detected. vgmstream-cli was not found.\n"
                    "Click Locate vgmstream and select vgmstream-cli.exe, or place the complete "
                    "vgmstream folder beside UBE / inside Tools\\vgmstream."
                )
                return

            self.audio_play_button.setEnabled(True)
            self._set_audio_message(
                f"Decoder: {self.audio_decoder_path}\n"
                f"Selected: {self._selected_audio_subsong_text()}\n"
                "Click Play; UBE will decode the selected FSB5 sample to a temporary WAV."
            )

        def _ube_material_summary(self, rec, plain: str) -> str:

            shader = getattr(rec, "shader", "").lower()
            text = plain.lower()

            summary = ["🧠 UBE Material Insight"]

            # --- TYPE LOGIC ---
            if "transparent" in shader or "alpha" in text:
                summary.append("• Likely Transparent material (glass / liquid / UI)")

            elif "emission" in text or "emissive" in shader:
                summary.append("• Likely Emissive material (glow / lights / effects)")

            else:
                summary.append("• Likely Opaque material (solid surface)")

            # --- TEXTURE HINTS ---
            if "normal" in text or "bump" in text:
                summary.append("• Uses Normal Map (surface detail present)")

            if "metal" in text or "smooth" in text:
                summary.append("• Uses Metallic / Smoothness response")

            return "\n".join(summary) + "\n\n" + plain

        def choose_inspector_report_options(self, records: list, title: str):
            dialog = QDialog(self)
            dialog.setWindowTitle(title)
            dialog.resize(620, 210)
            layout = QVBoxLayout(dialog)

            count = len(records)
            explanation = QLabel(
                f"Export the inspector display for {count} asset{'s' if count != 1 else ''} as readable UTF-8 HTML. "
                "The report includes the asset identity, decoded inspector data, relationships exposed by UBE, and external comments."
            )
            explanation.setWordWrap(True)
            layout.addWidget(explanation)

            form = QFormLayout()
            folder_row = QWidget(dialog)
            folder_layout = QHBoxLayout(folder_row)
            folder_layout.setContentsMargins(0, 0, 0, 0)
            folder_edit = QLineEdit(dialog)
            start = self.last_export_folder
            if not start and self.bundle_index is not None:
                try:
                    start = str(Path(self.bundle_index.path).parent)
                except Exception:
                    start = ""
            folder_edit.setText(start)
            folder_button = QPushButton("Browse...", dialog)
            folder_layout.addWidget(folder_edit, 1)
            folder_layout.addWidget(folder_button)
            form.addRow("Output folder:", folder_row)

            output_combo = QComboBox(dialog)
            output_combo.addItem("One combined HTML report", "combined")
            if count > 1:
                output_combo.addItem("One HTML file per asset", "separate")
            form.addRow("Output:", output_combo)
            layout.addLayout(form)

            hint = QLabel(
                "Combined HTML is recommended for AnimationClip/type branches: it adds a linked contents list and keeps the entire investigation in one file."
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
            layout.addWidget(buttons)

            def browse_folder():
                folder = QFileDialog.getExistingDirectory(dialog, title, folder_edit.text().strip() or start)
                if folder:
                    folder_edit.setText(folder)

            folder_button.clicked.connect(browse_folder)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)

            if dialog.exec() != QDialog.Accepted:
                return None
            folder = folder_edit.text().strip()
            if not folder:
                QMessageBox.information(self, "No report folder", "Choose an output folder before exporting the inspector report.")
                return None
            self.last_export_folder = folder
            return {"folder": folder, "output_mode": output_combo.currentData() or "combined"}

        def _inspector_report_bundle_metadata(self) -> dict:
            idx = self.bundle_index
            if idx is None:
                return {"bundle_name": "", "bundle_sha256": "", "unity_version": "", "source_kind": ""}
            header = getattr(idx, "header", None)
            try:
                bundle_name = Path(getattr(idx, "path", "")).name
            except Exception:
                bundle_name = str(getattr(idx, "path", "") or "")
            unity_version = str(
                getattr(header, "unity_revision", "")
                or getattr(header, "unity_version", "")
                or ""
            )
            return {
                "bundle_name": bundle_name,
                "bundle_sha256": str(getattr(idx, "sha256", "") or ""),
                "unity_version": unity_version,
                "source_kind": str(getattr(header, "source_kind", "") or ""),
            }

        def _inspector_report_entry(self, rec) -> dict:
            try:
                inspector_text = describe_record(rec, self.bundle_index, self.asset_graph, include_relationships=True)
            except Exception as exc:
                inspector_text = (
                    f"🏷 Name: {getattr(rec, 'name', 'Unnamed asset')}\n"
                    f"🧩 Asset type: {friendly_type_name(getattr(rec, 'type_name', 'Asset'))}\n"
                    f"# Path ID: {getattr(rec, 'path_id', '')}\n\n"
                    f"Inspector report generation failed: {exc}"
                )
            return {
                "name": str(getattr(rec, "name", "") or "Unnamed asset"),
                "asset_type": friendly_type_name(str(getattr(rec, "type_name", "") or "Asset")),
                "unity_type": str(getattr(rec, "type_name", "") or ""),
                "source_name": str(getattr(rec, "source_name", "") or ""),
                "path_id": getattr(rec, "path_id", ""),
                "comment": self.comment_store.get(rec) if self.comment_store is not None else "",
                "inspector_text": inspector_text,
            }

        def export_inspector_reports(self, records: list, title: str, report_label: str = "Assets"):
            rows = self.unique_records(records)
            if not rows:
                QMessageBox.information(self, "Nothing to report", "No assets were found for this inspector report.")
                return
            options = self.choose_inspector_report_options(rows, title)
            if not options:
                return

            folder = options.get("folder", "")
            output_mode = options.get("output_mode", "combined")
            metadata = self._inspector_report_bundle_metadata()
            bundle_stem = Path(metadata.get("bundle_name", "bundle") or "bundle").stem
            clean_label = report_label or "Assets"
            report_title = f"UBE Inspector Report — {clean_label}"
            base_name = safe_report_filename(f"{bundle_stem} - {clean_label} - UBE Inspector Report")

            try:
                self.statusBar().showMessage(f"Building inspector report for {len(rows)} asset(s)...")
                entries = []
                for index, rec in enumerate(rows, start=1):
                    entries.append(self._inspector_report_entry(rec))
                    if index % 10 == 0:
                        self.statusBar().showMessage(f"Building inspector report: {index}/{len(rows)}")
                        QApplication.processEvents()

                if output_mode == "separate" and len(entries) > 1:
                    paths = write_separate_html_reports(entries, folder, **metadata)
                else:
                    paths = [write_combined_html_report(
                        entries,
                        folder,
                        base_name,
                        report_title,
                        **metadata,
                    )]
            except Exception as exc:
                QMessageBox.warning(self, "Inspector report failed", f"Could not write the HTML inspector report.\n\n{exc}")
                self.statusBar().showMessage("Inspector report failed", 5000)
                return

            self.statusBar().showMessage(f"Inspector report exported: {len(paths)} HTML file(s)", 6000)
            if len(paths) == 1:
                QMessageBox.information(
                    self,
                    "Inspector report exported",
                    f"Exported a readable HTML inspector report for {len(rows)} asset(s) to:\n{paths[0]}",
                )
            else:
                QMessageBox.information(
                    self,
                    "Inspector reports exported",
                    f"Exported {len(paths)} HTML inspector report files to:\n{folder}",
                )

        def export_supported_for_record(self, rec) -> bool:
            return bool(rec is not None and getattr(rec, "type_name", "") in ("Texture2D", "Texture2DArray", "Cubemap", "Mesh", "AudioClip", "Sprite", "SpriteRenderer", "GameObject", "Transform", "MeshFilter", "MeshRenderer", "SkinnedMeshRenderer"))

        def unique_records(self, records: list) -> list:
            """De-duplicate Unity records using their local SerializedFile identity."""
            seen = set()
            out = []
            for rec in records or []:
                key = (
                    getattr(rec, "type_name", ""),
                    getattr(rec, "source_name", ""),
                    getattr(rec, "path_id", id(rec)),
                )
                if key in seen:
                    continue
                seen.add(key)
                out.append(rec)
            return out

        def collect_records_under_item(self, item) -> list:
            records = []
            if item is None:
                return records
            data = item.data(0, Qt.UserRole)
            if data is not None and not isinstance(data, tuple):
                records.append(data)
            for i in range(item.childCount()):
                records.extend(self.collect_records_under_item(item.child(i)))
            return records

        def collect_exportable_records_under_item(self, item) -> list:
            return [rec for rec in self.collect_records_under_item(item) if self.export_supported_for_record(rec)]

        def collect_visible_records_under_item(self, item) -> list:
            """Collect records that are currently visible after the quick filter.

            This is intentionally based on the QTreeWidget hidden state, so the
            export follows exactly what the user sees after typing in the search
            box.  Branch/container items that are visible only because a child
            matched are traversed, but hidden children are skipped.
            """
            records = []
            if item is None or item.isHidden():
                return records
            data = item.data(0, Qt.UserRole)
            if data is not None and not isinstance(data, tuple):
                records.append(data)
            for i in range(item.childCount()):
                child = item.child(i)
                if child is not None and not child.isHidden():
                    records.extend(self.collect_visible_records_under_item(child))
            return records

        def collect_visible_records_in_tree(self) -> list:
            records = []
            for i in range(self.tree.topLevelItemCount()):
                records.extend(self.collect_visible_records_under_item(self.tree.topLevelItem(i)))
            return self.unique_records(records)

        def collect_visible_exportable_records_under_item(self, item) -> list:
            seen = set()
            out = []
            for rec in self.collect_visible_records_under_item(item):
                if not self.export_supported_for_record(rec):
                    continue
                key = (getattr(rec, "type_name", ""), getattr(rec, "source_name", ""), getattr(rec, "path_id", id(rec)))
                if key in seen:
                    continue
                seen.add(key)
                out.append(rec)
            return out

        def collect_visible_exportable_records_in_tree(self) -> list:
            seen = set()
            out = []
            for i in range(self.tree.topLevelItemCount()):
                for rec in self.collect_visible_records_under_item(self.tree.topLevelItem(i)):
                    if not self.export_supported_for_record(rec):
                        continue
                    key = (getattr(rec, "type_name", ""), getattr(rec, "source_name", ""), getattr(rec, "path_id", id(rec)))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(rec)
            return out

        def current_tree_filter_text(self) -> str:
            parts = []
            try:
                global_text = (self.search.text() or "").strip()
            except Exception:
                global_text = ""
            if global_text:
                parts.append(global_text)
            branch_text = (getattr(self, "branch_filter_text", "") or "").strip()
            if branch_text:
                label = getattr(self, "branch_filter_label", "") or "branch"
                parts.append(f"{label}: {branch_text}")
            isolated_type = str(getattr(self, "isolated_asset_type", "") or "")
            if isolated_type:
                parts.insert(0, f"Asset type: {friendly_type_name(isolated_type)}")
            return " + ".join(parts)

        def collect_exportable_records_in_bundle(self) -> list:
            if not self.bundle_index:
                return []
            records = []
            for group in self.bundle_index.objects_by_type.values():
                for rec in group:
                    if self.export_supported_for_record(rec):
                        records.append(rec)
            return records

        def _record_is_mesh_export(self, rec) -> bool:
            return getattr(rec, "type_name", "") == "Mesh" or getattr(rec, "type_name", "") in self.object_view_types()

        def _record_export_family(self, rec) -> str:
            t = str(getattr(rec, "type_name", "") or "")
            if t in self.object_view_types() or t == "Mesh":
                return "mesh"
            if t == "Sprite":
                return "sprite"
            if t == "SpriteRenderer":
                return "sprite_renderer"
            if t == "Texture2D":
                return "texture"
            if t == "Cubemap":
                return "cubemap"
            if t == "Texture2DArray":
                return "texture_array"
            if t == "AudioClip":
                return "audio"
            return "other"

        def _export_family_set(self, records: list) -> set[str]:
            return {self._record_export_family(r) for r in records if r is not None}

        def _native_export_format_label(self, records: list) -> str:
            families = self._export_family_set(records)
            if families and families <= {"sprite"}:
                return "PNG sprite images + JSON metadata"
            if families and families <= {"sprite", "sprite_renderer"}:
                return "PNG sprite images + JSON metadata"
            if families and families <= {"texture"}:
                return "PNG textures + JSON metadata"
            if families and families <= {"cubemap"}:
                return "PNG cubemap/contact-sheet + JSON metadata"
            if families and families <= {"texture_array"}:
                return "PNG texture-array slices + JSON metadata"
            if families and families <= {"texture", "sprite", "sprite_renderer", "cubemap", "texture_array"}:
                return "PNG image assets + JSON metadata"
            if families and families <= {"audio"}:
                return "AudioClip native export"
            return "Auto / native per asset"

        def _export_options_hint(self, records: list, output_mode: str = "separate") -> str:
            families = self._export_family_set(records)
            count = len(records)
            if not records:
                return "Choose an output folder."

            has_mesh = "mesh" in families
            has_only_mesh = has_mesh and families <= {"mesh"}
            combined_mesh_export = count >= 2 and has_only_mesh

            if combined_mesh_export:
                if output_mode == "combined":
                    return (
                        "Combined mesh/object export:\n"
                        f"• All {count} results are written into one assembly; this is not limited by the four-object preview.\n"
                        "• GLB writes one binary glTF scene containing the assets as separate nodes.\n"
                        "• OBJ writes one combined OBJ/MTL assembly plus texture files.\n"
                        "• Shared Unity/authored coordinates are preserved; parts are not individually re-centred.\n"
                        "• Mesh/OBJ/GLB export uses View → Ground / Up Axis so the external file can match the 3D preview."
                    )
                return (
                    "Separate mesh/object export:\n"
                    f"• Each of the {count} results is exported independently.\n"
                    "• GLB creates one .glb file per asset, with embedded textures where possible.\n"
                    "• OBJ creates one OBJ/MTL package per asset plus its referenced texture files.\n"
                    "• Assets keep their own names; duplicate filenames are disambiguated with Path ID.\n"
                    "• Mesh/OBJ/GLB export uses View → Ground / Up Axis so the external files can match the 3D preview."
                )

            if has_mesh:
                return (
                    "Mesh/object export:\n"
                    "• OBJ/MTL exports mesh geometry, materials, textures, metadata and logs.\n"
                    "• GLB exports a single binary glTF file with embedded textures where possible.\n"
                    "• Export uses View → Ground / Up Axis so the external file can match the 3D preview.\n"
                    "• Non-mesh assets in a mixed selection use their native export route."
                )

            if families <= {"sprite"}:
                return (
                    "Sprite export:\n"
                    "• Each Sprite is exported as a cropped PNG where UnityPy can decode the source texture.\n"
                    "• JSON metadata is written beside the image, including rect, pivot, PPU and source texture details.\n"
                    "• Output normally goes under Sprites/.\n"
                    "• OBJ/GLB options do not apply to Sprite-only exports."
                )

            if families <= {"sprite", "sprite_renderer"}:
                return (
                    "Sprite/SpriteRenderer export:\n"
                    "• Sprites are exported as PNG images where the source texture can be resolved.\n"
                    "• SpriteRenderer exports follow the linked Sprite where possible.\n"
                    "• JSON metadata is written for reference.\n"
                    "• Output normally goes under Sprites/."
                )

            if families <= {"texture"}:
                return (
                    "Texture2D export:\n"
                    "• Each texture is exported as PNG where the decoder exposes image pixels.\n"
                    "• JSON metadata records size, format, mip/stream hints and source details.\n"
                    "• Output normally goes under Textures/."
                )

            if families <= {"cubemap"}:
                return (
                    "Cubemap export:\n"
                    "• Cubemaps are exported as PNG/contact-sheet style images where the decoder exposes faces.\n"
                    "• JSON metadata records face size, texture format and stream hints.\n"
                    "• Cubemaps are environment images, not normal flat UV textures."
                )

            if families <= {"texture_array"}:
                return (
                    "Texture2DArray export:\n"
                    "• Slices are exported as PNG images where the decoder exposes them.\n"
                    "• JSON metadata records array size, slice count and texture format.\n"
                    "• Output normally goes under TextureArrays/."
                )

            if families <= {"texture", "sprite", "sprite_renderer", "cubemap", "texture_array"}:
                return (
                    "Image asset export:\n"
                    "• Textures, sprites, cubemaps and texture arrays use their native PNG-based export paths.\n"
                    "• JSON metadata is written for reference.\n"
                    "• OBJ/GLB options only apply to mesh/object exports, not image-only selections."
                )

            if families <= {"audio"}:
                return (
                    "AudioClip export:\n"
                    "• Audio clips are exported to their native/decoded audio form where UnityPy exposes the data.\n"
                    "• Output normally goes under Audio/.\n"
                    "• OBJ/GLB options do not apply to AudioClip-only exports."
                )

            return (
                "Mixed native export:\n"
                "• Each asset uses the best export path for its own Unity type.\n"
                "• Textures and sprites export as PNG/JSON.\n"
                "• Audio exports under Audio/.\n"
                "• Meshes/objects can use OBJ/GLB when that format is selected."
            )

        def _export_completion_hint(self, records: list) -> str:
            families = self._export_family_set(records)
            if families <= {"sprite"}:
                return "Sprites are saved as PNG images plus JSON metadata under Sprites/."
            if families <= {"sprite", "sprite_renderer"}:
                return "Sprites/SpriteRenderers are saved as PNG images plus JSON metadata under Sprites/."
            if families <= {"texture"}:
                return "Textures are saved as PNG images plus JSON metadata under Textures/."
            if families <= {"cubemap"}:
                return "Cubemaps are saved as PNG/contact-sheet images plus JSON metadata where available."
            if families <= {"texture_array"}:
                return "Texture arrays are saved as PNG slice images plus JSON metadata under TextureArrays/."
            if families <= {"texture", "sprite", "sprite_renderer", "cubemap", "texture_array"}:
                return "Image assets are saved through their PNG-based native export paths."
            if families <= {"audio"}:
                return "Audio clips are saved under Audio/ in the original container or decoded WAV format selected in Export Options."
            if families <= {"mesh"}:
                return f"Mesh/object exports used ground/up axis: {self._current_ground_up_axis()}."
            return (
                f"Native export completed. Mesh/object exports used ground/up axis: {self._current_ground_up_axis()}. "
                "Textures, sprites, texture arrays, meshes/object meshes and audio are saved under their matching output folders."
            )


        def choose_export_options(self, records: list, title: str, default_mesh_mode: str = "separate") -> dict | None:
            """Choose the output folder, mesh format and batch output mode.

            Multi-record mesh/object exports can either be written as independent
            assets or merged into one authored-coordinate assembly.  Native image,
            audio and mixed exports remain independent by definition.
            """
            dialog = QDialog(self)
            dialog.setWindowTitle("Export Options")
            dialog.setModal(True)
            layout = QVBoxLayout(dialog)

            label = QLabel("Choose an output folder, export format and output mode.")
            layout.addWidget(label)

            form = QFormLayout()
            folder_row = QHBoxLayout()
            folder_edit = QLineEdit(dialog)
            folder_edit.setText(self.last_export_folder or "")
            folder_button = QPushButton("Browse...", dialog)
            folder_row.addWidget(folder_edit, 1)
            folder_row.addWidget(folder_button)
            form.addRow("Folder:", folder_row)

            format_combo = QComboBox(dialog)
            has_mesh = any(self._record_is_mesh_export(rec) for rec in records)
            has_only_mesh = has_mesh and all(self._record_is_mesh_export(rec) for rec in records)
            multi_mesh_export = len(records) >= 2 and has_only_mesh
            families = self._export_family_set(records)
            audio_only = bool(families and families <= {"audio"})
            available_audio_decoder = find_vgmstream_cli(
                self.audio_decoder_path or self._saved_vgmstream_path()
            ) if audio_only else None

            if audio_only:
                format_combo.addItem("Original Unity audio container  (.fsb/.ogg/.wav/etc.)", "audio_native")
                wav_index = format_combo.count()
                if available_audio_decoder is not None:
                    format_combo.addItem("Decoded standard WAV via vgmstream  (.wav)", "audio_wav")
                else:
                    format_combo.addItem("Decoded WAV unavailable — locate vgmstream first", "audio_wav_unavailable")
                    try:
                        item = format_combo.model().item(wav_index)
                        if item is not None:
                            item.setEnabled(False)
                    except Exception:
                        pass
            elif has_mesh:
                # For a mesh batch, keep GLB first because it is the cleanest
                # one-file-per-asset route and the existing combined default.
                if multi_mesh_export:
                    glb_index = format_combo.count()
                    format_combo.addItem("GLB / glTF binary  (.glb, embedded textures)", "glb")
                    format_combo.addItem("OBJ / MTL + textures", "obj")
                else:
                    format_combo.addItem("OBJ / MTL + textures", "obj")
                    glb_index = format_combo.count()
                    format_combo.addItem("GLB / glTF binary  (.glb, embedded textures)", "glb")
                try:
                    format_combo.setItemData(
                        glb_index,
                        "Exports binary glTF with embedded base and normal/bump textures where available.",
                        Qt.ToolTipRole,
                    )
                except Exception:
                    pass
                if not has_only_mesh:
                    format_combo.addItem(self._native_export_format_label(records), "auto")
            else:
                format_combo.addItem(self._native_export_format_label(records), "auto")
            form.addRow("Format:", format_combo)

            output_combo = None
            if multi_mesh_export:
                output_combo = QComboBox(dialog)
                output_combo.addItem(
                    f"Separate assets  ({len(records)} individual exports)",
                    "separate",
                )
                output_combo.addItem(
                    f"Combined assembly  (all {len(records)} assets in one model)",
                    "combined",
                )
                wanted_mode = "combined" if str(default_mesh_mode).lower() == "combined" else "separate"
                wanted_index = output_combo.findData(wanted_mode)
                if wanted_index >= 0:
                    output_combo.setCurrentIndex(wanted_index)
                try:
                    output_combo.setItemData(
                        output_combo.findData("separate"),
                        "Writes every filtered/selected asset independently. GLB creates one .glb per asset; OBJ creates one OBJ/MTL package per asset.",
                        Qt.ToolTipRole,
                    )
                    output_combo.setItemData(
                        output_combo.findData("combined"),
                        "Writes every selected result into one authored-coordinate assembly. Unlike the preview, export is not limited to four assets.",
                        Qt.ToolTipRole,
                    )
                except Exception:
                    pass
                form.addRow("Output:", output_combo)

            layout.addLayout(form)

            def export_hint_text() -> str:
                mode = output_combo.currentData() if output_combo is not None else "separate"
                selected_format = str(format_combo.currentData() or "auto")
                if audio_only:
                    if selected_format == "audio_wav":
                        sample_note = ""
                        if len(records) == 1:
                            sample_note = f"\n• Current FSB5 selection: {self._selected_audio_subsong_text()}."
                        else:
                            sample_note = "\n• Batch WAV export decodes sample/subsong 1 from each AudioClip."
                        return (
                            "Decoded WAV export:\n"
                            "• vgmstream converts the Unity/FSB audio into a normal RIFF/WAV file.\n"
                            "• The original game data is not changed.\n"
                            "• Output is saved under Audio/ with JSON metadata."
                            + sample_note
                        )
                    decoder_note = "" if available_audio_decoder is not None else (
                        "\n• WAV conversion becomes available after vgmstream is located in the AudioClip preview."
                    )
                    return (
                        "Original audio export:\n"
                        "• Preserves the exact Unity audio container (.fsb/.ogg/.wav/etc.).\n"
                        "• An FSB bank keeps all of its internal samples/subsongs together.\n"
                        "• Output is saved under Audio/ with JSON metadata."
                        + decoder_note
                    )
                return self._export_options_hint(records, mode or "separate")

            hint = QLabel(export_hint_text())
            hint.setWordWrap(True)
            layout.addWidget(hint)

            def refresh_hint(*_args):
                hint.setText(export_hint_text())

            format_combo.currentIndexChanged.connect(refresh_hint)
            if output_combo is not None:
                output_combo.currentIndexChanged.connect(refresh_hint)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
            try:
                buttons.button(QDialogButtonBox.Ok).setText("Export")
            except Exception:
                pass
            layout.addWidget(buttons)

            def browse_folder():
                start = folder_edit.text().strip() or self.last_export_folder or ""
                folder = QFileDialog.getExistingDirectory(dialog, title, start)
                if folder:
                    folder_edit.setText(folder)

            folder_button.clicked.connect(browse_folder)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)

            if dialog.exec() != QDialog.Accepted:
                return None
            folder = folder_edit.text().strip()
            if not folder:
                QMessageBox.information(self, "No export folder", "Choose an output folder before exporting.")
                return None
            self.last_export_folder = folder
            output_mode = output_combo.currentData() if output_combo is not None else "separate"
            selected_format = format_combo.currentData() or "auto"
            return {
                "folder": folder,
                "format": selected_format,
                "output_mode": output_mode or "separate",
                "audio_decoder": str(available_audio_decoder) if available_audio_decoder is not None else "",
                "audio_subsong": self._selected_audio_subsong() if audio_only and len(records) == 1 else 1,
            }

        def _export_render_only_parent_group(self, rec, out: str, export_format: str, uv_channel: int, ground_axis: str):
            """Export the same descendant assembly used by transform-only group preview.

            Descendant discovery and reference hydration remain on the Qt thread
            because they can trigger UBE's responsive external-bundle loader. The
            expensive GLB/OBJ construction then runs in a worker thread while the
            export notice continues to repaint.
            """
            if rec is None or self._ov_attached_mesh_record(rec) is not None:
                return None, 0

            parent_name = str(getattr(rec, "name", "group") or "group")
            self._update_export_work_notice(f"Scanning renderable children of {parent_name}…")
            items = self._ov_renderable_descendant_items(rec, limit=120, max_depth=10)
            if not items:
                return None, 0

            child_records = []
            matrices = {}
            seen = set()
            total = len(items)
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                child = item.get("record")
                matrix = item.get("matrix")
                if child is None:
                    continue
                key = (
                    str(getattr(child, "source_name", "") or ""),
                    str(getattr(child, "type_name", "") or ""),
                    getattr(child, "path_id", id(child)),
                )
                if key in seen:
                    continue
                seen.add(key)
                self._update_export_work_notice(
                    f"Resolving child materials and textures: {index}/{total} — "
                    f"{getattr(child, 'name', 'Object')}"
                )
                self._hydrate_object_external_render_assets(child)
                child_records.append(child)
                matrices[key] = matrix
                if index % 3 == 0:
                    self._pump_loading_events(25)

            if not child_records:
                return None, 0

            part_count = len(child_records)
            format_label = "GLB" if export_format == "glb" else "OBJ/MTL"

            def write_group(report):
                report(f"Writing {format_label} assembly: {part_count} rendered child object(s)…")
                if export_format == "glb":
                    result = export_multi_object_glb_records(
                        child_records,
                        out,
                        self.bundle_index,
                        self.asset_graph,
                        uv_channel=uv_channel,
                        name_override=parent_name,
                        record_matrices=matrices,
                        allow_single=True,
                    )
                else:
                    result = export_multi_object_record(
                        child_records,
                        out,
                        self.bundle_index,
                        self.asset_graph,
                        uv_channel=uv_channel,
                        name_override=parent_name,
                        record_matrices=matrices,
                        allow_single=True,
                    )
                report(f"Applying {ground_axis} export basis…")
                return apply_ground_axis_to_export_result(result, ground_axis)

            result = self._run_export_task_responsive(
                f"Writing {format_label} assembly for {parent_name}…",
                write_group,
            )
            return result, part_count

        def export_selected_asset(self):
            multi_records = self._selected_multi_preview_records()
            if len(multi_records) >= 2 and all(self._record_is_mesh_export(r) for r in multi_records):
                self.export_records(multi_records[:4], "Choose combined export folder", default_mesh_mode="combined")
                return
            if not self.selected_record:
                return
            if self.export_supported_for_record(self.selected_record):
                self.export_record(self.selected_record)
            else:
                self.export_inspector_reports(
                    [self.selected_record],
                    "Export inspector report",
                    report_label=getattr(self.selected_record, "name", "asset"),
                )

        def export_record(self, rec):
            if not self.export_supported_for_record(rec):
                QMessageBox.information(
                    self,
                    "Export not implemented",
                    f"Export is not yet implemented for {friendly_type_name(getattr(rec, 'type_name', 'asset'))} assets.",
                )
                return
            self.export_records([rec], "Choose export folder")

        def export_records(self, records: list, title: str, default_mesh_mode: str = "separate"):
            exportable = []
            seen = set()
            for rec in records:
                if not self.export_supported_for_record(rec):
                    continue
                key = (getattr(rec, "type_name", ""), getattr(rec, "source_name", ""), getattr(rec, "path_id", id(rec)))
                if key in seen:
                    continue
                seen.add(key)
                exportable.append(rec)
            if not exportable:
                QMessageBox.information(self, "Nothing to export", "No supported exportable assets were found here yet.")
                return
            options = self.choose_export_options(exportable, title, default_mesh_mode=default_mesh_mode)
            if not options:
                return
            out = options.get("folder", "")
            export_format = options.get("format", "auto")
            output_mode = options.get("output_mode", "separate")
            audio_decoder = options.get("audio_decoder", "")
            audio_subsong = max(1, int(options.get("audio_subsong", 1) or 1))
            if not out:
                return

            uv_channel = int(getattr(getattr(self, "preview_3d", None), "uv_channel", 0) or 0)
            ground_axis = self._current_ground_up_axis()

            # Multi-selection assembly export.  This is the same intent as the
            # multi-select preview: selected objects are written together without
            # per-part re-centering, so matching Unity origins stay aligned.
            if (
                output_mode == "combined"
                and len(exportable) >= 2
                and all(self._record_is_mesh_export(r) for r in exportable)
                and export_format in ("obj", "glb")
            ):
                label = "combined GLB" if export_format == "glb" else "combined OBJ"

                # v2.1: use the same hierarchy reconstruction as the multi-select
                # preview. Transform-only selections are expanded into their visible
                # renderer descendants and positioned relative to the nearest common
                # ancestor instead of being rejected as meshless objects.
                assembly = self._ov_multi_selection_render_items(exportable)
                assembled_items = list(assembly.get("items", []) or [])
                combined_exportable = []
                combined_matrices = {}
                combined_seen = set()
                for item in assembled_items:
                    child = item.get("record") if isinstance(item, dict) else None
                    if child is None:
                        continue
                    key = (
                        str(getattr(child, "source_name", "") or ""),
                        str(getattr(child, "type_name", "") or ""),
                        getattr(child, "path_id", id(child)),
                    )
                    if key in combined_seen:
                        continue
                    combined_seen.add(key)
                    combined_exportable.append(child)
                    combined_matrices[key] = item.get("matrix")

                if int(assembly.get("rendered_selection_count", 0) or 0) < 2 or len(combined_exportable) < 2:
                    combined_exportable = list(exportable)
                    combined_matrices = {}

                common_name = str(assembly.get("common_name", "Shared authored coordinates") or "Shared authored coordinates")
                self._show_export_work_notice(f"Preparing {label} from {len(combined_exportable)} reconstructed render instance(s)…")
                result = None
                export_error = None
                succeeded = False
                try:
                    def write_combined(report):
                        report(f"Writing {label} from {len(combined_exportable)} reconstructed render instance(s)…")
                        kwargs = {
                            "uv_channel": uv_channel,
                            "record_matrices": combined_matrices or None,
                            "name_override": "__plus__".join(str(getattr(r, "name", "Object")) for r in exportable[:2]),
                        }
                        if export_format == "glb":
                            raw = export_multi_object_glb_records(
                                combined_exportable,
                                out,
                                self.bundle_index,
                                self.asset_graph,
                                **kwargs,
                            )
                        else:
                            raw = export_multi_object_record(
                                combined_exportable,
                                out,
                                self.bundle_index,
                                self.asset_graph,
                                **kwargs,
                            )
                        report(f"Applying {ground_axis} export basis…")
                        return apply_ground_axis_to_export_result(raw, ground_axis)

                    result = self._run_export_task_responsive(
                        f"Writing {label}…",
                        write_combined,
                    )
                    succeeded = bool(result is not None and getattr(result, "ok", False))
                except Exception as exc:
                    export_error = exc
                finally:
                    self._hide_export_work_notice(success=succeeded)

                if export_error is not None:
                    QMessageBox.warning(
                        self,
                        "Combined export failed",
                        f"Could not export the selected objects as one assembly.\n\n{export_error}",
                    )
                    return

                if result.ok and result.path:
                    QMessageBox.information(
                        self,
                        "Exported combined selection",
                        f"Exported {label} from {len(exportable)} selected object(s) to:\n{result.path}\n\n"
                        f"The assembly preserves shared Unity coordinates; parts are not individually re-centred.\n"
                        f"Ground/up axis applied: {ground_axis}",
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Combined export failed",
                        f"Could not export the selected objects as one assembly.\n\n{getattr(result, 'message', '')}",
                    )
                return

            exported = []
            failed = []
            self._show_export_work_notice(f"Preparing {len(exportable)} asset(s) for export…")
            try:
                for rec_index, rec in enumerate(exportable, start=1):
                    rec_name = str(getattr(rec, "name", "asset") or "asset")
                    rec_type = str(getattr(rec, "type_name", "") or "")
                    self._update_export_work_notice(
                        f"Exporting {rec_index}/{len(exportable)} — {rec_name}"
                    )
                    try:
                        if rec_type == "Texture2D":
                            def write_texture(report, r=rec, name=rec_name):
                                report(f"Decoding and writing texture — {name}…")
                                return export_texture_record(r, out)

                            dst = self._run_export_task_responsive(
                                f"Writing texture PNG — {rec_name}…",
                                write_texture,
                            )
                            if dst:
                                exported.append(dst)
                            else:
                                failed.append(f"{rec_name}  [Texture PNG export failed]")

                        elif rec_type == "Cubemap":
                            def write_cubemap(report, r=rec, name=rec_name):
                                report(f"Decoding and writing cubemap — {name}…")
                                return export_texture_record(r, out)

                            dst = self._run_export_task_responsive(
                                f"Writing cubemap preview — {rec_name}…",
                                write_cubemap,
                            )
                            if dst:
                                exported.append(dst)
                            else:
                                failed.append(f"{rec_name}  [Cubemap PNG/contact-sheet export failed or not available from decoder]")

                        elif rec_type == "Texture2DArray":
                            def write_texture_array(report, r=rec, name=rec_name):
                                report(f"Decoding texture-array slices — {name}…")
                                return export_texture_array_record(r, out)

                            dsts = self._run_export_task_responsive(
                                f"Writing texture-array slices — {rec_name}…",
                                write_texture_array,
                            )
                            if dsts:
                                exported.extend(dsts)
                            else:
                                failed.append(f"{rec_name}  [Texture2DArray slice export not available from decoder]")

                        elif rec_type == "Sprite":
                            self._update_export_work_notice(f"Resolving sprite texture — {rec_name}…")
                            self._hydrate_sprite_external_assets(rec)

                            def write_sprite(report, r=rec, name=rec_name):
                                report(f"Cropping and writing sprite — {name}…")
                                return export_sprite_record(r, out, self.bundle_index)

                            dst = self._run_export_task_responsive(
                                f"Writing sprite PNG — {rec_name}…",
                                write_sprite,
                            )
                            if dst:
                                exported.append(dst)
                            else:
                                failed.append(f"{rec_name}  [Sprite PNG export failed]")

                        elif rec_type == "SpriteRenderer":
                            self._update_export_work_notice(f"Resolving SpriteRenderer texture — {rec_name}…")
                            self._hydrate_sprite_external_assets(rec)

                            def write_sprite_renderer(report, r=rec, name=rec_name):
                                report(f"Cropping and writing SpriteRenderer sprite — {name}…")
                                return export_sprite_renderer_record(r, out, self.bundle_index)

                            dst = self._run_export_task_responsive(
                                f"Writing SpriteRenderer PNG — {rec_name}…",
                                write_sprite_renderer,
                            )
                            if dst:
                                exported.append(dst)
                            else:
                                failed.append(f"{rec_name}  [SpriteRenderer sprite export failed]")

                        elif rec_type == "AudioClip":
                            if export_format == "audio_wav":
                                # A single selected AudioClip follows the sample/subsong currently
                                # chosen in the preview. Batch exports use sample 1 per clip.
                                selected_subsong = audio_subsong if len(exportable) == 1 else 1

                                def write_audio(report, r=rec, name=rec_name, subsong=selected_subsong):
                                    report(f"Decoding audio to WAV — {name} (sample {subsong})…")
                                    return export_audio_wav_record(
                                        r,
                                        out,
                                        decoder_path=audio_decoder or self.audio_decoder_path or self._saved_vgmstream_path(),
                                        subsong=subsong,
                                    )

                                task_text = f"Converting audio to WAV — {rec_name}…"
                            else:
                                def write_audio(report, r=rec, name=rec_name):
                                    report(f"Extracting original audio data — {name}…")
                                    return export_audio_record(r, out)

                                task_text = f"Writing original audio — {rec_name}…"

                            result = self._run_export_task_responsive(task_text, write_audio)
                            if result.ok:
                                exported.extend(result.paths)
                            else:
                                failed.append(f"{rec_name}  [Audio export failed: {result.message}]")

                        elif rec_type == "Mesh":
                            def write_mesh(report, r=rec, name=rec_name):
                                report(f"Decoding mesh geometry — {name}…")
                                if export_format == "glb":
                                    raw = export_mesh_glb_record(
                                        r,
                                        out,
                                        self.bundle_index,
                                        self.asset_graph,
                                        uv_channel=uv_channel,
                                    )
                                else:
                                    raw = export_mesh_record(
                                        r,
                                        out,
                                        self.bundle_index,
                                        self.asset_graph,
                                        uv_channel=uv_channel,
                                    )
                                report(f"Applying {ground_axis} export basis…")
                                return apply_ground_axis_to_export_result(raw, ground_axis)

                            result = self._run_export_task_responsive(
                                f"Writing {'GLB' if export_format == 'glb' else 'OBJ/MTL'} mesh — {rec_name}…",
                                write_mesh,
                            )
                            fail_label = "Mesh GLB skipped" if export_format == "glb" else "Mesh OBJ skipped"
                            if result.ok and result.path:
                                exported.append(result.path)
                            else:
                                failed.append(f"{rec_name}  [{fail_label}: {result.message}]")

                        elif rec_type in self.object_view_types():
                            self._update_export_work_notice(f"Resolving render chain — {rec_name}…")
                            self._hydrate_object_external_render_assets(rec)

                            # A transform-only parent can preview perfectly because
                            # UBE assembles its renderable descendants, yet it has no
                            # direct MeshFilter for the single-object exporter.
                            result, group_part_count = self._export_render_only_parent_group(
                                rec,
                                out,
                                export_format,
                                uv_channel,
                                ground_axis,
                            )
                            if result is not None:
                                fail_label = f"Group {'GLB' if export_format == 'glb' else 'OBJ'} skipped"
                            else:
                                def write_object(report, r=rec, name=rec_name):
                                    report(f"Decoding object geometry and materials — {name}…")
                                    if export_format == "glb":
                                        raw = export_object_glb_record(
                                            r,
                                            out,
                                            self.bundle_index,
                                            self.asset_graph,
                                            uv_channel=uv_channel,
                                        )
                                    else:
                                        raw = export_object_record(
                                            r,
                                            out,
                                            self.bundle_index,
                                            self.asset_graph,
                                            uv_channel=uv_channel,
                                        )
                                    report(f"Applying {ground_axis} export basis…")
                                    return apply_ground_axis_to_export_result(raw, ground_axis)

                                result = self._run_export_task_responsive(
                                    f"Writing {'GLB' if export_format == 'glb' else 'OBJ/MTL'} object — {rec_name}…",
                                    write_object,
                                )
                                fail_label = "Object GLB skipped" if export_format == "glb" else "Object mesh export skipped"

                            if result.ok and result.path:
                                exported.append(result.path)
                            else:
                                failed.append(f"{rec_name}  [{fail_label}: {result.message}]")

                    except Exception as exc:
                        failed.append(f"{rec_name}  [Export error: {exc}]")
            finally:
                self._hide_export_work_notice(success=bool(exported))

            if exported and not failed:
                QMessageBox.information(
                    self,
                    "Exported",
                    f"Exported {len(exported)} asset(s) to:\n{out}\n\n"
                    f"{self._export_completion_hint(exportable)}",
                )
            elif exported and failed:
                sample = "\n".join(f" • {name}" for name in failed[:20])
                more = f"\n... and {len(failed) - 20} more" if len(failed) > 20 else ""
                QMessageBox.warning(
                    self,
                    "Export partly completed",
                    f"Exported {len(exported)} asset(s) to:\n{out}\n\n"
                    f"{self._export_completion_hint(exportable)}\n\n"
                    f"Skipped {len(failed)} unsupported/failed asset(s):\n{sample}{more}",
                )
            else:
                sample = "\n".join(f" • {name}" for name in failed[:20]) if failed else ""
                QMessageBox.warning(self, "Export failed", f"Could not export the selected asset(s).\n\n{sample}")

    app = QApplication([])
    w = MainWindow()
    app.aboutToQuit.connect(w._shutdown_audio_preview)
    w.show()
    try:
        app.exec()
    finally:
        w._shutdown_audio_preview()
