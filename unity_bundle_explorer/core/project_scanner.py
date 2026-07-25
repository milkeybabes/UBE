from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

_ASSETS_RE = re.compile(r"^(?P<prefix>.+?common)_assets_\.bundle$", re.IGNORECASE)
_SCENE_RE = re.compile(r"^(?P<prefix>.+?common)_scenes_(?P<scene>.+)\.bundle$", re.IGNORECASE)


def _nice_course_name(prefix: str) -> str:
    # Walkabout uses names like "alfheimcommon" or "shangri-lacommon".
    if prefix.lower().endswith("common"):
        prefix = prefix[:-6]
    return prefix.replace("-", " ").replace("_", " ").strip() or prefix


def _scene_variant(scene: str) -> str:
    s = scene.lower()
    if s.endswith("_easy"):
        return "easy"
    if s.endswith("_hard"):
        return "hard"
    if s.endswith("_v001"):
        return "v001 / easy"
    # A few older courses use scene.bundle for easy/normal and scene_hard.bundle for hard.
    if "homestar" in s or "pack" in s or "distraction" in s:
        return "add-on / pack"
    return "scene"


@dataclass(slots=True)
class SceneBundle:
    path: Path
    scene_name: str
    variant: str


@dataclass(slots=True)
class CourseGroup:
    prefix: str
    display_name: str
    assets_bundle: Path | None = None
    scenes: list[SceneBundle] = field(default_factory=list)
    extras: list[Path] = field(default_factory=list)

    @property
    def bundle_count(self) -> int:
        return (1 if self.assets_bundle else 0) + len(self.scenes) + len(self.extras)


@dataclass(slots=True)
class ProjectIndex:
    folder: Path
    courses: dict[str, CourseGroup] = field(default_factory=dict)
    loose_bundles: list[Path] = field(default_factory=list)
    obb_files: list[Path] = field(default_factory=list)

    @property
    def bundle_count(self) -> int:
        return sum(c.bundle_count for c in self.courses.values()) + len(self.loose_bundles)


def scan_project_folder(folder: str | Path) -> ProjectIndex:
    root = Path(folder)
    project = ProjectIndex(folder=root)
    all_bundle_paths = sorted(root.rglob("*.bundle"), key=lambda p: str(p.relative_to(root)).lower())

    matched: set[Path] = set()

    for p in all_bundle_paths:
        m = _ASSETS_RE.match(p.name)
        if not m:
            continue
        prefix = m.group("prefix")
        group = project.courses.setdefault(
            prefix.lower(),
            CourseGroup(prefix=prefix, display_name=_nice_course_name(prefix)),
        )
        group.assets_bundle = p
        matched.add(p)

    for p in all_bundle_paths:
        m = _SCENE_RE.match(p.name)
        if not m:
            continue
        prefix = m.group("prefix")
        scene = m.group("scene")
        key = prefix.lower()
        group = project.courses.setdefault(
            key,
            CourseGroup(prefix=prefix, display_name=_nice_course_name(prefix)),
        )
        group.scenes.append(SceneBundle(path=p, scene_name=scene, variant=_scene_variant(scene)))
        matched.add(p)

    # Anything that didn't fit a common_assets/common_scenes family stays loose for now.
    for p in all_bundle_paths:
        if p not in matched:
            project.loose_bundles.append(p)

    project.obb_files = sorted(root.rglob("*.obb"), key=lambda p: str(p.relative_to(root)).lower())

    for group in project.courses.values():
        group.scenes.sort(key=lambda s: (s.variant, s.scene_name.lower()))

    return project



def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return a.absolute() == b.absolute()


def _course_bundle_paths(course: CourseGroup) -> list[Path]:
    paths: list[Path] = []
    if course.assets_bundle is not None:
        paths.append(course.assets_bundle)
    paths.extend(scene.path for scene in course.scenes)
    paths.extend(course.extras)
    return paths



def all_project_bundle_paths(project: ProjectIndex) -> list[Path]:
    """Return every bundle known to the project scanner, in a stable order.

    Course-local bundles are listed before loose/global bundles.  This is used by
    the external reference resolver as a second-pass fallback when a reference is
    not found in the obvious course sibling bundle.
    """
    paths: list[Path] = []
    for course in project.courses.values():
        for p in _course_bundle_paths(course):
            if p not in paths:
                paths.append(p)
    for p in project.loose_bundles:
        if p not in paths:
            paths.append(p)
    return paths


def related_bundle_paths(project: ProjectIndex, bundle_path: str | Path) -> list[Path]:
    """Return likely sibling bundles needed to resolve external references.

    Walkabout course bundles normally come in pairs/groups like:

        <course>common_assets_.bundle
        <course>common_scenes_<scene>.bundle

    Scene bundles often reference objects in the larger assets bundle.  This
    helper gives the UI a small, course-local set to scan instead of loading the
    whole project.
    """
    current = Path(bundle_path)

    for course in project.courses.values():
        course_paths = _course_bundle_paths(course)
        if not any(_same_path(p, current) for p in course_paths):
            continue

        # Put the assets bundle first because scene bundles most often point there.
        ordered: list[Path] = []
        if course.assets_bundle is not None and not _same_path(course.assets_bundle, current):
            ordered.append(course.assets_bundle)
        for p in course_paths:
            if _same_path(p, current):
                continue
            if p not in ordered:
                ordered.append(p)
        return ordered

    # Loose bundle fallback: try other bundles in the same folder only.  This is
    # useful when the user opens one bundle directly instead of the project view.
    current_parent = current.parent
    loose = [p for p in project.loose_bundles if not _same_path(p, current) and _same_path(p.parent, current_parent)]
    return loose
