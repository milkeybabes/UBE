from __future__ import annotations

import math
import re
from typing import Any


def _matrix_values(matrix: Any) -> tuple[float, ...] | None:
    """Return a finite row-major 4x4 matrix tuple, or ``None``."""
    try:
        values = tuple(float(matrix[row][column]) for row in range(4) for column in range(4))
    except Exception:
        return None
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        return None
    return values


def _matrices_match(a: Any, b: Any, tolerance: float = 1.0e-5) -> bool:
    av = _matrix_values(a)
    bv = _matrix_values(b)
    if av is None or bv is None:
        return False
    return all(abs(left - right) <= tolerance for left, right in zip(av, bv))


def _variant_name_parts(name: str) -> tuple[str, str] | None:
    """Return a numbered namespace family and rendered suffix.

    Imported variant sets commonly use names such as::

        Chicken_Rig_06:LevelGeo_sandPS.269
        Chicken_Rig_07:LevelGeo_sandPS.269

    The numbered namespace identifies the alternative rig while the identical
    suffix identifies the equivalent rendered role.  Requiring both pieces
    keeps this detector away from ordinary multi-part assemblies.
    """
    text = str(name or "").strip()
    if ":" not in text:
        return None
    prefix, suffix = text.split(":", 1)
    prefix = prefix.strip().lower()
    suffix = suffix.strip().lower()
    if not prefix or not suffix or not re.search(r"\d", prefix):
        return None
    family = re.sub(r"\d+", "#", prefix)
    family = re.sub(r"[_\-. ]+", "_", family).strip("_")
    suffix = re.sub(r"\s+", " ", suffix)
    return family, suffix


def detect_overlapping_render_variants(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Detect a conservative mutually-exclusive imported renderer set.

    A match requires all candidates to be skinned renderers with:

    * the same rendered-name suffix beneath numbered namespaces;
    * the same transform matrix and structural mesh signature;
    * distinct mesh assets.

    This is deliberately stricter than a filename-only heuristic.  It identifies
    alternatives occupying the same authored space, not ordinary body/head/prop
    parts that should be displayed together.
    """
    rows = [row for row in (candidates or []) if isinstance(row, dict)]
    if not 2 <= len(rows) <= 32:
        return None
    if not all(bool(row.get("is_skinned")) for row in rows):
        return None

    name_parts = [_variant_name_parts(str(row.get("name") or "")) for row in rows]
    if any(part is None for part in name_parts):
        return None
    families = {part[0] for part in name_parts if part is not None}
    suffixes = {part[1] for part in name_parts if part is not None}
    if len(families) != 1 or len(suffixes) != 1:
        return None

    # Require different numbered namespaces rather than repeated renderer rows.
    names = {str(row.get("name") or "").strip().lower() for row in rows}
    if len(names) != len(rows):
        return None

    base_matrix = rows[0].get("matrix")
    if any(not _matrices_match(base_matrix, row.get("matrix")) for row in rows[1:]):
        return None

    signatures = [row.get("mesh_signature") for row in rows]
    if any(signature is None for signature in signatures) or len(set(signatures)) != 1:
        return None

    mesh_keys = [row.get("mesh_key") for row in rows]
    if any(key is None for key in mesh_keys) or len(set(mesh_keys)) < 2:
        return None

    suffix = next(iter(suffixes))
    return {
        "count": len(rows),
        "default_index": 0,
        "family": next(iter(families)),
        "render_role": suffix,
        "reason": (
            f"{len(rows)} overlapping numbered skinned variants share the same "
            f"transform, mesh structure and rendered role '{suffix}'"
        ),
    }
