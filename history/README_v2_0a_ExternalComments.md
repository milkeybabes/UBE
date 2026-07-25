# UBE v2.0a — External JSON Comments and Tree Columns

Build 263 introduces UBE's first annotation system.

## External comments

- Select any asset and use the new **External comment** card in the inspector.
- Click **Add** or **Edit** to enter a multiline descriptive comment.
- Comments have no imposed character limit.
- The same commands are also available by right-clicking an asset in the tree.
- Assets with comments show a speech-bubble marker and their comment is searchable from the normal tree search box.

## Automatic JSON loading

Comments are saved as readable JSON files in:

```text
UBE_Comments/
```

The folder is created beside the running UBE application/source folder when the first comment is saved.

When a Unity bundle or SerializedFile is opened, UBE automatically checks for a matching JSON file. Matching uses the source file's SHA256, so the JSON still loads if the bundle or JSON is copied to another folder or the JSON filename is changed.

Each asset comment is keyed by:

```text
internal SerializedFile name + Path ID
```

This is important because a Path ID is unique only inside its owning Unity SerializedFile. Two internal files may both contain Path ID 8927 without referring to the same asset.

The JSON also stores the asset name and asset type as readable validation metadata.

## Tree column controls

Use:

```text
View > Asset Tree Columns
```

The following columns can be shown or hidden independently:

- Kind
- Path ID
- Comment Preview

The choices are remembered between UBE sessions. Path ID is hidden by default in this build, while Kind and Comment Preview are visible.

## Sharing

A comment JSON can be shared with another user who has the exact same bundle/file. Put it in that user's `UBE_Comments` folder; UBE identifies it from the SHA256 stored inside the JSON rather than relying only on its filename.
