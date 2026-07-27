#!/usr/bin/env python3
r"""
ube_lookup_search.py

Search UBE lookup/index files to rediscover which bundle/object a screenshot came from.

Good for cases like:
  "I have a screenshot showing PathID 4643 / head_00, but I forgot which bundle it was."

Usage:
  python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00
  python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
  python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" model_84_StrongBad-HomestarIAP
  python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 3043646292460274710
  python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" avatarsandputters_assets_all.bundle

You can pass the UBE folder, a project folder, a specific JSON/DB file, or your cache/index folder.

It searches:
  .json .jsonl .txt .tsv .csv .log
  .db .sqlite .sqlite3

For SQLite databases it scans all text-ish columns in all tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable


TEXT_EXTS = {".json", ".jsonl", ".txt", ".tsv", ".csv", ".log"}
SQLITE_EXTS = {".db", ".sqlite", ".sqlite3"}
DEFAULT_EXTS = TEXT_EXTS | SQLITE_EXTS


def norm(s: Any) -> str:
    return str(s).lower()


def safe_snip(s: str, terms: list[str], width: int = 180) -> str:
    low = s.lower()
    pos = -1
    for t in terms:
        p = low.find(t.lower())
        if p >= 0:
            pos = p
            break
    if pos < 0:
        return s[:width].replace("\t", " ").replace("\r", " ").replace("\n", " ")
    start = max(0, pos - width // 3)
    end = min(len(s), start + width)
    return s[start:end].replace("\t", " ").replace("\r", " ").replace("\n", " ")


def matches_text(text: str, terms: list[str], mode: str) -> bool:
    low = text.lower()
    if mode == "all":
        return all(t.lower() in low for t in terms)
    return any(t.lower() in low for t in terms)


def iter_files(root: Path, recursive: bool, exts: set[str]) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    it = root.rglob("*") if recursive else root.glob("*")
    for p in it:
        if not p.is_file():
            continue
        if p.suffix.lower() in exts:
            yield p


def flatten_context(obj: Any, max_len: int = 400) -> str:
    try:
        if isinstance(obj, dict):
            preferred = []
            for k in (
                "name", "asset_name", "object_name", "type", "unity_type", "class",
                "path_id", "pathid", "PathID", "file", "bundle", "bundle_path",
                "source", "container", "external", "guid"
            ):
                if k in obj:
                    preferred.append(f"{k}={obj[k]}")
            if preferred:
                return "; ".join(preferred)[:max_len]
        return json.dumps(obj, ensure_ascii=False, default=str)[:max_len]
    except Exception:
        return str(obj)[:max_len]


def search_json_object(obj: Any, terms: list[str], mode: str, trail: str = "$", limit: int = 200):
    found = []
    def walk(o: Any, path: str):
        if len(found) >= limit:
            return
        if isinstance(o, dict):
            joined = " ".join(f"{k} {v}" for k, v in o.items() if not isinstance(v, (dict, list, tuple)))
            if matches_text(joined, terms, mode):
                found.append((path, flatten_context(o)))
            for k, v in o.items():
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o[:10000]):
                walk(v, f"{path}[{i}]")
        else:
            if matches_text(str(o), terms, mode):
                found.append((path, str(o)[:400]))
    walk(obj, trail)
    return found


def search_text_file(path: Path, terms: list[str], mode: str, max_matches: int):
    matches = []

    # Try structured JSON first for better context.
    if path.suffix.lower() == ".json":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            data = json.loads(text)
            for jpath, ctx in search_json_object(data, terms, mode, limit=max_matches):
                matches.append({
                    "file": str(path),
                    "where": jpath,
                    "match": ctx,
                })
                if len(matches) >= max_matches:
                    return matches
        except Exception:
            pass

    # Generic line search.
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                if matches_text(line, terms, mode):
                    matches.append({
                        "file": str(path),
                        "where": f"line {line_no}",
                        "match": safe_snip(line.strip(), terms),
                    })
                    if len(matches) >= max_matches:
                        break
    except Exception as exc:
        matches.append({
            "file": str(path),
            "where": "error",
            "match": str(exc),
        })

    return matches


def search_sqlite_file(path: Path, terms: list[str], mode: str, max_matches: int):
    matches = []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            try:
                cols_info = list(cur.execute(f'PRAGMA table_info("{table}")'))
                cols = [c[1] for c in cols_info]
                if not cols:
                    continue

                # Keep it generic; scan rows and stringify. Usually lookup DBs are small enough.
                q = f'SELECT * FROM "{table}" LIMIT 200000'
                for row_i, row in enumerate(cur.execute(q), 1):
                    text = " | ".join(f"{c}={row[c]}" for c in cols)
                    if matches_text(text, terms, mode):
                        matches.append({
                            "file": str(path),
                            "where": f"sqlite table {table} row {row_i}",
                            "match": safe_snip(text, terms, width=260),
                        })
                        if len(matches) >= max_matches:
                            con.close()
                            return matches
            except Exception as exc:
                matches.append({
                    "file": str(path),
                    "where": f"sqlite table {table} error",
                    "match": str(exc),
                })
                if len(matches) >= max_matches:
                    con.close()
                    return matches
        con.close()
    except Exception as exc:
        matches.append({
            "file": str(path),
            "where": "sqlite open error",
            "match": str(exc),
        })
    return matches


def main() -> int:
    ap = argparse.ArgumentParser(description="Search UBE lookup/index JSON or SQLite files by name, PathID, bundle, etc.")
    ap.add_argument("root", help="Folder or file to search")
    ap.add_argument("query", nargs="+", help="Search term(s), e.g. head_00 or 4643 or model_84_StrongBad-HomestarIAP")
    ap.add_argument("-r", "--recursive", action="store_true", default=True, help="Recursive folder search; default on")
    ap.add_argument("--no-recursive", action="store_false", dest="recursive", help="Only search one folder level")
    ap.add_argument("--mode", choices=["any", "all"], default="any", help="Match any term or all terms")
    ap.add_argument("--max-per-file", type=int, default=50, help="Maximum matches per file")
    ap.add_argument("--out", default="", help="Optional TSV output path")
    args = ap.parse_args()

    root = Path(args.root)
    terms = args.query

    files = list(iter_files(root, args.recursive, DEFAULT_EXTS))
    if not files:
        print("No lookup/index files found.")
        print("Try pointing this at the UBE folder, the project folder, or the folder containing your PathID JSON/database.")
        return 1

    print(f"Searching {len(files)} lookup/index file(s) for: {' '.join(terms)}")
    print()

    all_matches = []
    for p in files:
        ext = p.suffix.lower()
        if ext in SQLITE_EXTS:
            found = search_sqlite_file(p, terms, args.mode, args.max_per_file)
        else:
            found = search_text_file(p, terms, args.mode, args.max_per_file)
        all_matches.extend(found)

    if not all_matches:
        print("No matches found.")
        print()
        print("Useful screenshot search terms to try:")
        print("  head_00")
        print("  4643")
        print("  model_84_StrongBad-HomestarIAP")
        print("  3043646292460274710")
        print("  7271676646510737621")
        print("  avatarsandputters_assets_all.bundle")
        return 2

    for i, m in enumerate(all_matches, 1):
        print(f"{i}. {m['file']}")
        print(f"   {m['where']}")
        print(f"   {m['match']}")
        print()

    if args.out:
        out = Path(args.out)
    else:
        out = Path.cwd() / "ube_lookup_search_results.tsv"

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["file", "where", "match"], delimiter="\t")
        w.writeheader()
        for m in all_matches:
            w.writerow(m)

    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
