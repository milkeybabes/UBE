#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
UBE Companion Utilities Launcher v1.0
=====================================

A lean graphical front end for the standalone UBE companion utilities.

The launcher does not duplicate or replace the utilities. It builds the normal
command line, starts the selected script as a child process, and displays the
same console output inside the window.

Run:
    python ube_utilities_gui.py

The launcher uses only Python's standard library. Individual utilities retain
their own requirements, such as UnityPy or Blender.
"""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "UBE Companion Utilities"
APP_VERSION = "1.0"
BASE_DIR = Path(__file__).resolve().parent

BG = "#1d1f22"
PANEL = "#25282c"
PANEL_ALT = "#2d3035"
BORDER = "#3b3f45"
TEXT = "#f0f0f0"
MUTED = "#aeb4bc"
ACCENT = "#4d9de0"
ACCENT_HOVER = "#62adeb"
SUCCESS = "#62c370"
WARNING = "#e6b85c"
ERROR = "#e66b6b"
ENTRY_BG = "#17191c"
SELECT_BG = "#355f83"


def tool_registry() -> "OrderedDict[str, dict[str, Any]]":
    """Single source of truth for the launcher forms and command arguments."""
    return OrderedDict(
        [
            (
                "huntunity",
                {
                    "title": "Extract Android Bundles",
                    "script": "huntunity.py",
                    "description": (
                        "Scan folders of Android APK and OBB archives, find genuine "
                        "UnityFS files, and extract them as normal .bundle files for UBE."
                    ),
                    "dependency": "standard",
                    "output_keys": ["destination"],
                    "fields": [
                        {
                            "key": "source",
                            "label": "Source APK / OBB folder",
                            "kind": "folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                            "help": "Folder containing .apk or .obb files. Subfolders are scanned automatically.",
                        },
                        {
                            "key": "destination",
                            "label": "Destination folder",
                            "kind": "folder",
                            "positional": True,
                            "required": True,
                            "create_ok": True,
                            "help": "Extracted bundle files are written beneath this folder.",
                        },
                        {
                            "key": "primary_only",
                            "label": "Extract primary data.unity3d only",
                            "kind": "checkbox",
                            "flag": "--primary-only",
                            "default": False,
                        },
                        {
                            "key": "flat",
                            "label": "Place primary bundles directly in destination",
                            "kind": "checkbox",
                            "flag": "--flat",
                            "default": False,
                        },
                        {
                            "key": "overwrite",
                            "label": "Overwrite existing extracted files",
                            "kind": "checkbox",
                            "flag": "--overwrite",
                            "default": False,
                        },
                        {
                            "key": "verbose",
                            "label": "Show detailed archive decisions",
                            "kind": "checkbox",
                            "flag": "--verbose",
                            "default": False,
                        },
                        {
                            "key": "include_non_unity_primary",
                            "label": "Extract expected primary file even without UnityFS signature",
                            "kind": "checkbox",
                            "flag": "--include-non-unity-primary",
                            "default": False,
                            "advanced": True,
                            "help": "Use only when you deliberately need assets/bin/Data/data.unity3d regardless of its header.",
                        },
                    ],
                },
            ),
            (
                "header_scan",
                {
                    "title": "Unity Header Scanner",
                    "script": "unity_bundle_header_scan.py",
                    "description": (
                        "Quickly identify Unity container signatures, engine versions, "
                        "header details, file sizes, and optionally SHA256 hashes."
                    ),
                    "dependency": "standard",
                    "output_keys": ["out_dir"],
                    "fields": [
                        {
                            "key": "path",
                            "label": "Bundle file or folder",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                        },
                        {
                            "key": "out_dir",
                            "label": "Report output folder",
                            "kind": "folder",
                            "flag": "--out-dir",
                            "create_ok": True,
                            "help": "Optional. Without this, reports are written beside the launcher scripts.",
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "flag": "--recursive",
                            "default": False,
                        },
                        {
                            "key": "all_files",
                            "label": "Scan every file regardless of extension",
                            "kind": "checkbox",
                            "flag": "--all",
                            "default": False,
                        },
                        {
                            "key": "sha256",
                            "label": "Calculate SHA256 hashes",
                            "kind": "checkbox",
                            "flag": "--sha256",
                            "default": False,
                            "help": "Useful for proving files are identical, but slower on large folders.",
                        },
                        {
                            "key": "extensions",
                            "label": "Custom extensions",
                            "kind": "tokens",
                            "flag": "--extensions",
                            "advanced": True,
                            "placeholder": ".bundle .unity3d .assets",
                            "help": "Leave blank to use the scanner defaults.",
                        },
                    ],
                },
            ),
            (
                "bundle_audit",
                {
                    "title": "Unity Bundle Audit",
                    "script": "unity_bundle_audit.py",
                    "description": (
                        "Produce a deeper UnityFS audit with hashes, compression, internal "
                        "nodes and quick texture/shader string hits. It can also compare "
                        "matching bundle names from different releases."
                    ),
                    "dependency": "lz4_optional",
                    "output_keys": ["csv"],
                    "fields": [
                        {
                            "key": "inputs",
                            "label": "Bundle files and/or folders",
                            "kind": "path_list",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                            "help": "Add one or more files or folders. Folder scans are recursive.",
                        },
                        {
                            "key": "csv",
                            "label": "CSV report",
                            "kind": "save_file",
                            "flag": "--csv",
                            "filetypes": [("CSV report", "*.csv"), ("All files", "*.*")],
                            "default_name": "unity_bundle_report.csv",
                            "help": "Optional. The utility otherwise writes unity_bundle_report.csv.",
                        },
                        {
                            "key": "compare",
                            "label": "Compare matching filenames",
                            "kind": "checkbox",
                            "flag": "--compare",
                            "default": False,
                        },
                    ],
                },
            ),
            (
                "texture_extract",
                {
                    "title": "Batch Texture Extractor",
                    "script": "unity_bundle_texture_extractor.py",
                    "description": (
                        "Extract Texture2D images from many Unity bundles as clean PNG files. "
                        "Ideal for course logos, menu art and other collections where each "
                        "small bundle contains one useful image."
                    ),
                    "dependency": "unitypy",
                    "output_keys": ["out"],
                    "fields": [
                        {
                            "key": "inputs",
                            "label": "Bundle file or folder",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                        },
                        {
                            "key": "out",
                            "label": "Output folder",
                            "kind": "folder",
                            "flag": "--out",
                            "create_ok": True,
                            "help": "Optional. Default: Extracted_Textures beside the input.",
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "default": True,
                            "false_flag": "--no-recursive",
                        },
                        {
                            "key": "same_folder",
                            "label": "Write PNG files beside each source bundle",
                            "kind": "checkbox",
                            "flag": "--same-folder",
                            "default": False,
                        },
                        {
                            "key": "overwrite",
                            "label": "Overwrite existing PNG files",
                            "kind": "checkbox",
                            "flag": "--overwrite",
                            "default": False,
                        },
                        {
                            "key": "include_sprites",
                            "label": "Also export Sprite images",
                            "kind": "checkbox",
                            "flag": "--include-sprites",
                            "default": False,
                            "help": "May duplicate Texture2D output when the Sprite references the complete texture.",
                        },
                        {
                            "key": "dry_run",
                            "label": "Dry run — list files without writing PNGs",
                            "kind": "checkbox",
                            "flag": "--dry-run",
                            "default": False,
                        },
                        {
                            "key": "all_files",
                            "label": "Attempt files without .bundle or .unity3d extensions",
                            "kind": "checkbox",
                            "flag": "--all-files",
                            "default": False,
                            "advanced": True,
                        },
                        {
                            "key": "report",
                            "label": "Custom TSV report",
                            "kind": "save_file",
                            "flag": "--report",
                            "advanced": True,
                            "filetypes": [("TSV report", "*.tsv"), ("All files", "*.*")],
                            "default_name": "unity_texture_extract_report.tsv",
                        },
                    ],
                },
            ),
            (
                "lookup",
                {
                    "title": "UBE Lookup Search",
                    "script": "ube_lookup_search.py",
                    "description": (
                        "Rediscover which bundle or object a screenshot, PathID, old note or "
                        "asset name came from by searching UBE JSON, text, TSV and SQLite data."
                    ),
                    "dependency": "standard",
                    "output_keys": ["out"],
                    "fields": [
                        {
                            "key": "root",
                            "label": "UBE cache, project folder or lookup file",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                        },
                        {
                            "key": "query",
                            "label": "Search terms",
                            "kind": "multitext",
                            "positional": True,
                            "required": True,
                            "height": 3,
                            "help": "Enter one term per line, or several terms separated by spaces. Quoted phrases stay together.",
                        },
                        {
                            "key": "mode",
                            "label": "Match mode",
                            "kind": "combo",
                            "flag": "--mode",
                            "values": ["any", "all"],
                            "default": "any",
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "default": True,
                            "false_flag": "--no-recursive",
                        },
                        {
                            "key": "max_per_file",
                            "label": "Maximum matches per file",
                            "kind": "integer",
                            "flag": "--max-per-file",
                            "default": 50,
                            "minimum": 1,
                            "maximum": 100000,
                            "advanced": True,
                        },
                        {
                            "key": "out",
                            "label": "TSV output file",
                            "kind": "save_file",
                            "flag": "--out",
                            "advanced": True,
                            "filetypes": [("TSV report", "*.tsv"), ("All files", "*.*")],
                            "default_name": "ube_lookup_search_results.tsv",
                        },
                    ],
                },
            ),
            (
                "validator",
                {
                    "title": "UBE Export Validator",
                    "script": "ube_export_validator.py",
                    "description": (
                        "Check UBE OBJ/MTL/texture exports and GLB files for missing files, "
                        "invalid indices, malformed chunks, and other structural problems."
                    ),
                    "dependency": "standard",
                    "output_keys": ["json"],
                    "fields": [
                        {
                            "key": "path",
                            "label": "OBJ, GLB or export folder",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "flag": "--recursive",
                            "default": False,
                        },
                        {
                            "key": "json",
                            "label": "JSON report",
                            "kind": "save_file",
                            "flag": "--json",
                            "filetypes": [("JSON report", "*.json"), ("All files", "*.*")],
                            "default_name": "ube_export_validation.json",
                            "help": "Optional machine-readable report.",
                        },
                    ],
                },
            ),
            (
                "glb_corrector",
                {
                    "title": "GLB Presentation Corrector",
                    "script": "glb_presentation_corrector.py",
                    "description": (
                        "Re-centre, ground and optionally rotate GLB exports for convenient "
                        "viewing, rendering or video while preserving geometry, skinning, "
                        "materials and animation tracks."
                    ),
                    "dependency": "standard",
                    "output_keys": ["output_dir"],
                    "fields": [
                        {
                            "key": "input",
                            "label": "GLB file or folder",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                            "filetypes": [("GLB files", "*.glb"), ("All files", "*.*")],
                        },
                        {
                            "key": "output_dir",
                            "label": "Output folder",
                            "kind": "folder",
                            "flag": "--output-dir",
                            "create_ok": True,
                            "help": "Optional. Without this, corrected files are written beside their source GLBs.",
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "flag": "--recursive",
                            "default": False,
                        },
                        {
                            "key": "center",
                            "label": "Centre model",
                            "kind": "combo",
                            "flag": "--center",
                            "values": ["xz", "xyz", "none"],
                            "default": "xz",
                        },
                        {
                            "key": "ground",
                            "label": "Place lowest point on Y=0",
                            "kind": "checkbox",
                            "default": True,
                            "false_flag": "--no-ground",
                        },
                        {
                            "key": "rotate_y",
                            "label": "Y rotation in degrees",
                            "kind": "float",
                            "flag": "--rotate-y",
                            "default": 0.0,
                        },
                        {
                            "key": "bounds",
                            "label": "Bounds source",
                            "kind": "combo",
                            "flag": "--bounds",
                            "values": ["rest", "first", "animation"],
                            "default": "first",
                        },
                        {
                            "key": "dry_run",
                            "label": "Dry run — calculate without writing",
                            "kind": "checkbox",
                            "flag": "--dry-run",
                            "default": False,
                        },
                        {
                            "key": "suffix",
                            "label": "Output filename suffix",
                            "kind": "text",
                            "flag": "--suffix",
                            "default": "_presented",
                            "advanced": True,
                        },
                        {
                            "key": "animation_index",
                            "label": "Animation index",
                            "kind": "integer",
                            "flag": "--animation-index",
                            "default": 0,
                            "minimum": 0,
                            "advanced": True,
                        },
                        {
                            "key": "samples",
                            "label": "Animation bound samples",
                            "kind": "integer",
                            "flag": "--samples",
                            "default": 120,
                            "minimum": 2,
                            "advanced": True,
                        },
                        {
                            "key": "max_skin_vertices",
                            "label": "Maximum sampled skin vertices",
                            "kind": "integer",
                            "flag": "--max-skin-vertices",
                            "default": 12000,
                            "minimum": 0,
                            "advanced": True,
                            "help": "Use 0 to evaluate every vertex at every sampled pose.",
                        },
                    ],
                },
            ),
            (
                "glb_thumbnails",
                {
                    "title": "GLB Thumbnail Renderer",
                    "script": "glb_thumbnail_batch.py",
                    "description": (
                        "Use Blender in background mode to render quick PNG or JPG previews "
                        "for one GLB or a complete folder. Lighting automatically scales to "
                        "tiny and large models."
                    ),
                    "dependency": "blender",
                    "output_keys": ["out"],
                    "fields": [
                        {
                            "key": "input",
                            "label": "GLB file or folder",
                            "kind": "file_or_folder",
                            "positional": True,
                            "required": True,
                            "must_exist": True,
                            "filetypes": [("GLB files", "*.glb"), ("All files", "*.*")],
                        },
                        {
                            "key": "out",
                            "label": "Thumbnail output folder",
                            "kind": "folder",
                            "flag": "--out",
                            "create_ok": True,
                            "help": "Optional. Default: <input>_thumbnails.",
                        },
                        {
                            "key": "recursive",
                            "label": "Scan subfolders",
                            "kind": "checkbox",
                            "flag": "--recursive",
                            "default": False,
                        },
                        {
                            "key": "view",
                            "label": "Camera view",
                            "kind": "combo",
                            "flag": "--view",
                            "values": ["iso", "front", "back", "left", "right", "top"],
                            "default": "iso",
                        },
                        {
                            "key": "size",
                            "label": "Thumbnail size",
                            "kind": "integer",
                            "flag": "--size",
                            "default": 768,
                            "minimum": 64,
                            "maximum": 8192,
                        },
                        {
                            "key": "format",
                            "label": "Image format",
                            "kind": "combo",
                            "flag": "--format",
                            "values": ["png", "jpg"],
                            "default": "png",
                        },
                        {
                            "key": "transparent",
                            "label": "Transparent PNG background",
                            "kind": "checkbox",
                            "flag": "--transparent",
                            "default": False,
                        },
                        {
                            "key": "overwrite",
                            "label": "Overwrite existing thumbnails",
                            "kind": "checkbox",
                            "flag": "--overwrite",
                            "default": False,
                        },
                        {
                            "key": "light_strength",
                            "label": "Lighting strength",
                            "kind": "float",
                            "flag": "--light-strength",
                            "default": 1.0,
                            "minimum": 0.0,
                        },
                        {
                            "key": "dry_run",
                            "label": "Dry run — show planned Blender command",
                            "kind": "checkbox",
                            "flag": "--dry-run",
                            "default": False,
                        },
                        {
                            "key": "blender",
                            "label": "Blender executable",
                            "kind": "file",
                            "flag": "--blender",
                            "advanced": True,
                            "filetypes": [("Blender", "blender.exe"), ("Executable", "*.exe"), ("All files", "*.*")],
                            "help": "Leave blank to auto-detect Blender.",
                        },
                        {
                            "key": "same_folder",
                            "label": "Write thumbnails beside each GLB",
                            "kind": "checkbox",
                            "flag": "--same-folder",
                            "default": False,
                            "advanced": True,
                        },
                        {
                            "key": "jpg_quality",
                            "label": "JPG quality",
                            "kind": "integer",
                            "flag": "--jpg-quality",
                            "default": 92,
                            "minimum": 1,
                            "maximum": 100,
                            "advanced": True,
                        },
                        {
                            "key": "suffix",
                            "label": "Thumbnail filename suffix",
                            "kind": "text",
                            "flag": "--suffix",
                            "default": "__preview",
                            "advanced": True,
                        },
                        {
                            "key": "material_mode",
                            "label": "Fallback material mode",
                            "kind": "combo",
                            "flag": "--material-mode",
                            "values": ["TEXTURED", "MATERIAL", "SOLID"],
                            "default": "TEXTURED",
                            "advanced": True,
                        },
                    ],
                },
            ),
        ]
    )


def settings_file() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / ".config"
    return root / "UBE_Companion_Utilities" / "settings.json"


def load_settings() -> dict[str, Any]:
    path = settings_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict[str, Any]) -> None:
    path = settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def find_blender(explicit: str = "") -> str | None:
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return str(candidate)
        found = shutil.which(explicit)
        if found:
            return found

    found = shutil.which("blender")
    if found:
        return found

    candidates = [
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def quote_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def split_tokens(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []

    lines: list[str] = []
    for raw_line in value.replace(";", "\n").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            lines.extend(shlex.split(raw_line, posix=(os.name != "nt")))
        except ValueError:
            lines.append(raw_line)
    return lines


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.tools = tool_registry()
        self.settings_data = load_settings()
        self.current_tool_key: str | None = None
        self.controls: dict[str, dict[str, Any]] = {}
        self.process: subprocess.Popen[str] | None = None
        self.output_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self.advanced_visible = tk.BooleanVar(value=False)
        self._preview_after: str | None = None

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.minsize(980, 700)
        geometry = self.settings_data.get("geometry", "1180x790")
        self.geometry(geometry)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.setup_style()
        self.build_layout()
        self.populate_tool_list()

        requested = self.settings_data.get("last_tool")
        keys = list(self.tools)
        initial_index = keys.index(requested) if requested in self.tools else 0
        self.tool_list.selection_set(initial_index)
        self.tool_list.activate(initial_index)
        self.on_tool_selected()

        self.after(80, self.poll_output_queue)

    # ---------- UI construction ----------

    def setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        default_font = ("Segoe UI", 10)
        self.option_add("*Font", default_font)

        style.configure(".", background=BG, foreground=TEXT, fieldbackground=ENTRY_BG)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Alt.TFrame", background=PANEL_ALT)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 18))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 17))
        style.configure("SubHeader.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Field.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("Help.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=BG, foreground=MUTED)
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=TEXT, insertcolor=TEXT, bordercolor=BORDER)
        style.configure("TCombobox", fieldbackground=ENTRY_BG, foreground=TEXT, arrowcolor=TEXT)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", ENTRY_BG)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", ENTRY_BG)],
            selectforeground=[("readonly", TEXT)],
        )
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", PANEL)], foreground=[("active", TEXT)])
        style.configure("TButton", background=PANEL_ALT, foreground=TEXT, bordercolor=BORDER, padding=(10, 6))
        style.map("TButton", background=[("active", "#3a3e44"), ("disabled", PANEL)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT, padding=(13, 7))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#466075")])
        style.configure("Danger.TButton", background="#704040", foreground="#ffffff", padding=(10, 6))
        style.map("Danger.TButton", background=[("active", "#8a4b4b")])
        style.configure("TLabelframe", background=PANEL, foreground=TEXT, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=PANEL, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("Horizontal.TSeparator", background=BORDER)

    def build_layout(self) -> None:
        header = ttk.Frame(self, padding=(18, 14, 18, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Simple graphical access to the standalone UBE utility scripts",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(
            header,
            text=f"v{APP_VERSION}",
            style="SubHeader.TLabel",
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        main = ttk.Frame(self, padding=(14, 4, 14, 10))
        main.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=3)
        main.rowconfigure(1, weight=2)
        main.columnconfigure(0, weight=1)

        upper = ttk.Frame(main)
        upper.grid(row=0, column=0, sticky="nsew")
        upper.rowconfigure(0, weight=1)
        upper.columnconfigure(1, weight=1)

        left = ttk.Frame(upper, style="Panel.TFrame", padding=(10, 10))
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left.rowconfigure(1, weight=1)

        ttk.Label(left, text="Utilities", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        self.tool_list = tk.Listbox(
            left,
            width=28,
            height=15,
            bg=ENTRY_BG,
            fg=TEXT,
            selectbackground=SELECT_BG,
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            borderwidth=0,
            exportselection=False,
            font=("Segoe UI", 10),
        )
        self.tool_list.grid(row=1, column=0, sticky="ns")
        self.tool_list.bind("<<ListboxSelect>>", lambda _event: self.on_tool_selected())

        self.right_panel = ttk.Frame(upper, style="Panel.TFrame", padding=(16, 14))
        self.right_panel.grid(row=0, column=1, sticky="nsew")
        self.right_panel.columnconfigure(0, weight=1)
        self.right_panel.rowconfigure(4, weight=1)

        self.tool_title = ttk.Label(self.right_panel, text="", style="Title.TLabel")
        self.tool_title.grid(row=0, column=0, sticky="w")

        dep_row = ttk.Frame(self.right_panel, style="Panel.TFrame")
        dep_row.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        dep_row.columnconfigure(0, weight=1)
        self.tool_description = ttk.Label(
            dep_row,
            text="",
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        )
        self.tool_description.grid(row=0, column=0, sticky="w")
        self.dependency_label = tk.Label(
            dep_row,
            text="",
            bg=PANEL_ALT,
            fg=TEXT,
            padx=9,
            pady=4,
            font=("Segoe UI Semibold", 9),
        )
        self.dependency_label.grid(row=0, column=1, sticky="ne", padx=(12, 0))

        ttk.Separator(self.right_panel).grid(row=2, column=0, sticky="ew", pady=(12, 10))

        controls_header = ttk.Frame(self.right_panel, style="Panel.TFrame")
        controls_header.grid(row=3, column=0, sticky="ew")
        controls_header.columnconfigure(0, weight=1)
        ttk.Label(controls_header, text="Settings", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.advanced_check = ttk.Checkbutton(
            controls_header,
            text="Show advanced options",
            variable=self.advanced_visible,
            command=self.toggle_advanced,
        )
        self.advanced_check.grid(row=0, column=1, sticky="e")

        form_outer = ttk.Frame(self.right_panel, style="Panel.TFrame")
        form_outer.grid(row=4, column=0, sticky="nsew", pady=(7, 8))
        form_outer.rowconfigure(0, weight=1)
        form_outer.columnconfigure(0, weight=1)

        self.form_canvas = tk.Canvas(
            form_outer,
            bg=PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        self.form_scroll = ttk.Scrollbar(form_outer, orient="vertical", command=self.form_canvas.yview)
        self.form_canvas.configure(yscrollcommand=self.form_scroll.set)
        self.form_canvas.grid(row=0, column=0, sticky="nsew")
        self.form_scroll.grid(row=0, column=1, sticky="ns")

        self.form_container = ttk.Frame(self.form_canvas, style="Panel.TFrame")
        self.form_window = self.form_canvas.create_window((0, 0), window=self.form_container, anchor="nw")
        self.form_container.bind(
            "<Configure>",
            lambda _event: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")),
        )
        self.form_canvas.bind(
            "<Configure>",
            lambda event: self.form_canvas.itemconfigure(self.form_window, width=event.width),
        )
        self.form_canvas.bind_all("<MouseWheel>", self.on_mousewheel, add="+")

        command_frame = ttk.LabelFrame(self.right_panel, text="Command preview", padding=(8, 7))
        command_frame.grid(row=5, column=0, sticky="ew", pady=(3, 7))
        command_frame.columnconfigure(0, weight=1)
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(command_frame, textvariable=self.command_var, state="readonly")
        self.command_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(command_frame, text="Copy", command=self.copy_command).grid(row=0, column=1, padx=(7, 0))

        action_row = ttk.Frame(self.right_panel, style="Panel.TFrame")
        action_row.grid(row=6, column=0, sticky="ew")
        action_row.columnconfigure(2, weight=1)
        self.run_button = ttk.Button(action_row, text="Run Utility", style="Accent.TButton", command=self.run_tool)
        self.run_button.grid(row=0, column=0)
        self.cancel_button = ttk.Button(action_row, text="Cancel", style="Danger.TButton", command=self.cancel_tool, state="disabled")
        self.cancel_button.grid(row=0, column=1, padx=(7, 0))
        self.open_output_button = ttk.Button(action_row, text="Open Output Folder", command=self.open_output_folder)
        self.open_output_button.grid(row=0, column=3, padx=(7, 0))

        log_frame = ttk.LabelFrame(main, text="Output", padding=(8, 7))
        log_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            bg="#111315",
            fg="#dce2e8",
            insertbackground=TEXT,
            selectbackground=SELECT_BG,
            relief="flat",
            borderwidth=0,
            wrap="word",
            font=("Consolas", 9),
            padx=8,
            pady=7,
            state="disabled",
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.tag_configure("normal", foreground="#dce2e8")
        self.log_text.tag_configure("muted", foreground=MUTED)
        self.log_text.tag_configure("success", foreground=SUCCESS)
        self.log_text.tag_configure("warning", foreground=WARNING)
        self.log_text.tag_configure("error", foreground=ERROR)
        self.log_text.tag_configure("command", foreground="#8dc8f2")

        log_buttons = ttk.Frame(log_frame)
        log_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        log_buttons.columnconfigure(0, weight=1)
        ttk.Button(log_buttons, text="Copy Log", command=self.copy_log).grid(row=0, column=1)
        ttk.Button(log_buttons, text="Clear", command=self.clear_log).grid(row=0, column=2, padx=(7, 0))

        status = ttk.Frame(self, padding=(14, 0, 14, 8))
        status.grid(row=2, column=0, sticky="ew")
        status.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")

    def populate_tool_list(self) -> None:
        for tool in self.tools.values():
            self.tool_list.insert("end", tool["title"])

    def on_mousewheel(self, event: tk.Event) -> None:
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if widget is not None and str(widget).startswith(str(self.form_canvas)):
                self.form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # ---------- Form handling ----------

    def on_tool_selected(self) -> None:
        selection = self.tool_list.curselection()
        if not selection:
            return

        if self.process is not None:
            messagebox.showinfo(APP_NAME, "Wait for the current utility to finish, or cancel it first.")
            if self.current_tool_key is not None:
                old_index = list(self.tools).index(self.current_tool_key)
                self.tool_list.selection_clear(0, "end")
                self.tool_list.selection_set(old_index)
            return

        self.capture_current_values()
        key = list(self.tools)[selection[0]]
        self.current_tool_key = key
        tool = self.tools[key]

        self.tool_title.configure(text=tool["title"])
        self.tool_description.configure(text=tool["description"])
        self.advanced_visible.set(False)
        self.build_form(tool)
        self.update_dependency_status()
        self.schedule_preview_update()
        self.status_var.set("Ready")

    def clear_form(self) -> None:
        for child in self.form_container.winfo_children():
            child.destroy()
        self.controls.clear()

    def build_form(self, tool: dict[str, Any]) -> None:
        self.clear_form()
        saved_values = self.settings_data.get("tools", {}).get(self.current_tool_key or "", {})

        self.normal_fields = ttk.Frame(self.form_container, style="Panel.TFrame")
        self.normal_fields.pack(fill="x")
        self.advanced_fields = ttk.Frame(self.form_container, style="Panel.TFrame")

        for field in tool["fields"]:
            parent = self.advanced_fields if field.get("advanced") else self.normal_fields
            self.create_control(parent, field, saved_values.get(field["key"], field.get("default", "")))

        self.toggle_advanced()
        self.form_canvas.yview_moveto(0)

    def create_control(self, parent: ttk.Frame, field: dict[str, Any], initial: Any) -> None:
        block = ttk.Frame(parent, style="Panel.TFrame")
        block.pack(fill="x", pady=(0, 9))

        label_text = field["label"] + (" *" if field.get("required") else "")
        ttk.Label(block, text=label_text, style="Field.TLabel").pack(anchor="w")

        kind = field["kind"]
        control: dict[str, Any] = {"field": field, "kind": kind}

        if kind in {"text", "integer", "float", "tokens"}:
            var = tk.StringVar(value="" if initial is None else str(initial))
            entry = ttk.Entry(block, textvariable=var)
            entry.pack(fill="x", pady=(3, 0))
            var.trace_add("write", lambda *_args: self.schedule_preview_update())
            control.update(var=var, widget=entry)

        elif kind == "combo":
            var = tk.StringVar(value=str(initial or field.get("default", "")))
            combo = ttk.Combobox(block, textvariable=var, values=field["values"], state="readonly")
            combo.pack(fill="x", pady=(3, 0))
            combo.bind("<<ComboboxSelected>>", lambda _event: self.schedule_preview_update())
            control.update(var=var, widget=combo)

        elif kind == "checkbox":
            var = tk.BooleanVar(value=bool(initial))
            check = ttk.Checkbutton(
                block,
                text=field["label"],
                variable=var,
                command=self.schedule_preview_update,
            )
            # The block heading is redundant for checkboxes, so hide it.
            for child in block.winfo_children():
                if isinstance(child, ttk.Label):
                    child.destroy()
            check.pack(anchor="w")
            control.update(var=var, widget=check)

        elif kind == "multitext":
            text_widget = tk.Text(
                block,
                height=int(field.get("height", 3)),
                bg=ENTRY_BG,
                fg=TEXT,
                insertbackground=TEXT,
                selectbackground=SELECT_BG,
                highlightthickness=1,
                highlightbackground=BORDER,
                relief="flat",
                wrap="word",
                font=("Segoe UI", 10),
                padx=6,
                pady=5,
            )
            text_widget.pack(fill="x", pady=(3, 0))
            if initial:
                text_widget.insert("1.0", str(initial))
            text_widget.bind("<KeyRelease>", lambda _event: self.schedule_preview_update())
            control.update(widget=text_widget)

        elif kind == "path_list":
            list_frame = ttk.Frame(block, style="Panel.TFrame")
            list_frame.pack(fill="x", pady=(3, 0))
            list_frame.columnconfigure(0, weight=1)

            listbox = tk.Listbox(
                list_frame,
                height=4,
                bg=ENTRY_BG,
                fg=TEXT,
                selectbackground=SELECT_BG,
                selectforeground="#ffffff",
                highlightthickness=1,
                highlightbackground=BORDER,
                borderwidth=0,
                font=("Segoe UI", 9),
            )
            listbox.grid(row=0, column=0, rowspan=3, sticky="nsew")
            if isinstance(initial, list):
                for item in initial:
                    listbox.insert("end", item)

            ttk.Button(list_frame, text="Add Files…", command=lambda: self.add_path_list_files(listbox, field)).grid(
                row=0, column=1, sticky="ew", padx=(7, 0)
            )
            ttk.Button(list_frame, text="Add Folder…", command=lambda: self.add_path_list_folder(listbox)).grid(
                row=1, column=1, sticky="ew", padx=(7, 0), pady=4
            )
            ttk.Button(list_frame, text="Remove", command=lambda: self.remove_path_list(listbox)).grid(
                row=2, column=1, sticky="ew", padx=(7, 0)
            )
            control.update(widget=listbox)

        elif kind in {"folder", "file", "file_or_folder", "save_file"}:
            var = tk.StringVar(value="" if initial is None else str(initial))
            row = ttk.Frame(block, style="Panel.TFrame")
            row.pack(fill="x", pady=(3, 0))
            row.columnconfigure(0, weight=1)
            entry = ttk.Entry(row, textvariable=var)
            entry.grid(row=0, column=0, sticky="ew")
            var.trace_add("write", lambda *_args: self.path_value_changed(field))
            button_column = 1

            if kind == "folder":
                ttk.Button(row, text="Browse…", command=lambda: self.browse_folder(var)).grid(
                    row=0, column=button_column, padx=(7, 0)
                )
            elif kind == "file":
                ttk.Button(row, text="Browse…", command=lambda: self.browse_file(var, field)).grid(
                    row=0, column=button_column, padx=(7, 0)
                )
            elif kind == "save_file":
                ttk.Button(row, text="Browse…", command=lambda: self.browse_save(var, field)).grid(
                    row=0, column=button_column, padx=(7, 0)
                )
            else:
                ttk.Button(row, text="File…", command=lambda: self.browse_file(var, field)).grid(
                    row=0, column=button_column, padx=(7, 0)
                )
                ttk.Button(row, text="Folder…", command=lambda: self.browse_folder(var)).grid(
                    row=0, column=button_column + 1, padx=(5, 0)
                )

            control.update(var=var, widget=entry)

        else:
            raise ValueError(f"Unsupported field kind: {kind}")

        if field.get("help"):
            ttk.Label(
                block,
                text=field["help"],
                style="Help.TLabel",
                wraplength=740,
                justify="left",
            ).pack(anchor="w", pady=(3, 0))

        self.controls[field["key"]] = control

    def toggle_advanced(self) -> None:
        if not hasattr(self, "advanced_fields"):
            return
        if self.advanced_visible.get():
            self.advanced_fields.pack(fill="x", pady=(4, 0))
        else:
            self.advanced_fields.pack_forget()
        self.form_container.update_idletasks()
        self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all"))

    def browse_folder(self, var: tk.StringVar) -> None:
        initial = self.initial_directory(var.get())
        selected = filedialog.askdirectory(parent=self, initialdir=initial)
        if selected:
            var.set(selected)

    def browse_file(self, var: tk.StringVar, field: dict[str, Any]) -> None:
        initial = self.initial_directory(var.get())
        selected = filedialog.askopenfilename(
            parent=self,
            initialdir=initial,
            filetypes=field.get("filetypes", [("All files", "*.*")]),
        )
        if selected:
            var.set(selected)

    def browse_save(self, var: tk.StringVar, field: dict[str, Any]) -> None:
        current = var.get().strip()
        initial_dir = self.initial_directory(current)
        initial_name = Path(current).name if current else field.get("default_name", "")
        selected = filedialog.asksaveasfilename(
            parent=self,
            initialdir=initial_dir,
            initialfile=initial_name,
            filetypes=field.get("filetypes", [("All files", "*.*")]),
        )
        if selected:
            var.set(selected)

    def add_path_list_files(self, listbox: tk.Listbox, field: dict[str, Any]) -> None:
        selected = filedialog.askopenfilenames(
            parent=self,
            filetypes=field.get("filetypes", [("Unity bundles", "*.bundle *.unity3d"), ("All files", "*.*")]),
        )
        for item in selected:
            if item not in listbox.get(0, "end"):
                listbox.insert("end", item)
        self.schedule_preview_update()

    def add_path_list_folder(self, listbox: tk.Listbox) -> None:
        selected = filedialog.askdirectory(parent=self)
        if selected and selected not in listbox.get(0, "end"):
            listbox.insert("end", selected)
        self.schedule_preview_update()

    def remove_path_list(self, listbox: tk.Listbox) -> None:
        for index in reversed(listbox.curselection()):
            listbox.delete(index)
        self.schedule_preview_update()

    @staticmethod
    def initial_directory(value: str) -> str:
        if value:
            path = Path(os.path.expandvars(os.path.expanduser(value)))
            if path.is_dir():
                return str(path)
            if path.parent.exists():
                return str(path.parent)
        return str(Path.home())

    def path_value_changed(self, field: dict[str, Any]) -> None:
        self.schedule_preview_update()
        if self.current_tool_key == "glb_thumbnails" and field["key"] == "blender":
            self.update_dependency_status()

    def get_control_value(self, key: str) -> Any:
        control = self.controls[key]
        kind = control["kind"]
        if kind in {"text", "integer", "float", "tokens", "combo", "checkbox", "folder", "file", "file_or_folder", "save_file"}:
            return control["var"].get()
        if kind == "multitext":
            return control["widget"].get("1.0", "end-1c")
        if kind == "path_list":
            return list(control["widget"].get(0, "end"))
        return ""

    def capture_current_values(self) -> None:
        if not self.current_tool_key or not self.controls:
            return
        tool_values = self.settings_data.setdefault("tools", {}).setdefault(self.current_tool_key, {})
        for key in self.controls:
            tool_values[key] = self.get_control_value(key)
        self.settings_data["last_tool"] = self.current_tool_key

    # ---------- Command generation and validation ----------

    def python_executable(self) -> str:
        return sys.executable

    def build_command(self) -> list[str]:
        if not self.current_tool_key:
            return []

        tool = self.tools[self.current_tool_key]
        script = BASE_DIR / tool["script"]
        command = [self.python_executable(), str(script)]

        # Positional values must appear before options for predictable previews.
        for field in tool["fields"]:
            if not field.get("positional"):
                continue
            value = self.get_control_value(field["key"])
            command.extend(self.value_arguments(field, value, positional=True))

        for field in tool["fields"]:
            if field.get("positional"):
                continue
            value = self.get_control_value(field["key"])
            command.extend(self.value_arguments(field, value, positional=False))

        return command

    def value_arguments(self, field: dict[str, Any], value: Any, positional: bool) -> list[str]:
        kind = field["kind"]

        if kind == "checkbox":
            checked = bool(value)
            if checked and field.get("flag"):
                return [field["flag"]]
            if not checked and field.get("false_flag"):
                return [field["false_flag"]]
            return []

        if kind == "path_list":
            return [str(item) for item in value if str(item).strip()]

        if kind in {"tokens", "multitext"}:
            tokens = split_tokens(str(value))
            if not tokens:
                return []
            if positional:
                return tokens
            return [field["flag"], *tokens]

        text = str(value).strip()
        if not text:
            return []

        if kind in {"integer", "float", "combo", "text"}:
            default = field.get("default", None)
            if default is not None and str(default) == text and not field.get("emit_default"):
                return []

        if positional:
            return [text]

        flag = field.get("flag")
        return [flag, text] if flag else []

    def validate_current(self) -> list[str]:
        if not self.current_tool_key:
            return ["No utility is selected."]

        tool = self.tools[self.current_tool_key]
        errors: list[str] = []
        script = BASE_DIR / tool["script"]
        if not script.exists():
            errors.append(f"Utility script is missing: {script.name}")

        for field in tool["fields"]:
            key = field["key"]
            value = self.get_control_value(key)
            kind = field["kind"]

            empty = (
                len(value) == 0
                if isinstance(value, list)
                else not str(value).strip()
            )
            if field.get("required") and empty:
                errors.append(f"{field['label']} is required.")
                continue

            if empty:
                continue

            if kind in {"integer", "float"}:
                try:
                    number = int(str(value)) if kind == "integer" else float(str(value))
                except ValueError:
                    errors.append(f"{field['label']} must be a valid number.")
                    continue
                if "minimum" in field and number < field["minimum"]:
                    errors.append(f"{field['label']} must be at least {field['minimum']}.")
                if "maximum" in field and number > field["maximum"]:
                    errors.append(f"{field['label']} must be no more than {field['maximum']}.")

            if field.get("must_exist"):
                values = value if isinstance(value, list) else [value]
                for item in values:
                    expanded = Path(os.path.expandvars(os.path.expanduser(str(item))))
                    if not expanded.exists():
                        errors.append(f"{field['label']} does not exist: {item}")

        dependency = tool.get("dependency")
        if dependency == "unitypy" and importlib.util.find_spec("UnityPy") is None:
            errors.append(
                "UnityPy is not installed in this Python environment. "
                "Run: python -m pip install UnityPy"
            )
        elif dependency == "blender":
            explicit = str(self.get_control_value("blender")).strip() if "blender" in self.controls else ""
            if find_blender(explicit) is None:
                errors.append(
                    "Blender was not found. Install Blender, add it to PATH, "
                    "or select blender.exe under Advanced options."
                )

        return errors

    def schedule_preview_update(self) -> None:
        if self._preview_after is not None:
            try:
                self.after_cancel(self._preview_after)
            except Exception:
                pass
        self._preview_after = self.after(100, self.update_command_preview)

    def update_command_preview(self) -> None:
        self._preview_after = None
        try:
            self.command_var.set(quote_command(self.build_command()))
        except Exception as exc:
            self.command_var.set(f"Unable to build command: {exc}")

    def update_dependency_status(self) -> None:
        if not self.current_tool_key:
            return

        tool = self.tools[self.current_tool_key]
        dependency = tool.get("dependency", "standard")
        script_ok = (BASE_DIR / tool["script"]).exists()

        if not script_ok:
            text, colour = "Script missing", ERROR
        elif dependency == "standard":
            text, colour = "Ready", SUCCESS
        elif dependency == "unitypy":
            if importlib.util.find_spec("UnityPy") is not None:
                text, colour = "UnityPy ready", SUCCESS
            else:
                text, colour = "UnityPy required", ERROR
        elif dependency == "lz4_optional":
            if importlib.util.find_spec("lz4") is not None:
                text, colour = "Ready · LZ4 installed", SUCCESS
            else:
                text, colour = "Ready · LZ4 optional", WARNING
        elif dependency == "blender":
            explicit = str(self.get_control_value("blender")).strip() if "blender" in self.controls else ""
            blender = find_blender(explicit)
            if blender:
                text, colour = "Blender ready", SUCCESS
            else:
                text, colour = "Blender required", ERROR
        else:
            text, colour = "Ready", SUCCESS

        self.dependency_label.configure(text=text, fg=colour)

    # ---------- Running utilities ----------

    def run_tool(self) -> None:
        if self.process is not None:
            return

        errors = self.validate_current()
        if errors:
            messagebox.showerror(APP_NAME, "\n\n".join(errors), parent=self)
            return

        self.capture_current_values()
        save_settings(self.settings_data)

        command = self.build_command()
        self.append_log("\n" + "=" * 78 + "\n", "muted")
        self.append_log(f"{self.tools[self.current_tool_key]['title']}\n", "success")
        self.append_log(quote_command(command) + "\n\n", "command")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=creationflags,
            )
        except Exception as exc:
            self.process = None
            self.append_log(f"ERROR: Could not start utility: {exc}\n", "error")
            messagebox.showerror(APP_NAME, f"Could not start the utility:\n\n{exc}", parent=self)
            return

        self.run_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.tool_list.configure(state="disabled")
        self.status_var.set("Running…")

        thread = threading.Thread(target=self.read_process_output, daemon=True)
        thread.start()

    def read_process_output(self) -> None:
        process = self.process
        if process is None:
            return
        try:
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    if line:
                        self.output_queue.put(("line", line))
                process.stdout.close()
            code = process.wait()
            self.output_queue.put(("done", code))
        except Exception as exc:
            self.output_queue.put(("line", f"ERROR reading process output: {exc}\n"))
            self.output_queue.put(("done", -1))

    def poll_output_queue(self) -> None:
        try:
            while True:
                kind, value = self.output_queue.get_nowait()
                if kind == "line":
                    self.append_log(value, self.tag_for_line(value))
                elif kind == "done":
                    self.process_finished(int(value))
        except queue.Empty:
            pass
        self.after(80, self.poll_output_queue)

    @staticmethod
    def tag_for_line(line: str) -> str:
        lowered = line.lower()
        if "error" in lowered or "traceback" in lowered or "failed" in lowered:
            return "error"
        if "warning" in lowered or "skipped" in lowered:
            return "warning"
        if (
            "exported" in lowered
            or lowered.startswith("done")
            or "rendered" in lowered
            or "status: ok" in lowered
            or "success" in lowered
        ):
            return "success"
        return "normal"

    def process_finished(self, code: int) -> None:
        self.process = None
        self.run_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.tool_list.configure(state="normal")

        if code == 0:
            self.append_log("\nCompleted successfully.\n", "success")
            self.status_var.set("Completed successfully")
        else:
            self.append_log(f"\nUtility finished with exit code {code}.\n", "error")
            self.status_var.set(f"Finished with exit code {code}")

    def cancel_tool(self) -> None:
        process = self.process
        if process is None:
            return

        if not messagebox.askyesno(APP_NAME, "Stop the running utility?", parent=self):
            return

        self.append_log("\nCancellation requested…\n", "warning")
        try:
            process.terminate()
        except Exception:
            pass
        self.after(1800, self.force_kill_if_running)

    def force_kill_if_running(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass

    # ---------- Output and convenience actions ----------

    def append_log(self, text: str, tag: str = "normal") -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text, tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def copy_log(self) -> None:
        value = self.log_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(value)
        self.status_var.set("Output copied to clipboard")

    def copy_command(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.command_var.get())
        self.status_var.set("Command copied to clipboard")

    def inferred_output_folder(self) -> Path | None:
        if not self.current_tool_key:
            return None

        tool = self.tools[self.current_tool_key]
        for key in tool.get("output_keys", []):
            if key in self.controls:
                value = str(self.get_control_value(key)).strip()
                if value:
                    path = Path(os.path.expandvars(os.path.expanduser(value)))
                    if self.controls[key]["kind"] == "save_file":
                        return path.parent
                    return path

        # Tool-specific defaults when no output was explicitly supplied.
        key = self.current_tool_key
        try:
            if key == "texture_extract":
                source = Path(str(self.get_control_value("inputs")))
                if bool(self.get_control_value("same_folder")):
                    return source if source.is_dir() else source.parent
                parent = source if source.is_dir() else source.parent
                return parent / "Extracted_Textures"

            if key == "glb_corrector":
                source = Path(str(self.get_control_value("input")))
                return source if source.is_dir() else source.parent

            if key == "glb_thumbnails":
                source = Path(str(self.get_control_value("input")))
                if bool(self.get_control_value("same_folder")):
                    return source if source.is_dir() else source.parent
                root = source if source.is_dir() else source.parent
                return root.with_name(root.name + "_thumbnails")

            if key == "validator":
                source = Path(str(self.get_control_value("path")))
                return source if source.is_dir() else source.parent

            if key == "lookup":
                source = Path(str(self.get_control_value("root")))
                return source if source.is_dir() else source.parent
        except Exception:
            pass

        return BASE_DIR

    def open_output_folder(self) -> None:
        folder = self.inferred_output_folder()
        if folder is None:
            return

        folder = folder.expanduser()
        if not folder.exists():
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except Exception:
                messagebox.showinfo(
                    APP_NAME,
                    f"The output folder does not exist yet:\n\n{folder}",
                    parent=self,
                )
                return

        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open the folder:\n\n{exc}", parent=self)

    # ---------- Shutdown ----------

    def on_close(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno(
                APP_NAME,
                "A utility is still running. Stop it and close the launcher?",
                parent=self,
            ):
                return
            try:
                self.process.terminate()
            except Exception:
                pass

        self.capture_current_values()
        self.settings_data["geometry"] = self.geometry()
        save_settings(self.settings_data)
        self.destroy()


def main() -> int:
    app = Launcher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
