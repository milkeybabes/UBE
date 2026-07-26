# Troubleshooting

## Python `unicodeescape` error on Windows paths

If Python reports an error like this:

```text
SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes ... truncated \UXXXXXXXX escape
```

it usually means a Windows path such as `G:\Users\...` or `G:\Pico4\...\UBE` was placed inside a normal Python string or docstring without escaping.

The included scripts use raw docstrings, so this should not happen.

For your own Python scripts, use one of these forms:

```python
path = r"G:\Pico4\WalkAboutMiniGolf\UBE"
```

or:

```python
path = "G:\\Pico4\\WalkAboutMiniGolf\\UBE"
```

or use forward slashes:

```python
path = "G:/Pico4/WalkAboutMiniGolf/UBE"
```

## No files matched

For `unity_bundle_header_scan.py`, try:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --all
```

This scans every file and ignores extension filtering.

## Lookup search finds too many results

Use `--mode all` or a more specific query:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 4643 --mode all
```

## Lookup search finds nothing

Try broader terms:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" avatarsandputters
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
```

Also make sure you are pointing the script at the folder containing your UBE cache, JSON, TSV, log, or database files.
