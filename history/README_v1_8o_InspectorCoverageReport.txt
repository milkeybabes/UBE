UBE v1.8o build 235 - Inspector Coverage Report

Adds View -> Inspector Coverage Report...

The report scans the currently opened bundle and shows:
  - asset types present in the bundle
  - object counts per type
  - whether UBE has Strong / Good / Basic / Raw coverage
  - what the specialised inspector explains
  - whether a preview exists
  - whether export is supported
  - possible next useful inspector targets found in the current bundle

This is meant as both a GitHub/release transparency feature and a development
guide, so users can see what UBE understands well and what is still best-effort.

The dialog can copy or export the report as TSV.
