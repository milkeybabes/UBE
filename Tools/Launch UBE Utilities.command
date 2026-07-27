#!/bin/bash
#
# UBE Companion Utilities — macOS launcher
#
# Finder opens .command files through Terminal. This launcher finds a suitable
# Python installation, changes to the utility folder, and starts the same GUI
# used on Windows.
#

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

PYTHON=""

# Prefer a local virtual environment when one is supplied with or created
# beside the utility package.
for CANDIDATE in \
    "$SCRIPT_DIR/.venv/bin/python3" \
    "$SCRIPT_DIR/venv/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "/usr/local/bin/python3"
do
    if [ -x "$CANDIDATE" ]; then
        PYTHON="$CANDIDATE"
        break
    fi
done

# Fall back to the user's normal PATH.
if [ -z "$PYTHON" ] && command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
fi

if [ -z "$PYTHON" ] && command -v python >/dev/null 2>&1; then
    PYTHON="$(command -v python)"
fi

if [ -z "$PYTHON" ]; then
    MESSAGE="Python 3 could not be found.

Install Python 3, then run this launcher again.

You can also open Terminal in this folder and run:
python3 ube_utilities_gui.py"

    echo "$MESSAGE"

    if command -v osascript >/dev/null 2>&1; then
        osascript -e 'display dialog "Python 3 could not be found.\n\nInstall Python 3, then run the launcher again." with title "UBE Companion Utilities" buttons {"OK"} default button "OK"' >/dev/null 2>&1
    fi

    echo
    read -r -p "Press Return to close this window..."
    exit 1
fi

"$PYTHON" "$SCRIPT_DIR/ube_utilities_gui.py"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
    echo
    echo "UBE Companion Utilities finished with exit code $STATUS."
    echo
    echo "If the error mentions tkinter, use a Python installation that includes Tk support."
    echo
    read -r -p "Press Return to close this window..."
fi

exit "$STATUS"
