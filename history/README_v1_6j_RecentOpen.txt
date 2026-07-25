UBE v1.6j - Recent Open List
================================

Added File -> Recent menu.

The recent list stores the last 5 manually opened items:
- folders/projects opened with File -> Open Folder / Project
- individual bundle files opened with File -> Open Bundle

Recent items are labelled as Folder or Bundle, keep their full path as tooltip,
and can be cleared from the Recent menu. Missing paths are removed after a warning.

Project-internal bundle clicks do not fill the Recent menu, so opening a course
from a project view will not spam the list with every bundle you inspect.
