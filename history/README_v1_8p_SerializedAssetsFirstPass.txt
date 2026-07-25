UBE v1.8p build 236 - Unity SerializedFile / .assets First Pass

This build keeps the normal AssetBundle workflow but adds first-pass support for
Unity SerializedFile sources used by many older PC/Steam Unity games.

New File menu entries:
  File -> Open Unity Serialized Assets...
  File -> Open Serialized Assets Folder...

Recognised source files include:
  globalgamemanagers
  globalgamemanagers.assets
  sharedassets*.assets
  resources.assets
  level* files that use the Unity SerializedFile header

Important:
  .resS and .resource files are sidecar byte stores.  They are not opened directly.
  The .assets/globalgamemanagers file is the object database that references them.

What works in this first pass:
  - Detects UnitySerializedFile headers.
  - Shows source type in the dashboard.
  - Opens the file with UnityPy using the same inspector/index path as bundles.
  - Lists a folder of .assets/globalgamemanagers sources and lets you open them.
  - Keeps existing UBE inspectors/previews/export logic for objects UnityPy exposes.

What is not complete yet:
  - Cross-file FileID/PathID resolving across sharedassets/globalgamemanagers is not
    fully implemented.
  - Folder mode is a source selector, not a merged project database.
  - If a texture/audio blob is in a .resS file, it depends on UnityPy being able to
    locate the sidecar file beside the .assets file.

This is intentionally not a converter.  UBE now has two honest source modes:
  - UnityFS AssetBundle-style source
  - Unity SerializedFile .assets/globalgamemanagers-style source
