from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
from typing import Any, Iterable


def safe_report_filename(value: str, fallback: str = "inspector-report", max_length: int = 150) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or fallback))
    text = re.sub(r"\s+", " ", text).strip(" ._") or fallback
    return text[:max_length]


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _entry_anchor(entry: dict[str, Any], index: int) -> str:
    source = str(entry.get("source_name", "") or "")
    path_id = str(entry.get("path_id", "") or "")
    seed = f"{source}-{path_id}-{index}"
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", seed).strip("-")
    return f"asset-{safe or index}"


def _page_start(title: str) -> list[str]:
    return [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{escape(title)}</title>",
        "<style>",
        "body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#f4f5f7;color:#202124;line-height:1.38}",
        ".page{max-width:1180px;margin:0 auto;padding:28px}",
        ".hero,.asset,.toc{background:#fff;border:1px solid #d8dde5;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.06)}",
        ".hero{padding:22px 24px;margin-bottom:18px}",
        ".hero h1{margin:0 0 8px;font-size:25px}.hero p{margin:4px 0;color:#555}",
        ".meta{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}",
        ".badge{display:inline-block;background:#eef2f7;border:1px solid #d7dee9;border-radius:12px;padding:3px 9px;font-size:12px;color:#3f4752}",
        ".toc{padding:16px 20px;margin-bottom:18px}.toc h2{margin:0 0 10px;font-size:18px}",
        ".toc ol{columns:2;column-gap:40px;margin:0;padding-left:24px}.toc li{break-inside:avoid;margin:3px 0}",
        "a{color:#1769aa;text-decoration:none}a:hover{text-decoration:underline}",
        ".asset{padding:18px 20px;margin:0 0 18px;page-break-inside:avoid}",
        ".asset h2{margin:0 0 6px;font-size:20px}.submeta{color:#666;font-size:12px;margin-bottom:12px}",
        ".comment{white-space:pre-wrap;background:#fff8db;border-left:5px solid #e0b62f;padding:10px 12px;margin:12px 0;border-radius:3px}",
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,'Cascadia Mono',monospace;font-size:12.5px;line-height:1.42;background:#f7f8fa;border:1px solid #e0e4ea;border-radius:7px;padding:14px;margin:10px 0 0}",
        ".back{font-size:12px;float:right}.muted{color:#6a7078}",
        "@media(max-width:780px){.page{padding:12px}.toc ol{columns:1}}",
        "@media print{body{background:#fff}.page{max-width:none;padding:0}.hero,.asset,.toc{box-shadow:none}.back{display:none}.asset{page-break-inside:avoid}}",
        "</style></head><body><div class='page'>",
    ]


def _hero_html(
    report_title: str,
    bundle_name: str,
    bundle_sha256: str,
    unity_version: str,
    source_kind: str,
    count: int,
) -> str:
    badges = [f"{count} asset{'s' if count != 1 else ''}"]
    if unity_version:
        badges.append(f"Unity {unity_version}")
    if source_kind:
        badges.append(source_kind)
    badge_html = "".join(f"<span class='badge'>{escape(x)}</span>" for x in badges)
    sha_line = f"<p><b>SHA-256:</b> <span class='muted'>{escape(bundle_sha256)}</span></p>" if bundle_sha256 else ""
    return (
        "<section class='hero' id='top'>"
        f"<h1>{escape(report_title)}</h1>"
        f"<p><b>Source:</b> {escape(bundle_name or 'Unknown source')}</p>"
        f"{sha_line}"
        f"<p><b>Generated:</b> {_utc_now_text()}</p>"
        f"<div class='meta'>{badge_html}</div>"
        "</section>"
    )


def _asset_html(entry: dict[str, Any], index: int, include_back_link: bool = True) -> str:
    anchor = _entry_anchor(entry, index)
    name = str(entry.get("name", "") or "Unnamed asset")
    asset_type = str(entry.get("asset_type", "") or "Asset")
    source_name = str(entry.get("source_name", "") or "")
    path_id = entry.get("path_id", "")
    comment = str(entry.get("comment", "") or "").strip()
    inspector_text = str(entry.get("inspector_text", "") or "")
    back = "<a class='back' href='#top'>Back to contents ↑</a>" if include_back_link else ""
    comment_html = f"<div class='comment'><b>External comment</b><br>{escape(comment)}</div>" if comment else ""
    source_bits = []
    if source_name:
        source_bits.append(f"SerializedFile: {escape(source_name)}")
    if path_id != "":
        source_bits.append(f"Path ID: {escape(str(path_id))}")
    source_line = " · ".join(source_bits)
    return (
        f"<section class='asset' id='{anchor}'>"
        f"{back}<h2>{escape(name)}</h2>"
        f"<div class='submeta'>{escape(asset_type)}{(' · ' + source_line) if source_line else ''}</div>"
        f"{comment_html}"
        f"<pre>{escape(inspector_text)}</pre>"
        "</section>"
    )


def write_combined_html_report(
    entries: Iterable[dict[str, Any]],
    output_folder: str | Path,
    base_name: str,
    report_title: str,
    *,
    bundle_name: str = "",
    bundle_sha256: str = "",
    unity_version: str = "",
    source_kind: str = "",
) -> Path:
    rows = list(entries)
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = safe_report_filename(base_name) + ".html"
    target = folder / filename

    html = _page_start(report_title)
    html.append(_hero_html(report_title, bundle_name, bundle_sha256, unity_version, source_kind, len(rows)))
    if len(rows) > 1:
        html.append("<section class='toc'><h2>Contents</h2><ol>")
        for index, entry in enumerate(rows):
            anchor = _entry_anchor(entry, index)
            label = str(entry.get("name", "") or "Unnamed asset")
            kind = str(entry.get("asset_type", "") or "Asset")
            html.append(f"<li><a href='#{anchor}'>{escape(label)}</a> <span class='muted'>({escape(kind)})</span></li>")
        html.append("</ol></section>")
    for index, entry in enumerate(rows):
        html.append(_asset_html(entry, index, include_back_link=len(rows) > 1))
    html.append("</div></body></html>")
    target.write_text("".join(html), encoding="utf-8")
    return target


def write_separate_html_reports(
    entries: Iterable[dict[str, Any]],
    output_folder: str | Path,
    *,
    bundle_name: str = "",
    bundle_sha256: str = "",
    unity_version: str = "",
    source_kind: str = "",
) -> list[Path]:
    rows = list(entries)
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    used: set[str] = set()

    for index, entry in enumerate(rows):
        name = str(entry.get("name", "") or "Unnamed asset")
        kind = str(entry.get("asset_type", "") or "Asset")
        path_id = str(entry.get("path_id", "") or index)
        stem = safe_report_filename(f"{name} - {kind} - {path_id}")
        candidate = stem
        suffix = 2
        while candidate.lower() in used or (folder / f"{candidate}.html").exists():
            candidate = safe_report_filename(f"{stem} ({suffix})")
            suffix += 1
        used.add(candidate.lower())
        title = f"{name} — UBE Inspector Report"
        html = _page_start(title)
        html.append(_hero_html(title, bundle_name, bundle_sha256, unity_version, source_kind, 1))
        html.append(_asset_html(entry, index, include_back_link=False))
        html.append("</div></body></html>")
        target = folder / f"{candidate}.html"
        target.write_text("".join(html), encoding="utf-8")
        paths.append(target)
    return paths
