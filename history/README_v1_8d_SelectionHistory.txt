UBE v1.8d - Selection History / Session Log
==========================================

Build: 224

Adds a View menu item:

  View -> Selection History / Session Log...

Every normal asset/component selection is recorded in a separate session log:

  timestamp
  bundle path/name
  asset name
  Unity type
  PathID
  owning GameObject where known
  hierarchy hint where known

Why this exists
---------------
When browsing many bundles it is easy to take a screenshot, spot a bad preview,
or find an interesting object and then forget which bundle/object it came from.
The session log gives UBE a breadcrumb trail.

Dialog features
---------------
  - newest selections first
  - click an asset name to return to it
  - copy TSV to clipboard
  - export TSV
  - clear current session history

UBE also appends a local TSV copy to:

  %USERPROFILE%\.ube_cache\selection_history.tsv

This auto-saved file is local only and is useful if the app is closed after a
long investigation session.

Notes
-----
This history is separate from the Back/Forward navigation list. Back/Forward is
for moving through the current navigation stack; Selection History is a longer
research breadcrumb trail.
