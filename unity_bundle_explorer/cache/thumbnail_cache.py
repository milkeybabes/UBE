from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..exporters.texture_exporter import safe_filename


@dataclass(slots=True)
class TexturePreviewResult:
    path: Path
    width: int
    height: int
    mode: str
    has_alpha: bool
    source_was_decoded: bool


def default_cache_root() -> Path:
    return Path.home() / ".ube_cache" / "previews"


def _has_alpha(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def preview_cache_path(record, bundle_sha: str | None, cache_root: str | Path | None = None, size: int = 512) -> Path:
    root = Path(cache_root) if cache_root else default_cache_root()
    sha = (bundle_sha or "unknown")[:16]
    name = safe_filename(record.name, f"texture_{record.path_id}")
    return root / sha / f"{name}_{record.path_id}_{size}.png"


def get_texture_preview(record, bundle_sha: str | None = None, *, size: int = 512, cache_root: str | Path | None = None) -> TexturePreviewResult | None:
    """Return a small PNG preview for a Texture2D record.

    The texture is decoded only if a cached preview does not already exist.
    This keeps UBE responsive when browsing large projects.
    """
    dst = preview_cache_path(record, bundle_sha, cache_root, size)
    if dst.exists():
        try:
            with Image.open(dst) as img:
                return TexturePreviewResult(
                    path=dst,
                    width=img.width,
                    height=img.height,
                    mode=img.mode,
                    has_alpha=_has_alpha(img),
                    source_was_decoded=False,
                )
        except Exception:
            try:
                dst.unlink()
            except Exception:
                pass

    try:
        data = record.object.read()
        img = data.image
    except Exception:
        return None

    try:
        # Keep alpha where present, but normalise exotic modes for Qt loading.
        has_alpha = _has_alpha(img)
        if has_alpha:
            preview = img.convert("RGBA")
        else:
            preview = img.convert("RGB")

        preview.thumbnail((size, size), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        preview.save(dst)
        return TexturePreviewResult(
            path=dst,
            width=img.width,
            height=img.height,
            mode=img.mode,
            has_alpha=has_alpha,
            source_was_decoded=True,
        )
    except Exception:
        return None
