UBE external comment files are stored here automatically.

Each *.ube-comments.json file is plain UTF-8 JSON. UBE matches it to the exact
Unity bundle or SerializedFile using the SHA256 recorded inside the JSON, so a
shared JSON may be renamed and will still be detected.

You do not need to create or open these files manually. Select an asset in UBE
and click the External comment field in the inspector.
