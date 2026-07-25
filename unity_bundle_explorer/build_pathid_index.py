from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys

from .core.project_ref_index import INDEX_FILENAME, INDEX_VERSION


def _asset_name(data, type_name: str, path_id: int) -> str:
    name = ""
    try:
        name = getattr(data, "name", "") or getattr(data, "m_Name", "") or ""
        if not name and type_name == "Shader":
            parsed = getattr(data, "m_ParsedForm", None) or getattr(data, "parsed_form", None)
            name = getattr(parsed, "m_Name", "") or getattr(parsed, "name", "") or ""
    except Exception:
        name = ""
    return name or f"{type_name}_{path_id}"


def build_index(folder: str | Path, recursive: bool = False) -> Path:
    try:
        import UnityPy  # type: ignore
    except Exception as e:
        raise SystemExit(f"UnityPy is required: {e}")

    root = Path(folder).resolve()
    pattern = "**/*.bundle" if recursive else "*.bundle"
    bundles = sorted(root.glob(pattern), key=lambda p: str(p).lower())
    if not bundles:
        raise SystemExit(f"No .bundle files found in: {root}")

    records = []
    errors = []
    total_objects = 0

    print("UBE PathID index builder")
    print(f"Folder: {root}")
    print(f"Bundles: {len(bundles)}")
    print(f"Output: {root / INDEX_FILENAME}")
    print()

    for i, bundle in enumerate(bundles, 1):
        print(f"[{i}/{len(bundles)}] {bundle.name}", flush=True)
        try:
            env = UnityPy.load(str(bundle))
            bundle_objects = 0
            rel = str(bundle.relative_to(root)).replace("\\", "/")
            for obj in env.objects:
                path_id = int(getattr(obj, "path_id", 0) or 0)
                type_name = getattr(obj.type, "name", str(obj.type))
                name = ""
                try:
                    data = obj.read()
                    name = _asset_name(data, type_name, path_id)
                except Exception:
                    name = f"{type_name}_{path_id}"
                records.append({
                    "path_id": path_id,
                    "type": type_name,
                    "name": name,
                    "bundle": rel,
                })
                bundle_objects += 1
            total_objects += bundle_objects
            print(f"    objects: {bundle_objects:,}", flush=True)
        except Exception as e:
            errors.append({"bundle": str(bundle.name), "error": str(e)})
            print(f"    ERROR: {e}", flush=True)

    output = {
        "format": "UBE PathID Index",
        "version": INDEX_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "recursive": recursive,
        "bundle_count": len(bundles),
        "object_count": total_objects,
        "records": records,
        "errors": errors,
    }
    out_path = root / INDEX_FILENAME
    tmp_path = root / (INDEX_FILENAME + ".tmp")
    tmp_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)
    print()
    print(f"Done. Indexed {total_objects:,} objects from {len(bundles):,} bundle(s).")
    print(f"Wrote: {out_path}")
    if errors:
        print(f"Warnings/errors: {len(errors)}")
    return out_path


def _json_line_value(line: str):
    """Parse a single pretty-printed JSON value line from our index.

    Example: '      "name": "foo",'
    """
    _, value = line.split(":", 1)
    value = value.strip()
    if value.endswith(","):
        value = value[:-1]
    return json.loads(value)


def lookup_pathid(folder: str | Path, path_id: int, max_results: int = 50) -> list[dict[str, object]]:
    """Fast-ish streaming lookup for one PathID in .ube_pathid_index.json.

    This deliberately does not json.load() a multi-million-record index.  It
    scans the file line-by-line and only materialises matching records.  The
    generated index is pretty-printed in a stable field order:
        path_id, type, name, bundle
    """
    root = Path(folder).resolve()
    p = root / INDEX_FILENAME
    if not p.exists():
        raise SystemExit(f"Missing index: {p}\nBuild it first with: python -m unity_bundle_explorer.build_pathid_index \"{root}\"")

    matches: list[dict[str, object]] = []
    target_text = f'"path_id": {path_id}'
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            if target_text not in line:
                continue
            try:
                found_pid = int(_json_line_value(line))
            except Exception:
                continue
            if found_pid != path_id:
                continue

            item: dict[str, object] = {"path_id": found_pid}
            # Read the rest of this record. Our builder writes type/name/bundle
            # immediately after path_id, but stop safely at object end.
            for subline in fh:
                stripped = subline.strip()
                if stripped.startswith('"type"'):
                    item["type"] = _json_line_value(subline)
                elif stripped.startswith('"name"'):
                    item["name"] = _json_line_value(subline)
                elif stripped.startswith('"bundle"'):
                    rel = str(_json_line_value(subline))
                    item["bundle"] = rel
                    item["full_path"] = str(root / rel)
                elif stripped.startswith("}"):
                    break
            matches.append(item)
            if len(matches) >= max_results:
                break
    return matches


def _print_lookup(folder: str | Path, path_id: int, max_results: int = 50) -> int:
    matches = lookup_pathid(folder, path_id, max_results=max_results)
    print(f"PathID: {path_id}")
    print(f"Matches: {len(matches)}")
    print()
    if not matches:
        print("No matches found in .ube_pathid_index.json")
        return 1
    for i, m in enumerate(matches, 1):
        print(f"[{i}] {m.get('type', 'Unknown')}  {m.get('name', '')}")
        print(f"    bundle: {m.get('bundle', '')}")
        print(f"    full:   {m.get('full_path', '')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    recursive = False
    max_results = 50
    path_id_arg = None

    if "--recursive" in args:
        recursive = True
        args.remove("--recursive")

    # Manual lookup mode.  Accept both spellings because PathID is what Unity
    # users tend to call it, while command lines often use lowercase.
    for flag in ("--pathID", "--pathid"):
        if flag in args:
            pos = args.index(flag)
            try:
                path_id_arg = int(args[pos + 1])
            except Exception:
                print(f"{flag} needs an integer PathID")
                return 2
            del args[pos:pos + 2]
            break

    if "--max" in args:
        pos = args.index("--max")
        try:
            max_results = max(1, int(args[pos + 1]))
        except Exception:
            print("--max needs a number")
            return 2
        del args[pos:pos + 2]

    if not args:
        print("Usage:")
        print("  python -m unity_bundle_explorer.build_pathid_index <folder>")
        print("  python -m unity_bundle_explorer.build_pathid_index <folder> --recursive")
        print("  python -m unity_bundle_explorer.build_pathid_index <folder> --pathID <id>")
        return 2

    if path_id_arg is not None:
        return _print_lookup(args[0], path_id_arg, max_results=max_results)

    build_index(args[0], recursive=recursive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
