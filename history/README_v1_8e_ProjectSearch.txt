UBE v1.8e - Project Search / PathID Lookup
==========================================

Adds View -> Project Search / PathID Lookup... (Ctrl+Shift+F).

Searches:
- Current loaded bundle records by name, Unity type, PathID, owner and hierarchy hint.
- Related/external records already known by the resolver.
- Project bundle filenames when a folder/project is open.
- Optional .ube_pathid_index.json using a streaming search, so it does not json.load the whole global index.

Useful examples:
- head_00
- 4643
- model_84_StrongBad
- avatarsandputters
- Texture2D

Results are clickable. Asset results open the owning bundle and select the PathID. Bundle results open the bundle. Results can be copied/exported as TSV.
