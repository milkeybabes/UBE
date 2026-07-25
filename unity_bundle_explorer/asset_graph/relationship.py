from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssetRelationship:
    """One directed relationship between two Unity/UBE assets.

    Example:
        Material -- _BaseMap/_ColorMap --> Texture
    """

    source_path_id: int
    source_name: str
    source_type: str
    target_path_id: int | None
    target_name: str
    target_type: str
    relationship: str
    file_id: int | None = None
    resolved: bool = False
    external_bundle: str | None = None
    # v1.8ze: PathIDs collide between internal SerializedFiles in UnityFS.
    # These names disambiguate level0/resources.assets/sharedassets0.assets.
    source_source_name: str = ""
    target_source_name: str = ""
